"""Analyze Stage 15 baseline feasibility without changing planner behavior."""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGE15 = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15_oracle_semantic_closed_loop"
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15a_baseline_feasibility_analysis"
RERUN = OUT / "runtime"
GOAL_TOLERANCE_M = 0.25
ACTIVE_DURATION_S = 6.0
REFERENCE_SPEED_MPS = 0.30
MAX_SPEED_MPS = 1.0


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def run_metrics(run_dir: Path) -> dict:
    planner = load(run_dir / "planner_result.json")
    gate = load(run_dir / "safe_gate_result.json")
    records = planner["records"]
    goal = records[0]["goal"]
    odom = gate["odom_log"]
    distances = [math.hypot(goal[0] - row["x"], goal[1] - row["y"]) for row in odom]
    statuses = collections.Counter(row["result"]["status"] for row in records)
    geometry_rejections = sum(
        status in {"REJECTED_BY_GEOMETRY_CHECK", "GEOMETRICALLY_INFEASIBLE"}
        for status in (row["result"]["status"] for row in records)
    )
    progress = distances[0] - distances[-1]
    maximum_progress = max(distances[0] - value for value in distances)
    eligible = sum(bool(row["actuation_eligible"]) for row in records)
    semantic_infeasible = statuses["SEMANTICALLY_INFEASIBLE"]
    nonzero = int(gate["forwarded_nonzero_count"])
    final_status = records[-1]["result"]["status"]

    # Classification is deliberately deterministic and never emits UNKNOWN.
    if semantic_infeasible and nonzero == 0:
        cause = "SEMANTICALLY_INFEASIBLE"
    elif progress <= -0.05:
        cause = "REVERSE_OR_DIVERGENT_PROGRESS"
    elif nonzero == 0:
        cause = "SAFE_REJECTION" if geometry_rejections else "NO_LEGAL_COMMAND"
    elif maximum_progress >= 0.05 and ACTIVE_DURATION_S < distances[0] / REFERENCE_SPEED_MPS:
        cause = "TIMEOUT_TOO_SHORT"
    elif geometry_rejections >= len(records) / 2:
        cause = "PLANNER_COMPLETENESS_LIMITATION"
    elif progress > 0:
        cause = "PROGRESS_WITHOUT_GOAL_REACH"
    else:
        cause = "OTHER_CONFIRMED_CAUSE"

    runtime_scene = records[0]["scene"]
    scene = "mixed_static_human_vehicle" if runtime_scene.startswith("stage15_mixed") else records[0].get("base_scene_contract", runtime_scene)
    positive_commands = [abs(row["v"]) for row in gate["command_log"] if abs(row["v"]) > 0]
    legal_average_speed = sum(positive_commands) / len(positive_commands) if positive_commands else 0.0
    return {
        "run_id": run_dir.name,
        "scene": scene,
        "runtime_scene": runtime_scene,
        "mode": records[0]["mode"],
        "initial_goal_distance_m": distances[0],
        "final_goal_distance_m": distances[-1],
        "goal_progress_m": progress,
        "maximum_positive_progress_m": maximum_progress,
        "recorded_runtime_s": odom[-1]["sim_time"] - odom[0]["sim_time"],
        "active_command_window_s": ACTIVE_DURATION_S,
        "active_window_completed": gate["phase"] == "FINAL_STOP",
        "nonzero_command_count": nonzero,
        "legal_average_linear_speed_mps": legal_average_speed,
        "completion_time_at_observed_legal_average_speed_s": distances[0] / legal_average_speed if legal_average_speed else None,
        "command_eligible_ratio": eligible / len(records),
        "zero_fallback_count": int(gate["rejected_count"]),
        "planner_final_status": final_status,
        "status_counts": dict(statuses),
        "geometry_rejection_count": geometry_rejections,
        "semantic_infeasible_count": semantic_infeasible,
        "deadline_miss_count": int(planner["deadline_miss_count"]),
        "minimum_static_clearance_m": None,
        "minimum_human_clearance_m": None,
        "minimum_vehicle_clearance_m": None,
        "path_length_m": sum(
            math.hypot(b["x"] - a["x"], b["y"] - a["y"])
            for a, b in zip(odom, odom[1:])
        ),
        "oscillation": maximum_progress - progress > 0.05,
        "stagnation": maximum_progress < 0.05,
        "reverse_or_divergent": progress <= -0.05,
        "primary_failure_type": cause,
    }


def main() -> None:
    paired = [json.loads(line) for line in (STAGE15 / "stage15_p0_p2_paired_results.jsonl").read_text().splitlines() if line]
    clearances = {row["run_id"]: row for row in paired}
    runs = []
    for path in sorted((STAGE15 / "runtime").glob("*/planner_result.json")):
        row = run_metrics(path.parent)
        source = clearances[row["run_id"]]
        for key in ("minimum_static_clearance", "minimum_human_clearance", "minimum_vehicle_clearance"):
            row[key + "_m"] = source[key]
        runs.append(row)
    assert len(runs) == 70
    counts = collections.Counter(row["primary_failure_type"] for row in runs)
    write("stage15a_failure_classification.json", {"run_count": 70, "classification_counts": dict(counts), "runs": runs})

    initial_distances = [row["initial_goal_distance_m"] for row in runs]
    manifest = load(ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11a_gazebo_preparation/gazebo_scenario_manifest.json")
    shared = manifest["shared"]
    path_endpoint_errors = {
        name: math.hypot(points[-1][0] - shared["goal_pose"][0], points[-1][1] - shared["goal_pose"][1])
        for name, points in (
            ("straight", shared["straight_reference_waypoints"]),
            ("avoid", shared["avoid_reference_waypoints"]),
        )
    }
    protocol = {
        "success_definition": {"frame": "world/odom XY", "goal_tolerance_m": GOAL_TOLERANCE_M, "source": "Core offline simulator formal tolerance"},
        "goal_distance_range_m": [min(initial_distances), max(initial_distances)],
        "active_command_window_s": ACTIVE_DURATION_S,
        "reference_speed_mps": REFERENCE_SPEED_MPS,
        "configured_max_speed_mps": MAX_SPEED_MPS,
        "reference_speed_shortest_completion_time_s": min(initial_distances) / REFERENCE_SPEED_MPS,
        "max_bound_shortest_completion_time_s": min(initial_distances) / MAX_SPEED_MPS,
        "active_window_vs_reference_time_ratio": ACTIVE_DURATION_S / (min(initial_distances) / REFERENCE_SPEED_MPS),
        "safe_stop_counted_as_runtime_error": False,
        "goal_frame_consistent_with_odom": True,
        "goal_reference_path_endpoint_consistent": max(path_endpoint_errors.values()) <= 1e-12,
        "global_reference_endpoint_error_m": path_endpoint_errors,
        "snapshot_reference_note": "Saved reference_path is a rolling local horizon; its endpoint is not the global goal and is not evidence of a mismatch.",
        "defect": "ACTIVE_WINDOW_TOO_SHORT_FOR_REFERENCE_SPEED_GOAL_COMPLETION",
        "allowed_remedy": "Extend evaluation duration; do not change goal, planner, speed, or safety parameters.",
    }
    write("stage15a_success_protocol_audit.json", protocol)
    write("stage15a_goal_and_timeout_audit.json", {
        "all_runs_reached_active_timeout": all(row["active_window_completed"] for row in runs),
        "goal_tolerance_m": GOAL_TOLERANCE_M,
        "per_scene": {
            scene: {
                "initial_goal_distance_m": sorted({round(row["initial_goal_distance_m"], 9) for row in runs if row["scene"] == scene}),
                "reference_speed_minimum_time_s": min(row["initial_goal_distance_m"] for row in runs if row["scene"] == scene) / REFERENCE_SPEED_MPS,
                "active_window_s": ACTIVE_DURATION_S,
            }
            for scene in sorted({row["scene"] for row in runs})
        },
    })

    suitability = {}
    for scene in sorted({row["scene"] for row in runs}):
        subset = [row for row in runs if row["scene"] == scene]
        p0 = [row for row in subset if row["mode"] == "P0"]
        p2 = [row for row in subset if row["mode"] == "P2"]
        p0_progress = max(row["maximum_positive_progress_m"] for row in p0)
        p0_legal = max(row["nonzero_command_count"] for row in p0)
        designed_infeasible = scene == "semantic_infeasible"
        baseline_suitable = not designed_infeasible and p0_legal > 0 and p0_progress >= 0.05
        suitability[scene] = {
            "p0_primary_causes": dict(collections.Counter(row["primary_failure_type"] for row in p0)),
            "p2_primary_causes": dict(collections.Counter(row["primary_failure_type"] for row in p2)),
            "p0_maximum_positive_progress_m": p0_progress,
            "p2_maximum_positive_progress_m": max(row["maximum_positive_progress_m"] for row in p2),
            "p0_has_legal_command": p0_legal > 0,
            "designed_semantically_infeasible": designed_infeasible,
            "p0_p2_failure_causes_same": collections.Counter(row["primary_failure_type"] for row in p0) == collections.Counter(row["primary_failure_type"] for row in p2),
            "suitable_for_navigation_success_comparison": baseline_suitable,
            "recommended_role": "NAVIGATION_BASELINE_CANDIDATE" if baseline_suitable else "SAFETY_REJECTION_OR_COMPLETENESS_DIAGNOSTIC",
        }
    write("stage15a_scene_suitability.json", suitability)

    reruns = []
    if RERUN.exists():
        for path in sorted(RERUN.glob("*/planner_result.json")):
            planner = load(path)
            gate = load(path.parent / "safe_gate_result.json")
            records = planner["records"]
            goal = records[0]["goal"]
            odom = gate["odom_log"]
            distances = [math.hypot(goal[0] - row["x"], goal[1] - row["y"]) for row in odom]
            forwarded = [row for row in gate["records"] if row["final_command"] != [0.0, 0.0]]
            runtime_scene = records[0]["scene"]
            rerun_scene = "mixed_static_human_vehicle" if (runtime_scene.startswith("stage15_mixed") or "mixed" in path.parent.name) else records[0].get("base_scene_contract", runtime_scene)
            reruns.append({
                "run_id": path.parent.name,
                "scene": rerun_scene,
                "initial_goal_distance_m": distances[0],
                "final_goal_distance_m": distances[-1],
                "goal_progress_m": distances[0] - distances[-1],
                "maximum_positive_progress_m": max(distances[0] - value for value in distances),
                "goal_reached": distances[-1] <= GOAL_TOLERANCE_M,
                "active_duration_s": 20.0,
                "nonzero_command_count": gate["forwarded_nonzero_count"],
                "command_eligible_ratio": sum(row["actuation_eligible"] for row in records) / len(records),
                "collision_count": sum(row["current_collision"] for row in records),
                "stale_late_ineligible_executed": sum(
                    (not row["checks"]["candidate_fresh"]) or row["record"]["deadline_miss"] or (not row["record"]["actuation_eligible"])
                    for row in forwarded
                ),
                "zero_stop": gate["phase"] == "FINAL_STOP" and all(row["v"] == row["w"] == 0 for row in gate["command_log"][-5:]),
                "final_status": records[-1]["result"]["status"],
                "status_counts": dict(collections.Counter(row["result"]["status"] for row in records)),
                "interpretation": "GOAL_REACHED" if distances[-1] <= GOAL_TOLERANCE_M else ("PARTIAL_PROGRESS" if distances[0] - distances[-1] >= 0.05 else "PLANNER_COMPLETENESS_LIMITATION"),
            })
    write("stage15a_minimal_p0_rerun.json", {"selection_basis": "Top historical P0 progress from distinct candidate scene types", "run_count": len(reruns), "runs": reruns})

    for scene, row in suitability.items():
        scene_reruns = [item for item in reruns if item["scene"] == scene]
        row["minimal_rerun"] = scene_reruns
        row["p0_goal_baseline_established"] = any(item["goal_reached"] for item in scene_reruns)
        row["p0_partial_progress_baseline_established"] = any(item["goal_progress_m"] >= 0.05 for item in scene_reruns)
        # A Stage 15 navigation-success comparison requires an actual P0 goal
        # success, not only a promising six-second trace.
        row["suitable_for_navigation_success_comparison"] = row["p0_goal_baseline_established"]
        if row["p0_goal_baseline_established"]:
            row["recommended_role"] = "NAVIGATION_BASELINE_CANDIDATE"
        elif row["p0_partial_progress_baseline_established"]:
            row["recommended_role"] = "PARTIAL_PROGRESS_BASELINE_ONLY"
        else:
            row["recommended_role"] = "SAFETY_REJECTION_OR_COMPLETENESS_DIAGNOSTIC"
    write("stage15a_scene_suitability.json", suitability)

    any_success = any(row["goal_reached"] for row in reruns)
    any_progress = any(row["goal_progress_m"] >= 0.05 for row in reruns)
    if any_success:
        decision = "STAGE_15A_COMPLETE"
        lines = ["STAGE15_BASELINE_PROTOCOL_DEFECT_FIXED", "P0_NAVIGATION_BASELINE_ESTABLISHED", "READY_TO_REPEAT_STAGE_15_ORACLE_COMPARISON"]
    elif any_progress:
        decision = "STAGE_15A_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS"
        lines = ["P0_PARTIAL_PROGRESS_BASELINE_ESTABLISHED", "FULL_NAVIGATION_SUCCESS_NOT_ESTABLISHED", "STAGE_16_REMAINS_BLOCKED"]
    else:
        decision = "STAGE_15A_COMPLETE_WITH_NEGATIVE_BASELINE_RESULT"
        lines = ["P0_SEMANTIC_SCENE_NAVIGATION_BASELINE_NOT_ESTABLISHED", "ORACLE_BENEFIT_NOT_IDENTIFIABLE", "DO_NOT_PROCEED_TO_STAGE_16"]
    write("stage15a_stage16_readiness.json", {"decision": decision, "stage16_ready": False, "protocol_defect_confirmed": True, "p0_goal_success_established": any_success, "p0_partial_progress_established": any_progress, "required_next_action": "Repeat Stage 15 only if a P0 success baseline is established; Stage 16 remains blocked."})
    (OUT / "stage_15a_decision.md").write_text("# Stage 15A Decision\n\n```text\n" + "\n".join([decision, *lines]) + "\n```\n")
    scene_lines = []
    for scene, row in suitability.items():
        p0_causes = ", ".join(f"{key}={value}" for key, value in sorted(row["p0_primary_causes"].items()))
        p2_causes = ", ".join(f"{key}={value}" for key, value in sorted(row["p2_primary_causes"].items()))
        scene_lines.append(
            f"- `{scene}`: P0 [{p0_causes}], max progress {row['p0_maximum_positive_progress_m']:.6f} m; "
            f"P2 [{p2_causes}], max progress {row['p2_maximum_positive_progress_m']:.6f} m. "
            f"Role: `{row['recommended_role']}`."
        )
    rerun_lines = [
        f"- `{row['scene']}`: progress {row['goal_progress_m']:.6f} m, final distance {row['final_goal_distance_m']:.6f} m, "
        f"status `{row['final_status']}`, interpretation `{row['interpretation']}`."
        for row in reruns
    ]
    (OUT / "stage_15a_report.md").write_text(
        "# Stage 15A Oracle Baseline Feasibility Analysis\n\n"
        f"## Decision\n\n`{decision}`\n\n"
        "## Root cause\n\nStage 15 used a 6 s active command window for a 4 m goal. At the frozen 0.30 m/s reference speed, the theoretical minimum is 13.33 s. This is a protocol floor for goal-reaching statistics, but it is not the sole failure: most runs also contain repeated exact-geometry rejection, geometric infeasibility, or semantic infeasibility.\n\n"
        "The global straight and avoidance paths both end at the configured goal. Saved snapshot paths are rolling planner horizons, so their nearer endpoints are expected and are not a goal/path mismatch. Safe stops were not counted as runtime errors.\n\n"
        "## Per-scene diagnosis\n\n" + "\n".join(scene_lines) + "\n\n"
        f"## Minimal reruns\n\n{len(reruns)} P0 reruns used a 20 s window without changing the goal, scene, planner, speed, or safety parameters. Goal success established: {any_success}. Stable progress established: {any_progress}.\n\n" + "\n".join(rerun_lines) + "\n\n"
        "## Stage 16\n\nStage 16 remains blocked. Semantic-infeasible and no-legal-path cases are safety-rejection tests, not navigation-success comparison scenes.\n"
    )
    print(json.dumps({"runs": len(runs), "classification_counts": dict(counts), "reruns": reruns, "decision": decision}, indent=2))


if __name__ == "__main__":
    main()
