import json
import unittest
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "artifacts/stages/stage_13_minimal_gazebo_sensor_world"


class Stage13Tests(unittest.TestCase):
    def load(self, name): return json.loads((OUT / name).read_text())

    def test_topics_and_timestamps(self):
        self.assertTrue(self.load("stage13_topic_audit.json")["passed"])
        self.assertTrue(self.load("stage13_timestamp_audit.json")["passed"])

    def test_tf_and_projection(self):
        self.assertEqual(self.load("stage13_tf_audit.json")["lookup_success_rate"], 1.0)
        projection = self.load("stage13_lidar_camera_projection.json")
        self.assertGreater(projection["valid_projection_count"], 0)
        self.assertEqual(projection["correct_object_hit_ratio"], 1.0)
        self.assertFalse(projection["world_geometry_used_as_projection_input"])

    def test_command_and_stop(self):
        command = self.load("stage13_cmd_vel_chain.json")
        self.assertEqual(command["maximum_component_error"], 0.0)
        self.assertGreater(command["positive_x_displacement_m"], 0.05)
        self.assertLess(abs(command["y_drift_m"]), 0.01)
        self.assertFalse(command["collision"])
        self.assertTrue(self.load("stage13_zero_stop.json")["passed"])

    def test_safety_boundaries(self):
        environment = self.load("stage13_environment_manifest.json")
        self.assertFalse(environment["images_rebuilt"])
        self.assertFalse(environment["planner_started"])
        self.assertFalse(environment["stage10_started"])
        for mode in ("zero", "motion"):
            runtime = json.loads((OUT / "runtime" / mode / "audit_result.json").read_text())
            self.assertEqual(runtime["self_return_count"], 0)
            self.assertEqual(runtime["nonfinite_count"], 0)

    def test_cleanup(self):
        self.assertTrue(self.load("stage13_process_cleanup.json")["passed"])


if __name__ == "__main__": unittest.main()
