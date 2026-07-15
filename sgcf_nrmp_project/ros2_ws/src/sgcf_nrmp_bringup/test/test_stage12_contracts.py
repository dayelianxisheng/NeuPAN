import json
import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts/stages/stage_12_ros2_offline_rosbag"


class Stage12ContractTests(unittest.TestCase):
    def test_four_scene_results_pass(self):
        for scene in ("single_static_obstacle", "vehicle_path", "rgb_dropout_contract", "outdated_rgb_contract"):
            result = json.loads((OUT / "runtime" / scene / "planner_result.json").read_text())
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["self_return_count"], 0)
            self.assertFalse(result["sustained_backlog"])

    def test_failure_fallbacks_are_geometry_equivalent(self):
        for name, reason in (("stage12_dropout_fallback.json", "RGB_DROPOUT"), ("stage12_outdated_fallback.json", "OUTDATED_IMAGE")):
            audit = json.loads((OUT / name).read_text())
            self.assertEqual(audit["fallback_reason"], reason)
            self.assertEqual(max(audit["p2_p0_max_error"].values()), 0.0)
            self.assertEqual(audit["semantic_margin_max"], 0.0)

    def test_replays_are_logically_identical(self):
        first = json.loads((OUT / "rosbag/replay_1.json").read_text())
        second = json.loads((OUT / "rosbag/replay_2.json").read_text())
        self.assertEqual(first, second)

    def test_self_contained_bag_matches_manifest(self):
        manifest = json.loads((OUT / "stage12_rosbag_manifest.json").read_text())
        connection = sqlite3.connect(OUT / "rosbag/stage12_rosbag.sqlite3")
        count = connection.execute("select count(*) from messages").fetchone()[0]
        connection.close()
        self.assertEqual(count, manifest["message_count"])
        for topic in ("/clock", "/scan", "/camera/image_raw", "/camera/camera_info", "/odom", "/tf", "/tf_static", "/sgcf_nrmp/fusion", "/sgcf_nrmp/local_plan", "/diagnostics"):
            self.assertGreater(manifest["counts"][topic], 0)

    def test_no_cmd_vel_publisher_contract(self):
        contract = json.loads((OUT / "stage12_topic_contract.json").read_text())
        self.assertEqual(contract["forbidden_topic"], "/cmd_vel")
        self.assertEqual(contract["cmd_vel_publisher_count"], 0)


if __name__ == "__main__":
    unittest.main()
