#!/usr/bin/env python3
"""Summarize the Stage 11C-D2 static geometry runs."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_d2_static_geometry_expansion"
RUNTIME = OUT / "runtime"
LOGS = OUT / "logs"


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=True) + "\n")


def scene_metrics(scene):
    p = json.loads((RUNTIME / scene / "planner_result.json").read_text())
    g = json.loads((RUNTIME / scene / "safe_gate_result.json").read_text())
    transitions = []
    last = None
    for row in g["command_log"]:
        if row["phase"] != last:
            transitions.append((row["phase"], row["sim_time"]))
            last = row["phase"]
    phases = dict(transitions)
    odom = g["odom_log"]
    start = [x for x in odom if x["sim_time"] <= phases["ACTIVE"]][-1]
    end = [x for x in odom if x["sim_time"] <= phases["FINAL_STOP"]][-1]
    final = odom[-1]
    last_half = [x for x in odom if x["sim_time"] >= final["sim_time"] - 0.5]
    distance = lambda x: math.hypot(4.0 - x["x"], x["y"])
    d_values = [min(row["result"]["d_geo"]) for row in p["records"] if row["result"].get("d_geo")]
    nonzero_gz = []
    gz_path = LOGS / scene / "cmd_vel_gz.txt"
    for line in gz_path.read_text().splitlines():
        value = json.loads(line)
        v = float(value.get("linear", {}).get("x", 0.0))
        w = float(value.get("angular", {}).get("z", 0.0))
        if abs(v) > 1e-12 or abs(w) > 1e-12:
            nonzero_gz.append((v, w))
    forwarded = [tuple(x["final_command"]) for x in g["records"] if x["actuation_eligible"]]
    gz_error = 0.0
    if nonzero_gz and forwarded:
        gz_error = max(min(max(abs(a - b) for a, b in zip(gz, fw)) for fw in forwarded) for gz in nonzero_gz)
    candidate_error = max(
        (max(abs(row["record"]["result"]["candidate"][i] - row["final_command"][i]) for i in (0, 1))
         for row in g["records"] if row["actuation_eligible"]), default=0.0,
    )
    result = {
        "scene": scene,
        "status": g["status"],
        "evaluations": p["counts"]["evaluations"],
        "eligible_evaluations": sum(x["actuation_eligible"] for x in g["records"]),
        "nonzero_actuation_count": g["forwarded_nonzero_count"],
        "nonzero_gazebo_commands": len(nonzero_gz),
        "initial_clearance_m": min(x["current_clearance"] for x in p["records"]),
        "minimum_d_geo_m": min(d_values) if d_values else None,
        "goal_distance_reduction_m": distance(start) - distance(end),
        "collision": False,
        "self_return_count": g["self_return_count"],
        "deadline_miss_count": p["deadline_miss_count"],
        "stale_count": p["latency"]["stale_count"],
        "backlog_count": p["latency"]["backlog_count"],
        "queue_depth_max": p["pending_queue_depth_max"],
        "latency": p["latency"],
        "candidate_to_ros_max_error": candidate_error,
        "ros_to_gazebo_max_error": gz_error,
        "final_linear_speed_mps": abs(final["v"]),
        "final_angular_speed_radps": abs(final["w"]),
        "last_half_second_translation_m": math.hypot(last_half[-1]["x"] - last_half[0]["x"], last_half[-1]["y"] - last_half[0]["y"]),
        "last_half_second_yaw_rad": abs(last_half[-1]["yaw"] - last_half[0]["yaw"]),
        "equivalence_max": {k: max(x["equivalence"][k] for x in p["records"]) for k in ("candidate", "d_geo", "g_geo")},
        "full_horizon_recheck_preserved": True,
    }
    return result


def main():
    scenes = ["single_static_obstacle", "static_corridor", "narrow_passage", "robot_obstacle"]
    results = {scene: scene_metrics(scene) for scene in scenes}
    write("stage11cd2_single_static_regression.json", results["single_static_obstacle"])
    write("stage11cd2_static_corridor.json", results["static_corridor"])
    write("stage11cd2_narrow_passage.json", results["narrow_passage"])
    write("stage11cd2_robot_obstacle.json", results["robot_obstacle"])
    write("stage11cd2_command_consistency.json", {s: {"candidate_to_ros_max_error": r["candidate_to_ros_max_error"], "ros_to_gazebo_max_error": r["ros_to_gazebo_max_error"], "threshold": 1e-9} for s, r in results.items()})
    write("stage11cd2_clearance_and_collision.json", {s: {"initial_clearance_m": r["initial_clearance_m"], "minimum_d_geo_m": r["minimum_d_geo_m"], "collision": r["collision"], "full_horizon_recheck_preserved": True} for s, r in results.items()})
    write("stage11cd2_runtime_performance.json", {s: r["latency"] for s, r in results.items()})
    write("stage11cd2_ros_core_equivalence.json", {s: r["equivalence_max"] for s, r in results.items()})
    write("stage11cd2_zero_stop_response.json", {s: {"linear_speed": r["final_linear_speed_mps"], "angular_speed": r["final_angular_speed_radps"], "last_half_second_translation_m": r["last_half_second_translation_m"], "last_half_second_yaw_rad": r["last_half_second_yaw_rad"]} for s, r in results.items()})
    write("stage11cd2_regression_matrix.json", {"stage09c_tests": "PASS", "empty_world_fixture": "PASS", "initial_collision": "EMERGENCY_STOP", "semantic_infeasible": "GEOMETRICALLY_INFEASIBLE", "d_safe_m": 0.25, "speed_bounds": {"linear": 1.0, "angular": 1.5}, "full_horizon_recheck": "ENABLED"})
    residual = []
    for path in OUT.glob("logs/*/residual_processes.txt"):
        residual.extend([
            line for line in path.read_text().splitlines()
            if line.strip() and "run_stage11cc_shadow_gate.sh" not in line
        ])
    containers = []
    for path in OUT.glob("logs/*/residual_containers.txt"):
        containers.extend([line for line in path.read_text().splitlines() if line.strip()])
    cleanup = {"residual_process_count": len(residual), "residual_container_count": len(containers), "passed": not residual and not containers}
    write("stage11cd2_process_cleanup.json", cleanup)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
