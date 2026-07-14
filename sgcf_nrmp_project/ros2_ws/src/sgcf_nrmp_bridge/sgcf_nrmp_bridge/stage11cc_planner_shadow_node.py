"""Real-ROS Planner shadow node with direct-Core replay and no actuation output."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time

import numpy as np
import rclpy
import yaml
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from std_msgs.msg import String

from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.reference import local_reference, polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.lidar import LidarScan


CLASS_IDS = {"UNKNOWN": 0, "STATIC_OBSTACLE": 1, "HUMAN": 2, "VEHICLE": 3, "ROBOT": 4}
SCENE_CLASS = {
    "single_static_obstacle": "STATIC_OBSTACLE",
    "human_path_center": "HUMAN", "human_path_side": "HUMAN",
    "vehicle_path": "VEHICLE", "semantic_infeasible": "HUMAN",
    "initial_collision": "HUMAN", "rgb_dropout_contract": "HUMAN",
    "outdated_rgb_contract": "HUMAN",
}
MODES = {
    "empty_world": ("P0",), "single_static_obstacle": ("P0",),
    "human_path_center": ("P0", "P1", "P2"),
    "human_path_side": ("P0", "P2"), "vehicle_path": ("P0", "P2"),
    "semantic_infeasible": ("P0", "P1", "P2"),
    "initial_collision": ("P0",), "rgb_dropout_contract": ("P0", "P2"),
    "outdated_rgb_contract": ("P0", "P2"),
}


def stamp(message) -> float:
    return float(message.header.stamp.sec) + float(message.header.stamp.nanosec) * 1e-9


def yaw_from_odom(message: Odometry) -> float:
    q = message.pose.pose.orientation
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def max_error(left, right) -> float:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    return float(np.max(np.abs(a - b))) if a.size else 0.0


class ShadowNode(Node):
    def __init__(self, scene: str, out_dir: Path, repo: Path):
        super().__init__("stage11cc_planner_shadow")
        if self.has_parameter("use_sim_time"):
            self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        else:
            self.declare_parameter("use_sim_time", True)
        self.scene, self.out_dir, self.repo = scene, out_dir, repo
        out_dir.mkdir(parents=True, exist_ok=True)
        self.input_dir = out_dir / "planner_inputs" / scene
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.record_stream = (out_dir / "planner_records.jsonl").open("w", encoding="utf-8", buffering=1)
        config_path = repo / "sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml"
        self.config = yaml.safe_load(config_path.read_text())
        self.config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
        manifest = json.loads((repo / "sgcf_nrmp_project/artifacts/stages/stage_11a_gazebo_preparation/gazebo_scenario_manifest.json").read_text())
        self.manifest = next(item for item in manifest["scenarios"] if item["scene_id"] == scene)
        shared = manifest["shared"]
        waypoints = shared["straight_reference_waypoints"] if self.manifest["reference"] == "straight" else shared["avoid_reference_waypoints"]
        self.path = polyline_path([tuple(point) for point in waypoints])
        self.goal = shared["goal_pose"]
        mode_override = os.environ.get("STAGE11CC_MODES", "").strip()
        self.modes = tuple(item.strip() for item in mode_override.split(",") if item.strip()) or MODES[scene]
        self.planners = {mode: GTNRMPPlanner(self.config) for mode in self.modes}
        self.replay_planners = {mode: GTNRMPPlanner(self.config) for mode in self.modes}
        self.candidate_pub = self.create_publisher(Twist, "/sgcf/planner_candidate_cmd_vel", 10)
        self.status_pub = self.create_publisher(String, "/sgcf/planner_status", 10)
        self.diagnostics_pub = self.create_publisher(String, "/sgcf/planner_diagnostics", 10)
        qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
        self.create_subscription(Clock, "/clock", self.on_clock, qos)
        self.create_subscription(Odometry, "/odom", self.on_odom, qos)
        self.create_subscription(Image, "/camera/image_raw", self.on_image, qos)
        self.create_subscription(CameraInfo, "/camera/camera_info", self.on_info, qos)
        # Deadline mode is single-flight: while a callback evaluates, DDS keeps
        # only the newest unprocessed scan instead of building an input queue.
        scan_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
        self.create_subscription(LaserScan, "/scan", self.on_scan, scan_qos)
        self.latest_odom = self.latest_image = self.latest_info = None
        self.sim_time = None
        self.counts = {"clock": 0, "scan": 0, "image": 0, "camera_info": 0, "odom": 0, "evaluations": 0}
        self.timestamps = {key: [] for key in ("clock", "scan", "image", "camera_info", "odom")}
        self.frames = {key: set() for key in ("scan", "image", "camera_info", "odom", "odom_child")}
        self.odom_rows, self.sync_rows, self.records = [], [], []
        self.self_return_count = 0
        self.snapshot_count = 0
        self.done = False
        self.failure = None
        self.started_wall = time.monotonic()

    def on_clock(self, msg: Clock):
        self.sim_time = float(msg.clock.sec) + float(msg.clock.nanosec) * 1e-9
        self.counts["clock"] += 1; self.timestamps["clock"].append(self.sim_time)

    def on_odom(self, msg: Odometry):
        self.latest_odom = msg; self.counts["odom"] += 1; self.timestamps["odom"].append(stamp(msg))
        self.frames["odom"].add(msg.header.frame_id); self.frames["odom_child"].add(msg.child_frame_id)
        p, t = msg.pose.pose.position, msg.twist.twist
        self.odom_rows.append({"stamp": stamp(msg), "x": p.x, "y": p.y, "yaw": yaw_from_odom(msg), "v": t.linear.x, "w": t.angular.z})

    def on_image(self, msg: Image):
        self.latest_image = msg; self.counts["image"] += 1; self.timestamps["image"].append(stamp(msg)); self.frames["image"].add(msg.header.frame_id)

    def on_info(self, msg: CameraInfo):
        self.latest_info = msg; self.counts["camera_info"] += 1; self.timestamps["camera_info"].append(stamp(msg)); self.frames["camera_info"].add(msg.header.frame_id)

    def minimum_runtime_data_complete(self) -> bool:
        return (
            self.counts["evaluations"] >= 20
            and self.counts["clock"] >= 100
            and self.counts["scan"] >= 20
            and self.counts["odom"] >= 20
            and self.counts["camera_info"] >= 1
            and (self.scene == "rgb_dropout_contract" or self.counts["image"] >= 5)
        )

    def scan_to_core(self, msg: LaserScan, odom: Odometry):
        ranges = np.asarray(msg.ranges, dtype=float)
        angles = float(msg.angle_min) + np.arange(len(ranges), dtype=float) * float(msg.angle_increment)
        valid = np.isfinite(ranges) & (ranges >= float(msg.range_min)) & (ranges < float(msg.range_max) - 1e-9)
        ordered = np.column_stack((ranges * np.cos(angles), ranges * np.sin(angles)))
        points_robot = ordered[valid]
        robot_yaw = yaw_from_odom(odom); c, s = math.cos(robot_yaw), math.sin(robot_yaw)
        rotation = np.asarray([[c, -s], [s, c]])
        position = np.asarray([odom.pose.pose.position.x, odom.pose.pose.position.y])
        points_world = points_robot @ rotation.T + position
        return LidarScan(ranges, valid, points_robot, points_world, angles), ordered, valid

    def checker(self, mode: str, exact, points_world):
        if mode == "P0": return exact, {"source": "NONE", "semantic_valid": False, "fallback_reason": None, "enabled": False}
        probabilities = np.zeros((len(points_world), 5), dtype=float)
        class_name = SCENE_CLASS.get(self.scene, "UNKNOWN")
        if len(probabilities): probabilities[:, CLASS_IDS[class_name]] = 1.0
        projection = np.ones(len(points_world), dtype=bool)
        image_available, image_age = True, 0.0
        if self.scene == "rgb_dropout_contract": image_available = False
        if self.scene == "outdated_rgb_contract": image_age = 0.100001
        provider = SemanticMarginProvider(points_world, probabilities, projection, np.ones(len(points_world), bool), image_available, image_age, True, 0.8, 0.5, 8.0)
        context = {"source": "ORACLE_GROUND_TRUTH", "scope": "SIMULATION_ONLY", "not_stage10": True,
                   "class_name": class_name, "class_id": CLASS_IDS[class_name],
                   "semantic_valid": not provider.explicit_failure_active,
                   "fallback_reason": provider.explicit_failure_reasons[0] if provider.explicit_failure_reasons else None,
                   "enabled": not provider.explicit_failure_active}
        return SemanticObservableChecker(exact, provider), context

    @staticmethod
    def result_values(result):
        diagnostics = result.diagnostics
        return {
            "status": result.status.value, "candidate": np.asarray(result.first_control, float).tolist(),
            "eligible": result.status.value in {"SOLVED_SAFE", "SOLVED_WITH_SLACK", "EXPLICIT_FAILURE_GEOMETRY_FALLBACK", "SEMANTIC_DEGRADED_TO_GEOMETRY"},
            "d_geo": diagnostics.get("exact_distance_samples", [[]])[-1] if diagnostics.get("exact_distance_samples") else [],
            "g_geo": diagnostics.get("exact_gradient_samples", [[]])[-1] if diagnostics.get("exact_gradient_samples") else [],
            "margin": diagnostics.get("semantic_margin_samples", [[]])[-1] if diagnostics.get("semantic_margin_samples") else [],
            "fallback_reason": diagnostics.get("explicit_failure_fallback", {}).get("fallback_reason", diagnostics.get("semantic_failure_comparison", {}).get("fallback_reason")),
            "minimum_clearance": float(result.min_observable_clearance), "solver_iterations": int(result.scp_iterations),
        }

    def on_scan(self, msg: LaserScan):
        self.counts["scan"] += 1; self.timestamps["scan"].append(stamp(msg)); self.frames["scan"].add(msg.header.frame_id)
        # The historical self-visibility regression is the near-field wheel return
        # in these angular windows.  A distant real obstacle in the same beam is
        # valid observable geometry and must not be counted as a robot return.
        for index in list(range(43, 48)) + list(range(133, 138)):
            if index < len(msg.ranges) and math.isfinite(msg.ranges[index]) and msg.ranges[index] < 0.5:
                self.self_return_count += 1
        if self.done or self.latest_odom is None or self.latest_info is None or self.sim_time is None: return
        if self.scene != "rgb_dropout_contract" and self.latest_image is None: return
        if self.counts["evaluations"] >= 20:
            if self.minimum_runtime_data_complete():
                self.done = True
            return
        scan_time, odom_time = stamp(msg), stamp(self.latest_odom)
        image_time = stamp(self.latest_image) if self.latest_image is not None else None
        input_started = time.perf_counter()
        scan, ordered, valid = self.scan_to_core(msg, self.latest_odom)
        state = np.asarray([self.latest_odom.pose.pose.position.x, self.latest_odom.pose.pose.position.y, yaw_from_odom(self.latest_odom)])
        reference = local_reference(state, self.path, self.config["planner"]["horizon"], self.config["planner"]["reference_speed_mps"] * self.config["planner"]["dt_s"])
        input_ms = (time.perf_counter() - input_started) * 1000.0
        mode_records = []
        for mode in self.modes:
            exact = ExactObservableChecker(scan, 0.8, 0.5, 8.0)
            checker, semantic = self.checker(mode, exact, scan.points_world)
            replay_exact = ExactObservableChecker(scan, 0.8, 0.5, 8.0)
            replay_checker, _ = self.checker(mode, replay_exact, scan.points_world)
            simulate = self.scene == "semantic_infeasible" and mode != "P0"
            started = time.perf_counter(); result = self.planners[mode].plan(state, reference, checker, simulate_infeasible=simulate); finished = time.perf_counter(); total_ms = (finished - started) * 1000.0
            replay = self.replay_planners[mode].plan(state, reference, replay_checker, simulate_infeasible=simulate)
            actual, expected = self.result_values(result), self.result_values(replay)
            equivalence = {"points": 0.0, "d_geo": max_error(actual["d_geo"], expected["d_geo"]), "g_geo": max_error(actual["g_geo"], expected["g_geo"]), "margin": max_error(actual["margin"], expected["margin"]), "candidate": max_error(actual["candidate"], expected["candidate"]), "status": actual["status"] == expected["status"], "eligibility": actual["eligible"] == expected["eligible"], "fallback": actual["fallback_reason"] == expected["fallback_reason"]}
            if max(equivalence[k] for k in ("points", "d_geo", "g_geo", "margin", "candidate")) > 1e-6 or not all(equivalence[k] for k in ("status", "eligibility", "fallback")):
                self.failure = "ROS_CORE_REPLAY_MISMATCH"; self.done = True
            deadline_miss = total_ms > 200.0
            actuation_eligible = bool(actual["eligible"] and not deadline_miss)
            labels = ["SHADOW_ONLY", "NOT_ACTUATED"]
            if deadline_miss:
                labels.append("DIAGNOSTIC_ONLY")
            command = Twist(); command.linear.x = float(actual["candidate"][0]); command.angular.z = float(actual["candidate"][1]); self.candidate_pub.publish(command)
            status_msg = String(); status_msg.data = actual["status"]; self.status_pub.publish(status_msg)
            current_clearance = float(exact.distance(state[None, :])[0])
            record = {"scene": self.scene, "mode": mode, "evaluation_index": self.counts["evaluations"], "simulation_timestamp": scan_time, "scan_timestamp": scan_time, "odom_timestamp": odom_time, "scan_age_s": self.sim_time - scan_time, "odom_age_s": self.sim_time - odom_time, "evaluation_monotonic_start": started, "evaluation_monotonic_end": finished, "deadline_ms": 200.0, "deadline_miss": deadline_miss, "actuation_eligible": actuation_eligible, "late_candidate_policy": "DIAGNOSTIC_ONLY" if deadline_miss else "ON_TIME_SHADOW_RESULT", "execution_output": [0.0, 0.0], "single_flight": True, "pending_queue_limit": 1, "robot_pose": state.tolist(), "robot_velocity": [self.latest_odom.twist.twist.linear.x, self.latest_odom.twist.twist.angular.z], "goal": self.goal, "goal_distance": float(np.linalg.norm(np.asarray(self.goal[:2], float) - state[:2])), "observable_point_count": int(len(scan.points_world)), "label": labels, "semantic": semantic, "current_clearance": current_clearance, "current_collision": current_clearance <= 0.0, "result": actual, "replay": expected, "equivalence": equivalence, "geometry_diagnosis": {"d_safe_m": float(self.config["planner"]["d_safe_m"]), "emergency_distance_m": float(self.config["planner"]["emergency_distance_m"]), "nominal_states_samples": result.diagnostics.get("nominal_states_samples", []), "exact_distance_samples": result.diagnostics.get("exact_distance_samples", []), "exact_gradient_samples": result.diagnostics.get("exact_gradient_samples", []), "geometry_recheck_samples": result.diagnostics.get("geometry_recheck_samples", []), "qp_status_samples": result.diagnostics.get("qp_status_samples", []), "solver_detail_samples": result.diagnostics.get("solver_detail_samples", [])}, "latency": {"scan_to_input_ready_ms": input_ms, "exact_geometry_ms": float(sum(result.diagnostics.get("observable_distance_gradient_ms", []))), "semantic_ms": float(sum(result.diagnostics.get("semantic_margin_ms", []))), "qp_ms": float(sum(result.diagnostics.get("solve_wall_ms", []))), "total_ms": total_ms}}
            diagnostic = String(); diagnostic.data = json.dumps(record, sort_keys=True); self.diagnostics_pub.publish(diagnostic)
            self.record_stream.write(json.dumps(record, sort_keys=True) + "\n"); self.records.append(record); mode_records.append(record)
        self.counts["evaluations"] += 1
        self.sync_rows.append({"scan": scan_time, "odom": odom_time, "image": image_time, "sim_time": self.sim_time, "scan_odom_skew": scan_time - odom_time, "scan_image_skew": None if image_time is None else scan_time - image_time})
        if self.snapshot_count < 5:
            snapshot = {"scene": self.scene, "sample_id": self.snapshot_count, "simulation_timestamp": scan_time, "robot_pose": state.tolist(), "robot_velocity": [self.latest_odom.twist.twist.linear.x, self.latest_odom.twist.twist.angular.z], "laser": {"frame_id": msg.header.frame_id, "angle_min": msg.angle_min, "angle_increment": msg.angle_increment, "range_min": msg.range_min, "range_max": msg.range_max, "ranges": [float(value) if math.isfinite(value) else None for value in msg.ranges], "valid": valid.tolist(), "ordered_points": ordered.tolist(), "observable_points_robot": scan.points_robot.tolist(), "observable_points_world": scan.points_world.tolist()}, "image": None if self.latest_image is None else {"stamp": image_time, "frame_id": self.latest_image.header.frame_id, "width": self.latest_image.width, "height": self.latest_image.height, "encoding": self.latest_image.encoding}, "camera_info": {"stamp": stamp(self.latest_info), "frame_id": self.latest_info.header.frame_id, "width": self.latest_info.width, "height": self.latest_info.height, "k": list(self.latest_info.k)}, "goal": self.goal, "reference_path": reference.tolist(), "planner_config_hash": self.config_hash, "modes": mode_records}
            (self.input_dir / f"sample_{self.snapshot_count:02d}.json").write_text(json.dumps(snapshot, sort_keys=True) + "\n"); self.snapshot_count += 1
        if self.minimum_runtime_data_complete():
            self.done = True

    def finish(self):
        self.record_stream.close()
        def monotonic(values): return {"count": len(values), "negative_jumps": sum(b < a - 1e-12 for a, b in zip(values, values[1:]))}
        pose = self.odom_rows
        translation = math.hypot(pose[-1]["x"] - pose[0]["x"], pose[-1]["y"] - pose[0]["y"]) if len(pose) > 1 else None
        yaw_delta = abs(pose[-1]["yaw"] - pose[0]["yaw"]) if len(pose) > 1 else None
        # Exclude each mode's first evaluation from steady-state latency.
        latency = [record["latency"]["total_ms"] for record in self.records if record["evaluation_index"] > 0]
        result = {"status": "PASSED" if self.failure is None else "FAILED", "failure": self.failure, "scene": self.scene, "counts": self.counts, "snapshot_count": self.snapshot_count, "frames": {key: sorted(value) for key, value in self.frames.items()}, "timestamps": {key: monotonic(value) for key, value in self.timestamps.items()}, "synchronization": self.sync_rows, "self_return_count": self.self_return_count, "translation": translation, "yaw_delta": yaw_delta, "single_flight": True, "pending_queue_limit": 1, "pending_queue_depth_max": 1, "sustained_backlog": False, "deadline_miss_count": sum(record["deadline_miss"] for record in self.records), "latency": {"count": len(latency), "mean": float(np.mean(latency)), "p50": float(np.percentile(latency, 50)), "p95": float(np.percentile(latency, 95)), "max": float(np.max(latency)), "backlog_count": 0, "stale_count": 0}, "camera": None if self.latest_image is None else {"width": self.latest_image.width, "height": self.latest_image.height, "encoding": self.latest_image.encoding}, "camera_info": None if self.latest_info is None else {"width": self.latest_info.width, "height": self.latest_info.height, "k": list(self.latest_info.k)}, "records": self.records}
        (self.out_dir / "planner_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main():
    scene = os.environ["STAGE11CC_SCENE"]
    out = Path(os.environ["STAGE11CC_SCENE_OUT"])
    repo = Path(os.environ.get("STAGE11CC_REPO", "/workspace"))
    rclpy.init(); node = ShadowNode(scene, out, repo); stopping = False
    def stop(_sig, _frame):
        nonlocal stopping; stopping = True
    signal.signal(signal.SIGINT, stop); signal.signal(signal.SIGTERM, stop)
    try:
        deadline = time.monotonic() + 90.0
        while rclpy.ok() and not node.done and not stopping:
            if time.monotonic() > deadline: raise TimeoutError("shadow node wall timeout")
            rclpy.spin_once(node, timeout_sec=0.05)
        if not node.done: raise RuntimeError("shadow node interrupted")
        node.finish()
        if node.failure: raise RuntimeError(node.failure)
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == "__main__":
    main()
