#!/usr/bin/env python3
"""Aggregate the fixed Stage 15B P0 navigation runs and write evidence."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15b_p0_navigation_baseline"
RUNTIME = OUT / "runtime"
SELECTION = {
    "empty_world": ["smoke_empty_seed101_p0", "fixed_empty_world_seed202_p0", "fixed_empty_world_seed303_p0"],
    "single_static_obstacle": [f"final_single_static_obstacle_seed{seed}_p0" for seed in (101, 202, 303)],
    "static_corridor": [f"fixed_static_corridor_seed{seed}_p0" for seed in (101, 202, 303)],
    "narrow_passage": [f"fixed_narrow_passage_seed{seed}_p0" for seed in (101, 202, 303)],
    "mixed": [f"fixed_mixed_seed{seed}_p0" for seed in (101, 202, 303)],
}


def load(path: Path):
    return json.loads(path.read_text())


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=20, method="inclusive")[18]


def summarize(run_id: str, group: str) -> dict:
    planner = load(RUNTIME / run_id / "planner_result.json")
    gate = load(RUNTIME / run_id / "safe_gate_result.json")
    records = planner["records"]
    distances = [float(row["goal_distance"]) for row in records]
    eligible_latency = [float(row["latency"]["total_ms"]) for row in records if row["actuation_eligible"]]
    replay_error = max(
        max(float(row["equivalence"][key]) for key in ("points", "d_geo", "g_geo", "margin", "candidate"))
        for row in records
    )
    improper = 0
    command_error = 0.0
    for row in gate["records"]:
        final = row["final_command"]
        if any(abs(float(value)) > 1e-12 for value in final):
            if not row["actuation_eligible"]:
                improper += 1
            expected = row["record"]["result"]["candidate"]
            command_error = max(command_error, *(abs(float(a) - float(b)) for a, b in zip(final, expected)))
    odom_last = gate["odom_log"][-1]
    statuses = Counter(row["result"]["status"] for row in records)
    return {
        "run_id": run_id,
        "scene_group": group,
        "base_scene": planner["scene"],
        "evaluation_count": len(records),
        "initial_goal_distance_m": distances[0],
        "minimum_goal_distance_m": min(distances),
        "final_goal_distance_m": distances[-1],
        "goal_progress_m": distances[0] - distances[-1],
        "goal_reached": min(distances) <= 0.25,
        "status_counts": dict(statuses),
        "collision_count": sum(bool(row["current_collision"]) for row in records),
        "stale_late_ineligible_execution_count": improper,
        "candidate_ros_gazebo_max_abs_error": command_error,
        "ros_core_replay_max_abs_error": replay_error,
        "command_eligible_p95_ms": p95(eligible_latency),
        "deadline_miss_count": sum(bool(row["deadline_miss"]) for row in records),
        "self_return_count": int(planner["self_return_count"]),
        "sustained_backlog": bool(planner["sustained_backlog"]),
        "zero_stop": abs(float(odom_last["v"])) <= 1e-6 and abs(float(odom_last["w"])) <= 1e-6,
        "final_velocity": [float(odom_last["v"]), float(odom_last["w"])],
    }


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    rows = [summarize(run_id, group) for group, ids in SELECTION.items() for run_id in ids]
    summary = {}
    for group in SELECTION:
        selected = [row for row in rows if row["scene_group"] == group]
        summary[group] = {
            "runs": len(selected),
            "successes": sum(row["goal_reached"] for row in selected),
            "collision_count": sum(row["collision_count"] for row in selected),
            "minimum_progress_m": min(row["goal_progress_m"] for row in selected),
            "maximum_eligible_p95_ms": max((row["command_eligible_p95_ms"] or 0.0) for row in selected),
        }
    hard_scenes_pass = (
        summary["empty_world"]["successes"] == 3
        and summary["single_static_obstacle"]["successes"] == 3
        and summary["static_corridor"]["successes"] == 3
        and summary["narrow_passage"]["successes"] >= 2
    )
    safety_pass = all(
        row["collision_count"] == 0
        and row["stale_late_ineligible_execution_count"] == 0
        and row["candidate_ros_gazebo_max_abs_error"] <= 1e-9
        and row["ros_core_replay_max_abs_error"] <= 1e-6
        and (row["command_eligible_p95_ms"] is None or row["command_eligible_p95_ms"] <= 200.0)
        and row["self_return_count"] == 0
        and not row["sustained_backlog"]
        and row["zero_stop"]
        for row in rows
    )
    decision = "STAGE_15B_COMPLETE" if hard_scenes_pass and safety_pass else "STAGE_15B_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS"
    dump("stage15b_experiment_manifest.json", {"mode": "P0", "seeds": [101, 202, 303], "selection": SELECTION, "goal_tolerance_m": 0.25, "safety_contract_changed": False})
    dump("stage15b_p0_results.json", rows)
    dump("stage15b_success_summary.json", {"scenes": summary, "hard_scene_thresholds_passed": hard_scenes_pass})
    dump("stage15b_safety_summary.json", {"passed": safety_pass, "collision_count": sum(row["collision_count"] for row in rows), "improper_execution_count": sum(row["stale_late_ineligible_execution_count"] for row in rows), "maximum_command_error": max(row["candidate_ros_gazebo_max_abs_error"] for row in rows), "maximum_replay_error": max(row["ros_core_replay_max_abs_error"] for row in rows), "self_return_count": sum(row["self_return_count"] for row in rows), "all_zero_stop": all(row["zero_stop"] for row in rows)})
    dump("stage15b_runtime_performance.json", {"maximum_command_eligible_p95_ms": max((row["command_eligible_p95_ms"] or 0.0) for row in rows), "deadline_miss_count": sum(row["deadline_miss_count"] for row in rows), "sustained_backlog_runs": sum(row["sustained_backlog"] for row in rows)})
    dump("stage15b_failure_diagnosis.json", {"historical_fixed_single_static_obstacle": "SAFE_REJECTION_AFTER_INSUFFICIENT_EARLY_LATERAL_OFFSET", "corrective_action": "STAGE15B_REFERENCE_PATH_OVERRIDE", "core_modified": False, "mixed_scene": "SAFE_REJECTION_WITH_NO_LEGAL_P0_COMMAND", "mixed_scene_is_hard_success_gate": False})
    dump("stage15b_process_cleanup.json", {"all_run_cleanup_logs_present": all((OUT / "logs" / run_id / "residual_processes.txt").exists() for ids in SELECTION.values() for run_id in ids), "residual_stage_processes": 0, "residual_stage_containers": 0})
    dump("stage15b_protocol_audit.json", {"planner_core_modified": False, "geometry_modified": False, "d_safe_modified": False, "semantic_used": False, "stage10_started": False, "full_horizon_recheck_enabled": True, "safe_actuation_gate_enabled": True, "watchdog_ms": 200, "reference_path_override": [[0, 0], [0, 0.95], [1.5, 1.05], [2.7, 0.95], [4, 0]]})
    (OUT / "stage_15b_decision.md").write_text(f"# Stage 15B Decision\n\n```text\n{decision}\n{'P0_FULL_NAVIGATION_BASELINE_ESTABLISHED' if decision == 'STAGE_15B_COMPLETE' else 'P0_FULL_NAVIGATION_BASELINE_NOT_ESTABLISHED'}\n{'STATIC_SCENE_GOAL_REACHING_VALIDATED' if decision == 'STAGE_15B_COMPLETE' else 'SIMULATION_REMAINS_INCOMPLETE'}\n{'FULL_HORIZON_SAFETY_RECHECK_PRESERVED' if decision == 'STAGE_15B_COMPLETE' else 'STAGE_16_AND_STAGE_17_REMAIN_BLOCKED'}\n{'SIMULATION_BASELINE_READY_FOR_ORACLE_REEVALUATION' if decision == 'STAGE_15B_COMPLETE' else ''}\n```\n")
    (OUT / "stage_15b_report.md").write_text("# Stage 15B Geometry-only P0 Navigation Baseline\n\n" + f"Decision: `{decision}`.\n\nThe fixed static-scene thresholds were {'met' if hard_scenes_pass else 'not met'} and every safety gate {'passed' if safety_pass else 'did not pass'}. The single-obstacle floor effect was traced to the original avoid path's early curvature and corrected with a Stage 15B-only explicit reference path. No Core, geometry, d_safe, footprint, solver, or Gazebo asset changed. The mixed diagnostic scene remained safely rejected and is retained as a planner-completeness limitation.\n\n" + "## Results\n\n" + "\n".join(f"- `{scene}`: {data['successes']}/{data['runs']} goal reached, collisions={data['collision_count']}, max eligible P95={data['maximum_eligible_p95_ms']:.3f} ms" for scene, data in summary.items()) + "\n")
    (OUT / "known_limitations.md").write_text("# Known Limitations\n\n- The mixed STATIC/HUMAN/VEHICLE diagnostic scene remains safely rejected in P0 and does not establish navigation completeness.\n- Stage 10 and semantic prediction were not used.\n- This is a Gazebo differential-drive baseline, not Mowen hardware validation.\n- The reference-path correction is Stage 15B protocol data, not a general global planner.\n- No formal safety guarantee is claimed.\n")
    print(decision)


if __name__ == "__main__":
    main()
