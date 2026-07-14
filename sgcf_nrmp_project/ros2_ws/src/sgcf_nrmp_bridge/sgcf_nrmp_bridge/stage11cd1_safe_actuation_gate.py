"""P0 safe-actuation gate; the sole Stage 11C-D1 /cmd_vel publisher."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


ALLOWED_STATUSES = {"SOLVED_SAFE", "SOLVED_WITH_SLACK"}


class SafeActuationGate(Node):
    def __init__(self, output: Path):
        super().__init__("stage11cd1_safe_actuation_gate")
        if self.has_parameter("use_sim_time"):
            self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        else:
            self.declare_parameter("use_sim_time", True)
        self.output = output
        output.parent.mkdir(parents=True, exist_ok=True)
        self.publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
        self.create_subscription(Clock, "/clock", self.on_clock, qos)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos)
        self.create_subscription(Odometry, "/odom", self.on_odom, qos)
        self.create_subscription(Twist, "/sgcf/planner_candidate_cmd_vel", self.on_candidate, 10)
        self.create_subscription(String, "/sgcf/planner_status", self.on_status, 10)
        self.create_subscription(String, "/sgcf/planner_diagnostics", self.on_diagnostics, 10)
        self.timer = self.create_timer(0.05, self.on_timer)
        self.sim_time = self.baseline_start = self.active_start = self.stop_start = None
        self.scan_stamp = self.odom_stamp = None
        self.candidate = None
        self.status = None
        self.phase = "BASELINE"
        self.done = False
        self.records = []
        self.command_log = []
        self.odom_log = []
        self.scan_frames = set()
        self.odom_frames = set()
        self.odom_child_frames = set()
        self.self_return_count = 0
        self.forwarded_nonzero_count = 0
        self.rejected_count = 0
        # These are already the audited min(Planner, DiffDrive) contracts.
        # Do not add wrapper-local limits and never clamp a candidate.
        self.max_linear = float(os.environ["STAGE11CD1_CONFIG_V_MAX"])
        self.max_angular = float(os.environ["STAGE11CD1_CONFIG_W_MAX"])
        self.active_duration_s = float(os.environ.get("STAGE11CD1_ACTIVE_DURATION_S", "10.0"))
        self.freshness_s = float(os.environ.get("STAGE11CD1_FRESHNESS_S", "0.2"))
        self.allowed_modes = {
            item.strip() for item in os.environ.get("STAGE11CD1_ALLOWED_MODES", "P0").split(",")
            if item.strip()
        }
        self.latest_allowed = False
        self.latest_command = (0.0, 0.0)
        self.latest_reason = "BASELINE_ZERO"

    @staticmethod
    def stamp(msg):
        return float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) * 1e-9

    def on_clock(self, msg):
        self.sim_time = float(msg.clock.sec) + float(msg.clock.nanosec) * 1e-9
        if self.baseline_start is None:
            self.baseline_start = self.sim_time
        if self.phase == "BASELINE" and self.sim_time - self.baseline_start >= 2.0:
            self.phase = "WAITING_FOR_CANDIDATE"
            self.latest_reason = "WAITING_FOR_FRESH_CANDIDATE"
        if self.phase == "ACTIVE" and self.sim_time - self.active_start >= self.active_duration_s:
            self.phase = "FINAL_STOP"; self.stop_start = self.sim_time
            self.latest_allowed = False; self.latest_command = (0.0, 0.0); self.latest_reason = "CLOSED_LOOP_WINDOW_COMPLETE"
        if self.phase == "FINAL_STOP" and self.sim_time - self.stop_start >= 2.0:
            self.done = True

    def on_scan(self, msg):
        self.scan_stamp = self.stamp(msg); self.scan_frames.add(msg.header.frame_id)
        for index in list(range(43, 48)) + list(range(133, 138)):
            if index < len(msg.ranges) and math.isfinite(msg.ranges[index]) and msg.ranges[index] < 0.5:
                self.self_return_count += 1

    def on_odom(self, msg):
        self.odom_stamp = self.stamp(msg); self.odom_frames.add(msg.header.frame_id); self.odom_child_frames.add(msg.child_frame_id)
        p, q, t = msg.pose.pose.position, msg.pose.pose.orientation, msg.twist.twist
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        self.odom_log.append({"sim_time": self.sim_time, "stamp": self.odom_stamp, "x": p.x, "y": p.y, "yaw": yaw, "v": t.linear.x, "w": t.angular.z})

    def on_candidate(self, msg):
        self.candidate = (float(msg.linear.x), float(msg.angular.z), float(msg.linear.y), float(msg.linear.z), float(msg.angular.x), float(msg.angular.y))

    def on_status(self, msg):
        self.status = msg.data

    def on_diagnostics(self, msg):
        record = json.loads(msg.data)
        if self.phase == "WAITING_FOR_CANDIDATE":
            self.phase = "ACTIVE"; self.active_start = self.sim_time
        candidate = tuple(float(x) for x in record["result"]["candidate"])
        published_match = self.candidate is not None and abs(self.candidate[0] - candidate[0]) <= 1e-9 and abs(self.candidate[1] - candidate[1]) <= 1e-9 and all(abs(x) <= 1e-12 for x in self.candidate[2:])
        scan_age = None if self.sim_time is None else self.sim_time - float(record["scan_timestamp"])
        odom_age = None if self.sim_time is None else self.sim_time - float(record["odom_timestamp"])
        checks = {
            "phase_active": self.phase == "ACTIVE", "mode_allowed": record["mode"] in self.allowed_modes,
            "core_eligible": bool(record["result"]["eligible"]), "deadline_ok": not record["deadline_miss"] and record["latency"]["total_ms"] <= 200.0,
            "scan_fresh": scan_age is not None and -1e-9 <= scan_age <= self.freshness_s,
            "odom_fresh": odom_age is not None and -1e-9 <= odom_age <= self.freshness_s,
            "candidate_fresh": scan_age is not None and -1e-9 <= scan_age <= self.freshness_s,
            "frame_valid": self.scan_frames == {"sgcf_robot/lidar_link/lidar"} and self.odom_frames == {"odom"} and self.odom_child_frames == {"base_link"},
            "finite": all(math.isfinite(x) for x in candidate), "status_allowed": record["result"]["status"] in ALLOWED_STATUSES,
            "not_collision": not record["current_collision"], "linear_bound": abs(candidate[0]) <= self.max_linear + 1e-12,
            "angular_bound": abs(candidate[1]) <= self.max_angular + 1e-12, "published_candidate_match": published_match,
        }
        allowed = all(checks.values())
        reason = None if allowed else next(key for key, value in checks.items() if not value)
        self.latest_allowed = allowed
        self.latest_command = candidate if allowed else (0.0, 0.0)
        self.latest_reason = reason
        if not allowed: self.rejected_count += 1
        row = {"simulation_timestamp": record["simulation_timestamp"], "record": record, "checks": checks, "actuation_eligible": allowed, "final_command": list(self.latest_command), "zero_fallback_reason": reason, "scan_age_s": scan_age, "odom_age_s": odom_age}
        self.records.append(row)

    def publish(self, v, w, reason):
        msg = Twist(); msg.linear.x = float(v); msg.angular.z = float(w); self.publisher.publish(msg)
        if abs(v) > 1e-12 or abs(w) > 1e-12: self.forwarded_nonzero_count += 1
        self.command_log.append({"sim_time": self.sim_time, "phase": self.phase, "v": float(v), "w": float(w), "reason": reason})

    def on_timer(self):
        if self.phase == "ACTIVE" and self.latest_allowed:
            self.publish(*self.latest_command, "FORWARDED_UNMODIFIED")
        else:
            self.publish(0.0, 0.0, self.latest_reason)

    def finish(self):
        for _ in range(5): self.publish(0.0, 0.0, "FINAL_ZERO")
        result = {"status": "PASSED", "phase": self.phase, "records": self.records, "command_log": self.command_log, "odom_log": self.odom_log, "forwarded_nonzero_count": self.forwarded_nonzero_count, "rejected_count": self.rejected_count, "self_return_count": self.self_return_count, "frames": {"scan": sorted(self.scan_frames), "odom": sorted(self.odom_frames), "odom_child": sorted(self.odom_child_frames)}, "bounds": {"linear": self.max_linear, "angular": self.max_angular}, "freshness_s": self.freshness_s}
        self.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main():
    rclpy.init(); node = SafeActuationGate(Path(os.environ["STAGE11CD1_GATE_OUT"])); stopping = False
    def stop(_sig, _frame):
        nonlocal stopping; stopping = True
    signal.signal(signal.SIGINT, stop); signal.signal(signal.SIGTERM, stop)
    try:
        deadline = time.monotonic() + 120
        while rclpy.ok() and not node.done and not stopping:
            if time.monotonic() > deadline: raise TimeoutError("safe gate wall timeout")
            rclpy.spin_once(node, timeout_sec=0.05)
        node.finish()
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == "__main__": main()
