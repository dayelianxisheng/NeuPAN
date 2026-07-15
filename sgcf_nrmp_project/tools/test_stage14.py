import json
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_14_external_depot_scene"
OVERLAY = ROOT / "sgcf_nrmp_project/gazebo/overlays/depot/depot_stage14.sdf"


class Stage14Tests(unittest.TestCase):
    def load(self, name):
        return json.loads((OUT / name).read_text())

    def test_vendor_boundary(self):
        manifest = self.load("stage14_vendor_archive_manifest.json")
        license_status = self.load("stage14_license_and_redistribution_status.json")
        self.assertEqual(manifest["dangerous_path_count"], 0)
        self.assertEqual(manifest["symlink_count"], 0)
        self.assertTrue(manifest["cache_read_only"])
        self.assertEqual(license_status["status"], "LICENSE_UNKNOWN_LOCAL_TEST_ONLY")
        self.assertFalse(license_status["redistribution_allowed"])

    def test_overlay_and_spawn(self):
        root = ET.parse(OVERLAY).getroot()
        self.assertEqual(root.get("version"), "1.9")
        text = OVERLAY.read_text()
        self.assertIn("file:///vendor_cache/Depot", text)
        self.assertIn("depot_projection_target", text)
        spawn = self.load("stage14_spawn_and_goal_selection.json")
        self.assertGreaterEqual(len(spawn["candidates"]), 3)
        self.assertFalse(spawn["selected_initial_collision"])

    def test_runtime_sensor_and_projection(self):
        sensor = self.load("stage14_sensor_validation.json")
        projection = self.load("stage14_lidar_rgb_projection.json")
        self.assertTrue(sensor["passed"])
        self.assertEqual(sensor["robot_self_return_count"], 0)
        self.assertGreater(projection["valid_projection_count"], 0)
        self.assertEqual(projection["correct_object_hit_ratio"], 1.0)
        self.assertFalse(projection["world_geometry_used_as_projection_input"])

    def test_command_and_stop(self):
        command = self.load("stage14_cmd_vel_chain.json")
        stop = self.load("stage14_zero_stop.json")
        self.assertTrue(command["passed"])
        self.assertLessEqual(command["maximum_component_error"], 1e-9)
        self.assertGreater(command["positive_x_displacement_m"], 0.0)
        self.assertTrue(stop["passed"])

    def test_cleanup_and_forbidden_components(self):
        cleanup = self.load("stage14_process_cleanup.json")
        self.assertTrue(cleanup["passed"])
        script = (ROOT / "sgcf_nrmp_project/tools/run_stage14_depot.sh").read_text()
        self.assertNotIn("planner", script.lower())
        self.assertNotIn("stage10", script.lower())


if __name__ == "__main__":
    unittest.main()
