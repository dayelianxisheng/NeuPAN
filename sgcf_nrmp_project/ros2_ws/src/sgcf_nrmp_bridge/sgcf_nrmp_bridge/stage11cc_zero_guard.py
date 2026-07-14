"""Independent hard-zero actuator guard for Stage 11C-C."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class ZeroGuard(Node):
    def __init__(self, log_path: Path):
        super().__init__("stage11cc_zero_guard")
        self.publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        self.stream = log_path.open("w", encoding="utf-8", buffering=1)
        self.count = 0
        self.timer = self.create_timer(0.05, self.publish_zero)

    def publish_zero(self) -> None:
        message = Twist()
        self.publisher.publish(message)
        self.count += 1
        self.stream.write(json.dumps({
            "wall_time_ns": time.time_ns(), "publisher": "stage11cc_zero_guard",
            "linear": [0.0, 0.0, 0.0], "angular": [0.0, 0.0, 0.0],
        }, sort_keys=True) + "\n")

    def close(self) -> None:
        for _ in range(3):
            self.publish_zero()
            time.sleep(0.05)
        self.stream.close()


def main() -> None:
    log_path = Path(os.environ["STAGE11CC_ZERO_LOG"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = ZeroGuard(log_path)
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while rclpy.ok() and not stopping:
            rclpy.spin_once(node, timeout_sec=0.05)
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
