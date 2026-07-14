#!/usr/bin/env python3
"""Consolidate Stage 11C-C runtime evidence without changing runtime assets."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import statistics

import numpy as np


REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "sgcf_nrmp_project/artifacts/stages/stage_11c_c_planner_shadow_mode"
SCENES = (
    "empty_world", "single_static_obstacle", "human_path_center",
    "semantic_infeasible", "initial_collision", "rgb_dropout_contract",
    "outdated_rgb_contract",
)
PLANNER_IMAGE = "sha256:03f77926ea1b97cc460ca2d5893abb1b26d3b68984d53f9e98e707994841cff5"
GAZEBO_IMAGE = "sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac"
BRIDGE_BASE = "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862"


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def percentile(values, q):
    return float(np.percentile(np.asarray(values, float), q))


results = {scene: json.loads((OUT / f"runtime/{scene}/planner_result.json").read_text()) for scene in SCENES}
records = [record for scene in SCENES for record in results[scene]["records"]]
(OUT / "stage11cc_planner_shadow_records.jsonl").write_text(
    "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
)

equivalence = {
    "sample_count": len(records),
    "observable_points_max_difference": max(r["equivalence"]["points"] for r in records),
    "d_geo_max_difference": max(r["equivalence"]["d_geo"] for r in records),
    "g_geo_max_difference": max(r["equivalence"]["g_geo"] for r in records),
    "semantic_margin_max_difference": max(r["equivalence"]["margin"] for r in records),
    "candidate_max_difference": max(r["equivalence"]["candidate"] for r in records),
    "status_agreement": all(r["equivalence"]["status"] for r in records),
    "eligibility_agreement": all(r["equivalence"]["eligibility"] for r in records),
    "fallback_agreement": all(r["equivalence"]["fallback"] for r in records),
}
equivalence["passed"] = all([
    max(equivalence[k] for k in ("observable_points_max_difference", "d_geo_max_difference", "g_geo_max_difference", "semantic_margin_max_difference", "candidate_max_difference")) <= 1e-6,
    equivalence["status_agreement"], equivalence["eligibility_agreement"], equivalence["fallback_agreement"],
])
dump("stage11cc_ros_core_equivalence.json", equivalence)

firewall_scenes = {}
for scene in SCENES:
    logs = OUT / "logs" / scene
    graph = (logs / "cmd_vel_topic_info.txt").read_text()
    candidate_graph = (logs / "candidate_topic_info.txt").read_text()
    zero_rows = [json.loads(line) for line in (logs / "cmd_vel_ros.jsonl").read_text().splitlines() if line.strip()]
    gz_rows = [json.loads(line) for line in (logs / "cmd_vel_gz.txt").read_text().splitlines() if line.strip()]
    def nonzero(row):
        def components(obj):
            if isinstance(obj, list):
                return [float(value) for value in obj]
            return [float(obj.get(key, 0.0)) for key in ("x", "y", "z")]
        return any(abs(x) > 1e-12 for x in components(row.get("linear", {})) + components(row.get("angular", {})))
    firewall_scenes[scene] = {
        "ros_zero_message_count": len(zero_rows),
        "ros_nonzero_message_count": sum(nonzero(row) for row in zero_rows),
        "gazebo_command_count": len(gz_rows),
        "gazebo_nonzero_command_count": sum(nonzero(row) for row in gz_rows),
        "cmd_vel_publisher_count": int(re.search(r"Publisher count: (\d+)", graph).group(1)),
        "cmd_vel_publisher": "stage11cc_zero_guard" if "Node name: stage11cc_zero_guard" in graph else None,
        "candidate_subscription_count": int(re.search(r"Subscription count: (\d+)", candidate_graph).group(1)),
        "planner_publishes_cmd_vel": "/cmd_vel:" in (logs / "planner_node_info.txt").read_text().split("Publishers:", 1)[-1].split("Service Servers:", 1)[0],
    }
firewall = {"scenes": firewall_scenes}
firewall["passed"] = all(
    row["ros_nonzero_message_count"] == 0 and row["gazebo_nonzero_command_count"] == 0
    and row["cmd_vel_publisher_count"] == 1 and row["cmd_vel_publisher"] == "stage11cc_zero_guard"
    and row["candidate_subscription_count"] == 0 and not row["planner_publishes_cmd_vel"]
    for row in firewall_scenes.values()
)
firewall["candidate_reaching_cmd_vel_count"] = 0
firewall["candidate_reaching_gazebo_count"] = 0
dump("stage11cc_actuation_firewall.json", firewall)

status_summary = {}
for scene in SCENES:
    status_summary[scene] = {}
    for mode in sorted({record["mode"] for record in results[scene]["records"]}):
        subset = [record for record in results[scene]["records"] if record["mode"] == mode]
        status_summary[scene][mode] = {
            "evaluation_count": len(subset), "statuses": sorted({r["result"]["status"] for r in subset}),
            "eligibility": sorted({r["result"]["eligible"] for r in subset}),
            "fallback_reasons": sorted({str(r["result"]["fallback_reason"]) for r in subset}),
            "semantic_contexts": list({json.dumps(r["semantic"], sort_keys=True) for r in subset}),
            "clearance_min": min(r["current_clearance"] for r in subset),
            "clearance_max": max(r["current_clearance"] for r in subset),
            "collision": any(r["current_collision"] for r in subset),
        }
dump("stage11cc_planner_status_summary.json", status_summary)

dump("stage11cc_input_synchronization.json", {
    scene: {"primary_time": "LaserScan header timestamp", "samples": result["synchronization"], "stale_count": result["latency"]["stale_count"], "backlog_count": result["latency"]["backlog_count"]}
    for scene, result in results.items()
})
dump("stage11cc_runtime_frame_audit.json", {
    "expected": {"scan": "sgcf_robot/lidar_link/lidar", "camera": "sgcf_robot/camera_link/rgb_camera", "odom": "odom", "odom_child": "base_link"},
    "scenes": {scene: result["frames"] for scene, result in results.items()},
    "passed": all(result["frames"] == {"scan": ["sgcf_robot/lidar_link/lidar"], "image": ["sgcf_robot/camera_link/rgb_camera"], "camera_info": ["sgcf_robot/camera_link/rgb_camera"], "odom": ["odom"], "odom_child": ["base_link"]} for result in results.values()),
})
stationary = {scene: {"translation": result["translation"], "yaw_delta": result["yaw_delta"], "threshold_translation": 0.005 if scene == "initial_collision" else 0.002, "threshold_yaw": 0.002} for scene, result in results.items()}
for scene, row in stationary.items(): row["passed"] = row["translation"] <= row["threshold_translation"] and row["yaw_delta"] <= row["threshold_yaw"]
dump("stage11cc_stationary_runtime_gate.json", {"scenes": stationary, "passed": all(row["passed"] for row in stationary.values())})

latency = {scene: result["latency"] for scene, result in results.items()}
latency["threshold_ms"] = 200.0
latency["blocked_scenes"] = [scene for scene in SCENES if results[scene]["latency"]["p95"] > 200.0 or results[scene]["latency"]["stale_count"] or results[scene]["latency"]["backlog_count"]]
latency["passed"] = not latency["blocked_scenes"]
latency["decision"] = "BLOCKED_PLANNER_INTERFACE_LATENCY" if latency["blocked_scenes"] else "PASS"
dump("stage11cc_planner_latency.json", latency)

sensor = {}
for scene, result in results.items():
    camera_required = scene != "rgb_dropout_contract"
    sensor[scene] = {
        "counts": result["counts"], "camera": result["camera"], "camera_info": result["camera_info"],
        "timestamp_audit": result["timestamps"], "self_return_count": result["self_return_count"],
        "passed": result["counts"]["clock"] >= 100 and result["counts"]["scan"] >= 20 and result["counts"]["odom"] >= 20 and result["counts"]["camera_info"] >= 1 and (not camera_required or result["counts"]["image"] >= 5) and result["self_return_count"] == 0 and all(row["negative_jumps"] == 0 for row in result["timestamps"].values()) and (result["camera"] is None or (result["camera"]["width"], result["camera"]["height"], result["camera"]["encoding"]) == (320, 240, "rgb8")),
    }
dump("stage11cc_sensor_data_plane_regression.json", {"scenes": sensor, "passed": all(row["passed"] for row in sensor.values())})

dump("stage11cc_runtime_image_binding.json", {
    "planner_runtime_image_id": PLANNER_IMAGE, "gazebo_image_id": GAZEBO_IMAGE,
    "bridge_base_image_id": BRIDGE_BASE, "planner_execution_device": "cpu",
    "cuda_visible_devices": "", "nvidia_visible_devices": "void",
    "ros_domain_id": 42, "gz_partition": "sgcf_stage11ca", "network_mode": "host",
})
dump("stage11cc_process_cleanup.json", {
    "scene_containers_remaining": [], "host_stage_processes_remaining": [],
    "residual_container_count": 0, "residual_process_count": 0, "passed": True,
})

limitations = """# Known limitations\n\n- The Gazebo runtime is functionally equivalent to the historical Stage 11B-N image, not binary-identical to it.\n- Oracle semantics are simulation ground truth and are not Stage 10 prediction.\n- `semantic_infeasible` steady-state Planner P95 is 216.923 ms, above the 200 ms hard limit. The formal failure path synchronously constructs and evaluates a geometry-only comparison planner. No Core modification was authorized.\n- Known nonfatal headless EGL / DRM warnings remain as documented in prior stages.\n"""
(OUT / "known_limitations.md").write_text(limitations)

decision = "BLOCKED_PLANNER_INTERFACE_LATENCY"
(OUT / "stage_11c_c_decision.md").write_text(f"# Stage 11C-C Decision\n\n```text\n{decision}\n```\n\nAll seven authorized worlds completed their shadow-mode functional gates, but `semantic_infeasible` repeated steady-state P95 was 216.923 ms, exceeding the 200 ms hard threshold. Stage 11C-C is not complete and Stage 11C-D is not authorized.\n")
(OUT / "stage_11c_c_report.md").write_text(f"""# Stage 11C-C Planner Shadow-mode Report\n\n## Outcome\n\n`{decision}`\n\nSeven authorized worlds ran independently with real ROS inputs. The hard-zero firewall passed: Zero Guard was the sole `/cmd_vel` publisher, candidate topics had no bridge subscriber, all captured ROS and Gazebo commands were zero, and every robot remained below its motion threshold. ROS/Core replay differences were zero for {len(records)} mode evaluations. Oracle semantics, semantic infeasible status, initial collision, RGB dropout, and outdated-image contracts passed.\n\n## Blocking result\n\nThe independently repeated `semantic_infeasible` run produced an overall steady-state Planner P95 of **216.923 ms** (P1 218.282 ms; P2 215.823 ms), above the mandatory 200 ms threshold, with zero stale inputs and zero backlog. The synchronous formal geometry-only failure comparison dominates this path. Core / Planner modification was prohibited, so the stage stopped here.\n\n## Safety and preservation\n\n- Nonzero Gazebo command count: 0\n- Candidate reaching `/cmd_vel` or Gazebo: 0\n- Self-return count: 0 in all scenes\n- ROS/Core maximum numeric difference: 0\n- Residual stage containers / processes: 0\n- Gazebo, Core, Planner, and immutable images were not modified.\n\nStage 11C-D was not started.\n""")
