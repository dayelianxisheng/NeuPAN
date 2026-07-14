"""Deterministic Stage 11C-B open-loop command and sensor audit node."""

from __future__ import annotations

import json
import math
import os
import signal
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, LaserScan


PHASES = (
    "BASELINE",
    "ZERO_BASELINE",
    "POSITIVE_LINEAR",
    "ZERO_AFTER_LINEAR",
    "POSITIVE_ANGULAR",
    "ZERO_AFTER_ANGULAR",
    "FINAL_STATIONARY",
    "COMPLETE",
)


class JsonLines:
    def __init__(self, path: Path):
        self._stream = path.open("w", encoding="utf-8", buffering=1)

    def write(self, value: dict) -> None:
        self._stream.write(json.dumps(value, sort_keys=True) + "\n")

    def close(self) -> None:
        self._stream.close()


class Stage11CBOpenLoopAudit(Node):
    """Publish the authorized command phases and record observable responses."""

    def __init__(self, log_dir: Path):
        super().__init__(
            "stage11cb_open_loop_audit",
        )
        # ROS 2 declares use_sim_time before this constructor when it is supplied
        # through NodeOptions / parameter overrides.  Reading the existing
        # parameter avoids a duplicate declaration on Humble.
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)
        elif not bool(self.get_parameter("use_sim_time").value):
            self.set_parameters([Parameter("use_sim_time", value=True)])
        self.linear_velocity = float(
            self.declare_parameter("linear_velocity_mps", 0.10).value
        )
        self.linear_duration = float(
            self.declare_parameter("linear_duration_s", 1.0).value
        )
        self.angular_velocity = float(
            self.declare_parameter("angular_velocity_radps", 0.30).value
        )
        self.angular_duration = float(
            self.declare_parameter("angular_duration_s", 1.0).value
        )
        self.zero_duration = float(
            self.declare_parameter("zero_settle_duration_s", 1.0).value
        )
        self.final_duration = float(
            self.declare_parameter("final_stationary_duration_s", 2.0).value
        )
        if not (
            0.0 < self.linear_velocity <= 0.15
            and 0.0 < self.angular_velocity <= 0.50
            and 0.0 < self.linear_duration <= 2.0
            and 0.0 < self.angular_duration <= 2.0
            and self.zero_duration >= 1.0
        ):
            raise ValueError("Stage 11C-B command profile exceeds its authorization")

        log_dir.mkdir(parents=True, exist_ok=True)
        self.commands = JsonLines(log_dir / "cmd_vel_ros.jsonl")
        self.odometry = JsonLines(log_dir / "odom.jsonl")
        self.scans = JsonLines(log_dir / "scan.jsonl")
        self.images = JsonLines(log_dir / "camera.jsonl")
        self.camera_info = JsonLines(log_dir / "camera_info.jsonl")
        self.clocks = JsonLines(log_dir / "clock.jsonl")
        self.result_path = log_dir / "open_loop_node_result.json"

        sensor_qos = QoSProfile(
            depth=100,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Clock, "/clock", self.on_clock, sensor_qos)
        self.create_subscription(Odometry, "/odom", self.on_odom, sensor_qos)
        self.create_subscription(LaserScan, "/scan", self.on_scan, sensor_qos)
        self.create_subscription(Image, "/camera/image_raw", self.on_image, sensor_qos)
        self.create_subscription(
            CameraInfo, "/camera/camera_info", self.on_camera_info, sensor_qos
        )
        self.timer = self.create_timer(0.02, self.on_timer)

        self.phase = "BASELINE"
        self.phase_start = None
        self.phase_records: list[dict] = []
        self.sim_time = None
        self.done = False
        self.shutdown_requested = False
        self.counts = {"clock": 0, "odom": 0, "scan": 0, "image": 0, "info": 0}
        self.final_start_counts = None

    @staticmethod
    def message_stamp(message) -> float:
        return float(message.header.stamp.sec) + float(message.header.stamp.nanosec) * 1e-9

    @staticmethod
    def yaw(odometry: Odometry) -> float:
        q = odometry.pose.pose.orientation
        return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y**2 + q.z**2))

    def on_clock(self, message: Clock) -> None:
        self.sim_time = float(message.clock.sec) + float(message.clock.nanosec) * 1e-9
        self.counts["clock"] += 1
        self.clocks.write({"sim_time_s": self.sim_time})

    def on_odom(self, message: Odometry) -> None:
        self.counts["odom"] += 1
        p = message.pose.pose.position
        t = message.twist.twist
        self.odometry.write(
            {
                "stamp_s": self.message_stamp(message),
                "phase": self.phase,
                "frame_id": message.header.frame_id,
                "child_frame_id": message.child_frame_id,
                "x": p.x,
                "y": p.y,
                "z": p.z,
                "yaw": self.yaw(message),
                "linear_x": t.linear.x,
                "linear_y": t.linear.y,
                "linear_z": t.linear.z,
                "angular_x": t.angular.x,
                "angular_y": t.angular.y,
                "angular_z": t.angular.z,
            }
        )

    def on_scan(self, message: LaserScan) -> None:
        self.counts["scan"] += 1
        self.scans.write(
            {
                "stamp_s": self.message_stamp(message),
                "phase": self.phase,
                "frame_id": message.header.frame_id,
                "angle_min": message.angle_min,
                "angle_increment": message.angle_increment,
                "range_min": message.range_min,
                "range_max": message.range_max,
                "ranges": list(message.ranges),
            }
        )

    def on_image(self, message: Image) -> None:
        self.counts["image"] += 1
        self.images.write(
            {
                "stamp_s": self.message_stamp(message),
                "phase": self.phase,
                "frame_id": message.header.frame_id,
                "width": message.width,
                "height": message.height,
                "encoding": message.encoding,
                "step": message.step,
                "data_length": len(message.data),
            }
        )

    def on_camera_info(self, message: CameraInfo) -> None:
        self.counts["info"] += 1
        self.camera_info.write(
            {
                "stamp_s": self.message_stamp(message),
                "phase": self.phase,
                "frame_id": message.header.frame_id,
                "width": message.width,
                "height": message.height,
                "k": list(message.k),
            }
        )

    def publish(self, linear_x: float, angular_z: float) -> None:
        command = Twist()
        command.linear.x = linear_x
        command.angular.z = angular_z
        self.publisher.publish(command)
        self.commands.write(
            {
                "wall_time_ns": time.time_ns(),
                "sim_time_s": self.sim_time,
                "phase": self.phase,
                "linear_x": linear_x,
                "linear_y": 0.0,
                "linear_z": 0.0,
                "angular_x": 0.0,
                "angular_y": 0.0,
                "angular_z": angular_z,
            }
        )

    def transition(self, new_phase: str) -> None:
        if self.phase_start is not None:
            self.phase_records[-1]["end_sim_time_s"] = self.sim_time
        self.phase = new_phase
        self.phase_start = self.sim_time
        self.phase_records.append(
            {"phase": new_phase, "start_sim_time_s": self.sim_time}
        )
        if new_phase == "FINAL_STATIONARY":
            self.final_start_counts = self.counts.copy()

    def elapsed(self) -> float:
        return 0.0 if self.phase_start is None else self.sim_time - self.phase_start

    def baseline_ready(self) -> bool:
        return (
            self.counts["odom"] >= 20
            and self.counts["scan"] >= 20
            and self.counts["image"] >= 5
            and self.counts["info"] >= 1
        )

    def final_ready(self) -> bool:
        if self.final_start_counts is None or self.elapsed() < self.final_duration:
            return False
        return (
            self.counts["odom"] - self.final_start_counts["odom"] >= 20
            and self.counts["scan"] - self.final_start_counts["scan"] >= 20
            and self.counts["image"] - self.final_start_counts["image"] >= 5
        )

    def on_timer(self) -> None:
        if self.sim_time is None or self.done:
            return
        if self.phase == "BASELINE":
            self.publish(0.0, 0.0)
            if self.baseline_ready():
                self.transition("ZERO_BASELINE")
        elif self.phase == "ZERO_BASELINE":
            self.publish(0.0, 0.0)
            if self.elapsed() >= self.zero_duration:
                self.transition("POSITIVE_LINEAR")
        elif self.phase == "POSITIVE_LINEAR":
            self.publish(self.linear_velocity, 0.0)
            if self.elapsed() >= self.linear_duration:
                self.transition("ZERO_AFTER_LINEAR")
        elif self.phase == "ZERO_AFTER_LINEAR":
            self.publish(0.0, 0.0)
            if self.elapsed() >= self.zero_duration:
                self.transition("POSITIVE_ANGULAR")
        elif self.phase == "POSITIVE_ANGULAR":
            self.publish(0.0, self.angular_velocity)
            if self.elapsed() >= self.angular_duration:
                self.transition("ZERO_AFTER_ANGULAR")
        elif self.phase == "ZERO_AFTER_ANGULAR":
            self.publish(0.0, 0.0)
            if self.elapsed() >= self.zero_duration:
                self.transition("FINAL_STATIONARY")
        elif self.phase == "FINAL_STATIONARY":
            self.publish(0.0, 0.0)
            if self.final_ready():
                self.transition("COMPLETE")
                self.publish(0.0, 0.0)
                self.done = True

    def emergency_zero(self) -> None:
        for _ in range(3):
            self.publish(0.0, 0.0)
            time.sleep(0.05)

    def close(self, status: str) -> None:
        if self.phase_records and "end_sim_time_s" not in self.phase_records[-1]:
            self.phase_records[-1]["end_sim_time_s"] = self.sim_time
        result = {
            "status": status,
            "use_sim_time": True,
            "phase_order": [item["phase"] for item in self.phase_records],
            "phase_records": self.phase_records,
            "counts": self.counts,
            "profile": {
                "linear_velocity_mps": self.linear_velocity,
                "linear_duration_s": self.linear_duration,
                "angular_velocity_radps": self.angular_velocity,
                "angular_duration_s": self.angular_duration,
                "zero_settle_duration_s": self.zero_duration,
                "final_stationary_duration_s": self.final_duration,
            },
        }
        self.result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for stream in (
            self.commands,
            self.odometry,
            self.scans,
            self.images,
            self.camera_info,
            self.clocks,
        ):
            stream.close()


def main() -> None:
    log_dir = Path(os.environ["STAGE11CB_LOG_DIR"])
    rclpy.init()
    node = Stage11CBOpenLoopAudit(log_dir)
    interrupted = False

    def request_shutdown(_signum, _frame):
        nonlocal interrupted
        interrupted = True
        node.shutdown_requested = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    try:
        deadline = time.monotonic() + 60.0
        while rclpy.ok() and not node.done and not node.shutdown_requested:
            if time.monotonic() > deadline:
                raise TimeoutError("Stage 11C-B wall-clock timeout")
            rclpy.spin_once(node, timeout_sec=0.05)
        if not node.done:
            raise RuntimeError("Stage 11C-B interrupted before completion")
        node.emergency_zero()
        node.close("PASSED")
    except BaseException:
        try:
            node.emergency_zero()
            node.close("INTERRUPTED" if interrupted else "FAILED")
        finally:
            node.destroy_node()
            rclpy.shutdown()
        raise
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
