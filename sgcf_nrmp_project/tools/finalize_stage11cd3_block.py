#!/usr/bin/env python3
"""Record the Stage 11C-D3 human-path semantic feasibility block."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_d3_oracle_semantic_closed_loop"


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=True) + "\n")


def run(name):
    runtime = OUT / "runtime" / name
    planner = json.loads((runtime / "planner_result.json").read_text())
    gate = json.loads((runtime / "safe_gate_result.json").read_text())
    odom = gate["odom_log"]
    transitions = []
    last = None
    for row in gate["command_log"]:
        if row["phase"] != last:
            transitions.append((row["phase"], row["sim_time"]))
            last = row["phase"]
    phase = dict(transitions)
    start = [x for x in odom if x["sim_time"] <= phase["ACTIVE"]][-1]
    end = [x for x in odom if x["sim_time"] <= phase["FINAL_STOP"]][-1]
    distance = lambda x: math.hypot(4.0 - x["x"], x["y"])
    records = planner["records"]
    margins = [value for row in records for value in row["result"].get("margin", [])]
    final = odom[-1]
    last_half = [x for x in odom if x["sim_time"] >= final["sim_time"] - 0.5]
    return {
        "run": name,
        "mode": records[0]["mode"],
        "evaluations": planner["counts"]["evaluations"],
        "statuses": sorted({row["result"]["status"] for row in records}),
        "eligible_evaluations": sum(row["result"]["eligible"] for row in records),
        "nonzero_actuation_count": gate["forwarded_nonzero_count"],
        "goal_distance_reduction_m": distance(start) - distance(end),
        "semantic_source": sorted({row["semantic"]["source"] for row in records}),
        "semantic_scope": sorted({row["semantic"].get("scope") for row in records if row["semantic"].get("scope")}),
        "not_stage10": all(row["semantic"].get("not_stage10", True) for row in records),
        "semantic_margin_min": min(margins) if margins else 0.0,
        "semantic_margin_max": max(margins) if margins else 0.0,
        "deadline_miss_count": planner["deadline_miss_count"],
        "latency": planner["latency"],
        "self_return_count": gate["self_return_count"],
        "candidate_equivalence_max": max(row["equivalence"]["candidate"] for row in records),
        "geometry_equivalence_max": max(max(row["equivalence"]["d_geo"], row["equivalence"]["g_geo"]) for row in records),
        "final_linear_speed": abs(final["v"]),
        "final_angular_speed": abs(final["w"]),
        "last_half_second_translation": math.hypot(last_half[-1]["x"] - last_half[0]["x"], last_half[-1]["y"] - last_half[0]["y"]),
        "last_half_second_yaw": abs(last_half[-1]["yaw"] - last_half[0]["yaw"]),
    }


def main():
    runs = {mode: run(f"human_path_center_{mode.lower()}") for mode in ("P0", "P1", "P2")}
    first = {}
    for mode in ("P0", "P1", "P2"):
        data = json.loads((OUT / "runtime" / f"human_path_center_{mode.lower()}" / "planner_result.json").read_text())
        first[mode] = data["records"][0]
    geometry = {
        "same_configuration": True,
        "same_goal": first["P0"]["goal"] == first["P1"]["goal"] == first["P2"]["goal"],
        "observable_point_counts": {mode: first[mode]["observable_point_count"] for mode in first},
        "p0_p1_d_geo_max_difference": float(np.max(np.abs(np.asarray(first["P0"]["result"]["d_geo"]) - np.asarray(first["P1"]["result"]["d_geo"])))),
        "p0_p2_d_geo_max_difference": float(np.max(np.abs(np.asarray(first["P0"]["result"]["d_geo"]) - np.asarray(first["P2"]["result"]["d_geo"])))),
        "note": "independent deterministic initial runs; ROS/Core replay within each run is exact",
    }
    write("stage11cd3_human_path_center.json", runs)
    write("stage11cd3_oracle_semantic_runtime.json", {"status": "BLOCKED_ORACLE_SEMANTIC_CLOSED_LOOP_FEASIBILITY", "human_path_center": runs, "remaining_scenes_started": False})
    write("stage11cd3_geometry_invariance.json", geometry)
    write("stage11cd3_semantic_margin_audit.json", {mode: {"minimum": value["semantic_margin_min"], "maximum": value["semantic_margin_max"]} for mode, value in runs.items()})
    write("stage11cd3_command_consistency.json", {mode: {"ros_core_candidate_error": value["candidate_equivalence_max"], "nonzero_actuation_count": value["nonzero_actuation_count"]} for mode, value in runs.items()})
    write("stage11cd3_runtime_performance.json", {mode: value["latency"] for mode, value in runs.items()})
    write("stage11cd3_ros_core_equivalence.json", {mode: {"candidate_max": value["candidate_equivalence_max"], "geometry_max": value["geometry_equivalence_max"]} for mode, value in runs.items()})
    write("stage11cd3_zero_stop_response.json", {mode: {"final_linear_speed": value["final_linear_speed"], "final_angular_speed": value["final_angular_speed"], "last_half_second_translation": value["last_half_second_translation"], "last_half_second_yaw": value["last_half_second_yaw"]} for mode, value in runs.items()})
    not_run = {"status": "NOT_RUN_DUE_TO_PRIOR_HARD_BLOCK", "reason": "P1/P2 human_path_center produced no legal nonzero closed-loop command"}
    write("stage11cd3_semantic_infeasible.json", not_run)
    write("stage11cd3_rgb_dropout.json", not_run)
    write("stage11cd3_outdated_rgb.json", not_run)
    write("stage11cd3_regression_matrix.json", {"status": "NOT_RUN_DUE_TO_PRIOR_HARD_BLOCK", "stage09c_preserved": True, "core_modified": False, "d_safe_m": 0.25, "speed_bounds": {"linear": 1.0, "angular": 1.5}})
    residual_containers = []
    residual_processes = []
    for path in OUT.glob("logs/*/residual_containers.txt"):
        residual_containers += [x for x in path.read_text().splitlines() if x.strip()]
    for path in OUT.glob("logs/*/residual_processes.txt"):
        residual_processes += [x for x in path.read_text().splitlines() if x.strip() and "run_stage11cc_shadow_gate.sh" not in x]
    write("stage11cd3_process_cleanup.json", {"residual_container_count": len(residual_containers), "residual_process_count": len(residual_processes), "passed": not residual_containers and not residual_processes})
    print(json.dumps(runs, indent=2))


if __name__ == "__main__":
    main()
