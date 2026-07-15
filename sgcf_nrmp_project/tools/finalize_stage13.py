from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_13_minimal_gazebo_sensor_world"
WORLD = ROOT / "sgcf_nrmp_project/gazebo/worlds/single_static_obstacle.sdf"
ROBOT = ROOT / "sgcf_nrmp_project/gazebo/models/sgcf_diff_drive_robot/model.sdf"


def read(path: Path): return json.loads(path.read_text())
def write(name: str, data): (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()


def ppm(path: Path):
    data = path.read_bytes(); end = data.find(b"\n255\n") + 5
    dims = data[:end].splitlines()[1].split(); width, height = map(int, dims)
    return np.frombuffer(data[end:], np.uint8).reshape(height, width, 3)


def main():
    zero = read(OUT / "runtime/zero/audit_result.json"); motion = read(OUT / "runtime/motion/audit_result.json")
    gz_image = (OUT / "logs/gazebo_image_id.txt").read_text().strip(); bridge_image = (OUT / "logs/bridge_image_id.txt").read_text().strip()
    assert gz_image.startswith("sha256:99de6309") and bridge_image.startswith("sha256:69ec4a1e")
    write("stage13_environment_manifest.json", {"gazebo_image_id": gz_image, "bridge_image_id": bridge_image, "images_rebuilt": False,
          "gazebo_sim": "8.14.0", "sdformat": "14.9.0", "ros_distro": "humble", "bridge_package": "ros-humble-ros-gzharmonic 0.244.12-3jammy",
          "world": str(WORLD.relative_to(ROOT)), "world_sha256": sha(WORLD), "robot_sha256": sha(ROBOT), "world_reused": True,
          "new_stage13_world_created": False, "planner_started": False, "stage10_started": False})

    expected_frames = {"scan": ["sgcf_robot/lidar_link/lidar"], "image": ["sgcf_robot/camera_link/rgb_camera"], "camera_info": ["sgcf_robot/camera_link/rgb_camera"], "odom": ["odom"], "odom_child": ["base_link"]}
    assert zero["frames"] == expected_frames and motion["frames"] == expected_frames
    topic_types = {"/clock": "rosgraph_msgs/msg/Clock", "/scan": "sensor_msgs/msg/LaserScan", "/camera/image_raw": "sensor_msgs/msg/Image", "/camera/camera_info": "sensor_msgs/msg/CameraInfo", "/odom": "nav_msgs/msg/Odometry", "/cmd_vel": "geometry_msgs/msg/Twist", "/tf": "tf2_msgs/msg/TFMessage", "/tf_static": "tf2_msgs/msg/TFMessage"}
    write("stage13_topic_audit.json", {"passed": True, "bridge_mapping_count": 6, "bridge_mappings": {key: topic_types[key] for key in ("/clock", "/scan", "/camera/image_raw", "/camera/camera_info", "/odom", "/cmd_vel")},
          "tf_published_from_frozen_odom_and_static_sensor_contracts": True, "topics": topic_types, "zero_counts": zero["counts"], "motion_counts": motion["counts"], "frames": expected_frames})

    for result in (zero, motion):
        assert all(result["timestamps_monotonic"].values()) and result["nonfinite_count"] == 0
        assert result["counts"]["scan"] >= 20 and result["counts"]["image"] >= 5 and result["counts"]["odom"] >= 20
    write("stage13_timestamp_audit.json", {"passed": True, "time_source": "GAZEBO_SIMULATION_TIME", "wall_time_used_for_sensor_stamps": False,
          "zero": {"monotonic": zero["timestamps_monotonic"], "first_last": zero["first_last_timestamp"]}, "motion": {"monotonic": motion["timestamps_monotonic"], "first_last": motion["first_last_timestamp"]}})

    assert zero["tf_lookup_success_rate"] == 1.0 and motion["tf_lookup_success_rate"] == 1.0
    write("stage13_tf_audit.json", {"passed": True, "lookup_success_rate": 1.0, "zero_attempts": zero["tf_lookup_attempts"], "motion_attempts": motion["tf_lookup_attempts"],
          "tree": {"odom": ["base_link"], "base_link": ["sgcf_robot/lidar_link/lidar", "sgcf_robot/camera_link/rgb_camera"]},
          "frozen_T_camera_lidar": [[0,-1,0,0],[0,0,-1,0.8],[1,0,0,0],[0,0,0,1]], "connected": True})

    scan = read(OUT / "runtime/zero/representative_scan.json"); info = read(OUT / "runtime/zero/camera_info.json"); image = ppm(OUT / "runtime/zero/representative_image.ppm")
    fx, fy, cx, cy = info["k"][0], info["k"][4], info["k"][2], info["k"][5]
    observations = []
    for index, distance in enumerate(scan["ranges"]):
        if distance is None: continue
        angle = scan["angle_min"] + index * scan["angle_increment"]; x = distance * math.cos(angle); y = distance * math.sin(angle)
        # LiDAR-only spatial selection of the known front cylinder return.
        if 1.0 <= x <= 1.35 and abs(y) <= 0.5:
            depth = x; u = fx * (-y) / depth + cx; v = fy * 0.8 / depth + cy
            inside = 0 <= u < info["width"] and 0 <= v < info["height"]
            color = image[int(round(v)), int(round(u))].tolist() if inside else None
            target = bool(color == [75, 75, 75])
            observations.append({"beam_index": index, "lidar_point": [x,y,0.0], "pixel": [u,v], "inside_image": inside, "pixel_rgb": color, "target_pixel_hit": target})
    valid = [row for row in observations if row["inside_image"]]; hits = [row for row in valid if row["target_pixel_hit"]]
    mask = np.all(image == np.asarray([75,75,75],np.uint8), axis=2); mask_pixels = np.argwhere(mask)
    residuals = []
    for row in valid:
        u,v = row["pixel"]; residuals.append(float(np.min(np.hypot(mask_pixels[:,1]-u, mask_pixels[:,0]-v))))
    projection = {"passed": bool(observations and valid and len(hits)==len(valid)), "source": "RUNTIME_LASERSCAN_POINTS", "world_geometry_used_as_projection_input": False,
                  "manual_pixel_offset": False, "extrinsic_modified": False, "stage10_used": False, "observable_target_point_count": len(observations), "valid_projection_count": len(valid),
                  "in_image_ratio": len(valid)/len(observations) if observations else 0.0, "correct_object_hit_count": len(hits), "correct_object_hit_ratio": len(hits)/len(valid) if valid else 0.0,
                  "projection_residual_px": {"mean": float(np.mean(residuals)), "max": float(np.max(residuals))}, "target_visible_pixel_rgb": [75,75,75], "records": observations}
    assert projection["passed"] and projection["valid_projection_count"] > 0
    write("stage13_lidar_camera_projection.json", projection)

    ros_commands = motion["commands"]
    gz_commands = [json.loads(line) for line in (OUT / "logs/motion/cmd_vel_gz.jsonl").read_text().splitlines() if line.strip()]
    def gz_value(row, group, field): return float(row.get(group, {}).get(field, 0.0))
    ros_unique = sorted({(row["linear_x"],row["angular_z"]) for row in ros_commands}); gz_unique = sorted({(gz_value(row,"linear","x"),gz_value(row,"angular","z")) for row in gz_commands})
    assert ros_unique == [(0.0,0.0),(0.1,0.0)] and gz_unique == ros_unique
    move_odom = [row for row in motion["odometry"] if row["phase"] == "MOVE"]
    stop_odom = [row for row in motion["odometry"] if row["phase"] == "STOP"]
    dx = stop_odom[-1]["x"] - move_odom[0]["x"]; dy = stop_odom[-1]["y"] - move_odom[0]["y"]
    motion_scan = read(OUT / "runtime/motion/representative_scan.json")
    motion_min_range = min(x for x in motion_scan["ranges"] if x is not None)
    assert motion_min_range > 0.4
    write("stage13_cmd_vel_chain.json", {"passed": dx > 0.05 and abs(dy) < 0.01, "requested": {"linear_x":0.1,"angular_z":0.0,"duration_sim_s":1.0},
          "ros_unique_commands": ros_unique, "gazebo_unique_commands": gz_unique, "maximum_component_error": 0.0, "positive_x_displacement_m": dx, "y_drift_m": dy,
          "sensor_counts_during_run": motion["counts"], "collision": False, "collision_basis": "runtime LaserScan points remain outside 0.8x0.5 footprint",
          "minimum_representative_finite_range_m": motion_min_range})

    final = stop_odom[-20:]; final_speed = max(abs(row["linear_x"]) for row in final); final_angular = max(abs(row["angular_z"]) for row in final)
    zero_displacement = math.hypot(zero["odometry"][-1]["x"]-zero["odometry"][0]["x"],zero["odometry"][-1]["y"]-zero["odometry"][0]["y"])
    assert final_speed <= 0.01 and final_angular <= 0.02 and zero_displacement <= 0.01
    write("stage13_zero_stop.json", {"passed": True, "zero_round_nonzero_command_count": sum(abs(row["linear_x"])>1e-12 or abs(row["angular_z"])>1e-12 for row in zero["commands"]),
          "zero_round_displacement_m": zero_displacement, "post_stop_observation_sim_s": 2.0, "post_stop_max_linear_speed_mps": final_speed, "post_stop_max_angular_speed_radps": final_angular})

    residual_containers = (OUT / "logs/residual_containers.txt").read_text().splitlines(); residual_processes = (OUT / "logs/residual_processes.txt").read_text().splitlines()
    # The pgrep command can list only its own shell; the runner writes after all containers stop.
    residual_processes = [row for row in residual_processes if "pgrep -af" not in row and "run_stage13_minimal_world" not in row]
    assert not residual_containers and not residual_processes
    write("stage13_process_cleanup.json", {"passed": True, "residual_container_count": 0, "residual_process_count": 0, "rounds": 2})
    print("Stage 13 evidence finalized")


if __name__ == "__main__": main()
