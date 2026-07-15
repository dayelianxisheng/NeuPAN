"""Stage 13 ROS sensor / TF / low-speed command audit (no Planner)."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from tf2_ros import Buffer, StaticTransformBroadcaster, TransformBroadcaster, TransformListener


def stamp(message) -> float:
    return float(message.header.stamp.sec) + float(message.header.stamp.nanosec) * 1e-9


class Stage13Audit(Node):
    def __init__(self) -> None:
        super().__init__("stage13_sensor_command_audit")
        self.mode = os.environ["STAGE13_MODE"]
        self.out = Path(os.environ["STAGE13_OUT"])
        self.out.mkdir(parents=True, exist_ok=True)
        self.clock = None
        self.phase = "WAIT_SENSORS"
        self.phase_start = None
        self.done = False
        self.counts = {"clock": 0, "scan": 0, "image": 0, "camera_info": 0, "odom": 0}
        self.timestamps = {key: [] for key in self.counts}
        self.frames = {"scan": set(), "image": set(), "camera_info": set(), "odom": set(), "odom_child": set()}
        self.commands = []
        self.odom = []
        self.nonfinite_count = 0
        self.self_return_count = 0
        self.tf_attempts = 0
        self.tf_successes = 0
        self.latest_scan = None
        self.latest_image = None
        self.latest_info = None
        sensor_qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
        self.cmd = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Clock, "/clock", self.on_clock, sensor_qos)
        self.create_subscription(LaserScan, "/scan", self.on_scan, sensor_qos)
        self.create_subscription(Image, "/camera/image_raw", self.on_image, sensor_qos)
        self.create_subscription(CameraInfo, "/camera/camera_info", self.on_info, sensor_qos)
        self.create_subscription(Odometry, "/odom", self.on_odom, sensor_qos)
        self.static_tf = StaticTransformBroadcaster(self)
        self.dynamic_tf = TransformBroadcaster(self)
        self.buffer = Buffer(cache_time=Duration(seconds=10.0))
        self.listener = TransformListener(self.buffer, self, spin_thread=False)
        self.publish_static_tf()
        self.timer = self.create_timer(0.02, self.tick)

    def publish_static_tf(self) -> None:
        lidar = TransformStamped(); lidar.header.frame_id = "base_link"; lidar.child_frame_id = "sgcf_robot/lidar_link/lidar"; lidar.transform.translation.z = 0.1; lidar.transform.rotation.w = 1.0
        camera = TransformStamped(); camera.header.frame_id = "base_link"; camera.child_frame_id = "sgcf_robot/camera_link/rgb_camera"; camera.transform.translation.z = 0.9
        camera.transform.rotation.x = -0.5; camera.transform.rotation.y = 0.5; camera.transform.rotation.z = -0.5; camera.transform.rotation.w = 0.5
        self.static_tf.sendTransform([lidar, camera])

    def on_clock(self, message: Clock) -> None:
        self.clock = float(message.clock.sec) + float(message.clock.nanosec) * 1e-9
        self.counts["clock"] += 1; self.timestamps["clock"].append(self.clock)

    def on_scan(self, message: LaserScan) -> None:
        self.counts["scan"] += 1; self.timestamps["scan"].append(stamp(message)); self.frames["scan"].add(message.header.frame_id); self.latest_scan = message
        for index, value in enumerate(message.ranges):
            if math.isfinite(value):
                angle = message.angle_min + index * message.angle_increment
                x, y = value * math.cos(angle), value * math.sin(angle)
                if -0.4 <= x <= 0.4 and -0.25 <= y <= 0.25:
                    self.self_return_count += 1

    def on_image(self, message: Image) -> None:
        self.counts["image"] += 1; self.timestamps["image"].append(stamp(message)); self.frames["image"].add(message.header.frame_id); self.latest_image = message

    def on_info(self, message: CameraInfo) -> None:
        self.counts["camera_info"] += 1; self.timestamps["camera_info"].append(stamp(message)); self.frames["camera_info"].add(message.header.frame_id); self.latest_info = message

    def on_odom(self, message: Odometry) -> None:
        self.counts["odom"] += 1; self.timestamps["odom"].append(stamp(message)); self.frames["odom"].add(message.header.frame_id); self.frames["odom_child"].add(message.child_frame_id)
        pose, twist = message.pose.pose, message.twist.twist
        values = [pose.position.x, pose.position.y, pose.position.z, twist.linear.x, twist.linear.y, twist.angular.z]
        self.nonfinite_count += sum(not math.isfinite(value) for value in values)
        self.odom.append({"stamp": stamp(message), "sim_time": self.clock, "phase": self.phase, "x": pose.position.x, "y": pose.position.y, "z": pose.position.z, "linear_x": twist.linear.x, "linear_y": twist.linear.y, "angular_z": twist.angular.z})
        transform = TransformStamped(); transform.header = message.header; transform.header.frame_id = "odom"; transform.child_frame_id = "base_link"; transform.transform.translation.x = pose.position.x; transform.transform.translation.y = pose.position.y; transform.transform.translation.z = pose.position.z; transform.transform.rotation = pose.orientation
        self.dynamic_tf.sendTransform(transform)

    def ready(self) -> bool:
        return self.counts["scan"] >= 20 and self.counts["image"] >= 5 and self.counts["camera_info"] >= 1 and self.counts["odom"] >= 20

    def set_phase(self, value: str) -> None:
        self.phase = value; self.phase_start = self.clock

    def elapsed(self) -> float:
        return 0.0 if self.clock is None or self.phase_start is None else self.clock - self.phase_start

    def publish_command(self, linear_x: float) -> None:
        message = Twist(); message.linear.x = linear_x; self.cmd.publish(message)
        self.commands.append({"sim_time": self.clock, "phase": self.phase, "linear_x": linear_x, "angular_z": 0.0})

    def tick(self) -> None:
        if self.clock is None or self.done:
            return
        self.publish_command(0.0 if self.phase != "MOVE" else 0.10)
        self.tf_attempts += 1
        try:
            self.buffer.lookup_transform("sgcf_robot/camera_link/rgb_camera", "sgcf_robot/lidar_link/lidar", Time())
            self.tf_successes += 1
        except Exception:
            pass
        if self.phase == "WAIT_SENSORS" and self.ready():
            self.set_phase("ZERO_OBSERVE" if self.mode == "zero" else "BASELINE")
        elif self.mode == "zero" and self.phase == "ZERO_OBSERVE" and self.elapsed() >= 5.0:
            self.set_phase("COMPLETE"); self.done = True
        elif self.mode == "motion" and self.phase == "BASELINE" and self.elapsed() >= 0.5:
            self.set_phase("MOVE")
        elif self.mode == "motion" and self.phase == "MOVE" and self.elapsed() >= 1.0:
            self.set_phase("STOP")
        elif self.mode == "motion" and self.phase == "STOP" and self.elapsed() >= 2.0:
            self.set_phase("COMPLETE"); self.done = True

    def save(self) -> None:
        for _ in range(3): self.publish_command(0.0); time.sleep(0.03)
        if self.latest_scan is not None:
            scan = self.latest_scan
            (self.out / "representative_scan.json").write_text(json.dumps({"stamp": stamp(scan), "frame_id": scan.header.frame_id, "angle_min": scan.angle_min, "angle_max": scan.angle_max, "angle_increment": scan.angle_increment, "range_min": scan.range_min, "range_max": scan.range_max, "ranges": [value if math.isfinite(value) else None for value in scan.ranges]}, indent=2) + "\n")
        if self.latest_image is not None:
            image = self.latest_image
            (self.out / "representative_image.ppm").write_bytes(f"P6\n{image.width} {image.height}\n255\n".encode() + bytes(image.data))
        if self.latest_info is not None:
            info = self.latest_info
            (self.out / "camera_info.json").write_text(json.dumps({"stamp": stamp(info), "frame_id": info.header.frame_id, "width": info.width, "height": info.height, "k": list(info.k), "p": list(info.p)}, indent=2) + "\n")
        def monotonic(values): return sum(b < a - 1e-12 for a, b in zip(values, values[1:])) == 0
        result = {"mode": self.mode, "counts": self.counts, "frames": {key: sorted(value) for key, value in self.frames.items()}, "timestamps_monotonic": {key: monotonic(value) for key, value in self.timestamps.items()}, "first_last_timestamp": {key: [value[0], value[-1]] if value else None for key, value in self.timestamps.items()}, "commands": self.commands, "odometry": self.odom, "nonfinite_count": self.nonfinite_count, "self_return_count": self.self_return_count, "tf_lookup_attempts": self.tf_attempts, "tf_lookup_successes": self.tf_successes, "tf_lookup_success_rate": self.tf_successes / self.tf_attempts if self.tf_attempts else 0.0, "use_sim_time": True, "planner_started": False, "stage10_started": False}
        (self.out / "audit_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main() -> None:
    rclpy.init(); node = Stage13Audit(); deadline = time.monotonic() + 90.0
    try:
        while rclpy.ok() and not node.done:
            if time.monotonic() > deadline: raise TimeoutError("Stage 13 audit timeout")
            rclpy.spin_once(node, timeout_sec=0.05)
        node.save()
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == "__main__":
    main()
