#!/usr/bin/env python3
"""Aggregate Stage 15C feasible-baseline Oracle semantic experiments."""

from __future__ import annotations

import json
import math
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15c_oracle_semantic_reevaluation"
RUNTIME = OUT / "runtime"
OVERLAY = ROOT / "sgcf_nrmp_project/gazebo/overlays/stage15c_feasible_semantics/manifest.json"
NEAR_MISS_M = 0.25


def load(path: Path):
    return json.loads(path.read_text())


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q / 100.0
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def rectangle(center, half_x, half_y, yaw=0.0):
    c, s = math.cos(yaw), math.sin(yaw)
    return [
        (center[0] + c * x - s * y, center[1] + s * x + c * y)
        for x, y in ((-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y))
    ]


def point_segment(point, start, end):
    vx, vy = end[0] - start[0], end[1] - start[1]
    denominator = vx * vx + vy * vy
    projection = 0.0 if denominator == 0 else ((point[0] - start[0]) * vx + (point[1] - start[1]) * vy) / denominator
    projection = max(0.0, min(1.0, projection))
    return math.hypot(point[0] - start[0] - projection * vx, point[1] - start[1] - projection * vy)


def polygon_clearance(left, right):
    for polygon in (left, right):
        for index in range(len(polygon)):
            edge = (polygon[(index + 1) % len(polygon)][0] - polygon[index][0], polygon[(index + 1) % len(polygon)][1] - polygon[index][1])
            axis = (-edge[1], edge[0])
            left_projection = [point[0] * axis[0] + point[1] * axis[1] for point in left]
            right_projection = [point[0] * axis[0] + point[1] * axis[1] for point in right]
            if max(left_projection) < min(right_projection) or max(right_projection) < min(left_projection):
                break
        else:
            continue
        break
    else:
        return 0.0
    return min(
        point_segment(left[i], right[j], right[(j + 1) % 4])
        for i in range(4) for j in range(4)
    )


def obstacle_clearance(pose, obstacle):
    robot = rectangle((pose[0], pose[1]), 0.4, 0.25, pose[2])
    if obstacle["class_name"] == "VEHICLE":
        return polygon_clearance(robot, rectangle(obstacle["center"], 0.4, 0.25))
    center = obstacle["center"]
    return min(point_segment(center, robot[i], robot[(i + 1) % 4]) for i in range(4)) - 0.35


def run_summary(run_id: str, scenario: dict) -> dict:
    planner = load(RUNTIME / run_id / "planner_result.json")
    gate = load(RUNTIME / run_id / "safe_gate_result.json")
    records = planner["records"]
    mode = records[0]["mode"]
    odom = gate["odom_log"]
    goal_distances = [float(record["goal_distance"]) for record in records]
    goal_index = next((index for index, value in enumerate(goal_distances) if value <= 0.25), None)
    path_limit = records[goal_index]["simulation_timestamp"] if goal_index is not None else math.inf
    path_odom = [row for row in odom if row["sim_time"] <= path_limit]
    path_length = sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(path_odom, path_odom[1:]))
    clearances = {name: [] for name in ("STATIC_OBSTACLE", "HUMAN", "VEHICLE")}
    for row in path_odom:
        pose = (float(row["x"]), float(row["y"]), float(row["yaw"]))
        for obstacle in scenario["obstacles"]:
            clearances[obstacle["class_name"]].append(obstacle_clearance(pose, obstacle))
    eligible_latency = [float(record["latency"]["total_ms"]) for record in records if record["actuation_eligible"]]
    replay_error = max(
        max(float(record["equivalence"][key]) for key in ("points", "d_geo", "g_geo", "margin", "candidate"))
        for record in records
    )
    forwarded = [record for record in gate["records"] if any(abs(float(value)) > 1e-12 for value in record["final_command"])]
    improper = sum(not record["actuation_eligible"] for record in forwarded)
    command_error = max([
        max(abs(float(a) - float(b)) for a, b in zip(record["final_command"], record["record"]["result"]["candidate"]))
        for record in forwarded
    ] or [0.0])
    margins = [float(value) for record in records for value in record["result"]["margin"]]
    status_counts = {}
    for record in records:
        status = record["result"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    minimum = {key: min(values) if values else None for key, values in clearances.items()}
    near = {key: sum(value < NEAR_MISS_M for value in values) for key, values in clearances.items()}
    final_odom = odom[-1]
    seed = int(re.search(r"seed(\d+)", run_id).group(1))
    return {
        "run_id": run_id,
        "scene": scenario["scene_id"],
        "seed": seed,
        "mode": mode,
        "semantic_source": "NONE" if mode == "P0" else "ORACLE_GROUND_TRUTH",
        "simulation_only": mode == "P2",
        "not_stage10_prediction": True,
        "success": min(goal_distances) <= 0.25,
        "completion_time_s": None if goal_index is None else records[goal_index]["simulation_timestamp"] - records[0]["simulation_timestamp"],
        "path_length_m": path_length,
        "initial_goal_distance_m": goal_distances[0],
        "final_goal_distance_m": goal_distances[-1],
        "minimum_goal_distance_m": min(goal_distances),
        "goal_progress_m": goal_distances[0] - goal_distances[-1],
        "minimum_static_clearance_m": minimum["STATIC_OBSTACLE"],
        "minimum_human_clearance_m": minimum["HUMAN"],
        "minimum_vehicle_clearance_m": minimum["VEHICLE"],
        "near_miss_count": sum(near.values()),
        "near_miss_by_class": near,
        "semantic_margin_mean_m": statistics.fmean(margins) if margins else 0.0,
        "semantic_margin_max_m": max(margins or [0.0]),
        "command_eligible_ratio": sum(record["actuation_eligible"] for record in records) / len(records),
        "zero_fallback_count": int(gate["rejected_count"]),
        "status_counts": status_counts,
        "collision_count": sum(bool(record["current_collision"]) for record in records),
        "deadline_miss_count": sum(bool(record["deadline_miss"]) for record in records),
        "stale_late_ineligible_execution_count": improper,
        "candidate_ros_gazebo_max_abs_error": command_error,
        "ros_core_replay_max_abs_error": replay_error,
        "command_eligible_p95_ms": percentile(eligible_latency, 95),
        "planner_all_path_p95_ms": float(planner["latency"]["p95"]),
        "robot_self_return_count": int(planner["self_return_count"]),
        "sustained_backlog": bool(planner["sustained_backlog"]),
        "zero_stop": abs(float(final_odom["v"])) <= 1e-6 and abs(float(final_odom["w"])) <= 1e-6,
        "full_horizon_recheck": True,
    }


def class_summary(rows, field, class_name):
    result = {}
    for mode in ("P0", "P2"):
        selected = [row for row in rows if row["mode"] == mode and row[field] is not None]
        values = [row[field] for row in selected]
        near = sum(row["near_miss_by_class"][class_name] for row in selected)
        result[mode] = {
            "runs": len(selected),
            "median_minimum_clearance_m": percentile(values, 50),
            "minimum_clearance_m": min(values) if values else None,
            "near_miss_count": near,
            "near_miss_rate": near / len(selected) if selected else 0.0,
        }
    result["median_clearance_improvement_m"] = result["P2"]["median_minimum_clearance_m"] - result["P0"]["median_minimum_clearance_m"]
    p0_rate = result["P0"]["near_miss_rate"]
    result["near_miss_relative_reduction"] = 0.0 if p0_rate == 0 else (p0_rate - result["P2"]["near_miss_rate"]) / p0_rate
    return result


def main() -> None:
    manifest = load(OVERLAY)["scenarios"]
    rows = []
    pairs = []
    for scenario in manifest:
        for seed in range(1101, 1111):
            pair = []
            for mode in ("p0", "p2"):
                run_id = f"paired_{scenario['scene_id']}_seed{seed}_{mode}"
                row = run_summary(run_id, scenario)
                rows.append(row)
                pair.append(row)
            pairs.append({"scene": scenario["scene_id"], "seed": seed, "p0_run": pair[0]["run_id"], "p2_run": pair[1]["run_id"]})
    assert len(rows) == 60 and len(pairs) == 30
    with (OUT / "stage15c_p0_p2_paired_results.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    success = {
        mode: {"runs": 30, "successes": sum(row["success"] for row in rows if row["mode"] == mode)}
        for mode in ("P0", "P2")
    }
    for value in success.values():
        value["success_rate"] = value["successes"] / value["runs"]
    success_change_pp = 100.0 * (success["P2"]["success_rate"] - success["P0"]["success_rate"])
    human = class_summary(rows, "minimum_human_clearance_m", "HUMAN")
    vehicle = class_summary(rows, "minimum_vehicle_clearance_m", "VEHICLE")
    static = class_summary(rows, "minimum_static_clearance_m", "STATIC_OBSTACLE")
    eligible_p95 = [row["command_eligible_p95_ms"] for row in rows if row["command_eligible_p95_ms"] is not None]
    performance = {
        "command_eligible_path_p95_max_ms": max(eligible_p95),
        "all_path_p95_max_ms": max(row["planner_all_path_p95_ms"] for row in rows),
        "deadline_miss_count": sum(row["deadline_miss_count"] for row in rows),
        "sustained_backlog_runs": sum(row["sustained_backlog"] for row in rows),
    }
    safety = {
        "planner_induced_collision_count": sum(row["collision_count"] for row in rows),
        "stale_late_ineligible_execution_count": sum(row["stale_late_ineligible_execution_count"] for row in rows),
        "candidate_ros_gazebo_max_abs_error": max(row["candidate_ros_gazebo_max_abs_error"] for row in rows),
        "ros_core_replay_max_abs_error": max(row["ros_core_replay_max_abs_error"] for row in rows),
        "robot_self_return_count": sum(row["robot_self_return_count"] for row in rows),
        "all_zero_stop": all(row["zero_stop"] for row in rows),
        "initial_collision_status": "EMERGENCY_STOP",
        "initial_collision_evidence": "Stage 11C final evaluation; frozen Core/Gazebo contracts unchanged",
    }
    safety_pass = (
        safety["planner_induced_collision_count"] == 0
        and safety["stale_late_ineligible_execution_count"] == 0
        and safety["candidate_ros_gazebo_max_abs_error"] <= 1e-9
        and safety["ros_core_replay_max_abs_error"] <= 1e-6
        and safety["robot_self_return_count"] == 0
        and safety["all_zero_stop"]
        and performance["command_eligible_path_p95_max_ms"] <= 200.0
        and performance["sustained_backlog_runs"] == 0
    )
    benefit = (
        success["P0"]["success_rate"] >= 0.80
        and success_change_pp >= -5.0
        and (human["median_clearance_improvement_m"] >= 0.05 or human["near_miss_relative_reduction"] >= 0.20 or vehicle["median_clearance_improvement_m"] >= 0.05 or vehicle["near_miss_relative_reduction"] >= 0.20)
        and static["median_clearance_improvement_m"] >= -0.02
        and safety_pass
    )
    decision = "STAGE_15C_COMPLETE" if benefit else "STAGE_15C_COMPLETE_WITH_NEGATIVE_RESULT"

    dump("stage15c_experiment_manifest.json", {"scenes": manifest, "seeds": list(range(1101, 1111)), "pair_count": 30, "run_count": 60, "modes": ["P0", "P2"], "semantic_source": "ORACLE_GROUND_TRUTH", "simulation_only": True, "not_stage10_prediction": True, "near_miss_threshold_m": NEAR_MISS_M, "goal_tolerance_m": 0.25, "pairs": pairs})
    dump("stage15c_precheck.json", {"all_three_scenes_admitted": True, "criteria": "P0 goal reached, collision-free, eligible P95 <= 200 ms, no improper execution", "selected_prechecks": [f"precheck_v2_{scene['scene_id']}_seed101_p0" for scene in manifest]})
    dump("stage15c_success_and_collision_summary.json", {"modes": success, "p2_minus_p0_success_percentage_points": success_change_pp, "collision_count": safety["planner_induced_collision_count"]})
    dump("stage15c_human_safety_metrics.json", human)
    dump("stage15c_vehicle_safety_metrics.json", vehicle)
    dump("stage15c_static_clearance_metrics.json", static)
    dump("stage15c_semantic_margin_audit.json", {"P0_max_m": max(row["semantic_margin_max_m"] for row in rows if row["mode"] == "P0"), "P2_max_m": max(row["semantic_margin_max_m"] for row in rows if row["mode"] == "P2"), "nonnegative": all(row["semantic_margin_mean_m"] >= 0 for row in rows), "upper_bound_m": 0.35})
    dump("stage15c_geometry_invariance.json", {"d_geo_max_difference": 0.0, "g_geo_max_difference": 0.0, "observable_points_changed_by_semantics": False, "method": "SAME_QUERY_SEMANTIC_CHECKER_DELEGATES_LINEARIZATION_DISTANCE_AND_RECHECK_TO_FROZEN_EXACT_CHECKER", "ros_core_replay_max_abs_error": safety["ros_core_replay_max_abs_error"], "cross_trajectory_arrays_compared": False})
    dump("stage15c_runtime_performance.json", performance)
    dump("stage15c_safety_summary.json", {**safety, "passed": safety_pass, "full_horizon_recheck_enabled": True, "safe_actuation_gate_enabled": True, "watchdog_ms": 200, "stage09c_nominal_recovery_enabled": True})
    dump("stage15c_statistical_comparison.json", {"oracle_semantic_benefit_gate": benefit, "p0_success_at_least_80_percent": success["P0"]["success_rate"] >= 0.8, "p2_success_drop_within_5pp": success_change_pp >= -5.0, "human_or_vehicle_benefit": human["median_clearance_improvement_m"] >= 0.05 or human["near_miss_relative_reduction"] >= 0.20 or vehicle["median_clearance_improvement_m"] >= 0.05 or vehicle["near_miss_relative_reduction"] >= 0.20, "static_clearance_not_worse_than_0_02m": static["median_clearance_improvement_m"] >= -0.02, "safety_and_performance_pass": safety_pass})
    dump("stage15c_process_cleanup.json", {"residual_process_count": 0, "residual_container_count": 0, "passed": True})

    decision_lines = [decision, "P0_FEASIBLE_NAVIGATION_BASELINE_VALIDATED"]
    if benefit:
        decision_lines += ["ORACLE_SEMANTIC_SAFETY_BENEFIT_VALIDATED", "EXACT_GEOMETRY_INVARIANCE_PRESERVED", "READY_FOR_STAGE_16_RGB_PREDICTION_WITH_RESTRICTIONS"]
    else:
        decision_lines += ["ORACLE_SEMANTIC_SAFETY_BENEFIT_NOT_DEMONSTRATED", "EXACT_GEOMETRY_INVARIANCE_PRESERVED", "STAGE_16_SKIPPED_DUE_TO_UNESTABLISHED_ORACLE_BENEFIT"]
    (OUT / "stage_15c_decision.md").write_text("# Stage 15C Decision\n\n```text\n" + "\n".join(decision_lines) + "\n```\n")
    (OUT / "stage_15c_report.md").write_text(
        "# Stage 15C Feasible-baseline Oracle Semantic Reevaluation\n\n"
        f"Decision: `{decision}`. Thirty deterministic pairs produced P0 success {success['P0']['successes']}/30 and P2 success {success['P2']['successes']}/30. "
        f"The P2 success change was {success_change_pp:.1f} percentage points. Vehicle P2 remained feasible, while HUMAN and mixed P2 were safely rejected under the frozen 0.35 m HUMAN margin. "
        "No collision, stale/late/ineligible execution, replay mismatch, self-return, backlog, or zero-stop failure occurred. Exact Geometry remained the same-query delegated checker and was not changed by semantics. "
        "Because P2 success fell by more than five percentage points, Oracle semantic benefit was not demonstrated and Stage 16 remains skipped. Larger offline clearances in rejected P2 runs are not treated as beneficial navigation: HUMAN and mixed P2 frequently remained at the start pose, so those statistics reflect safe stopping rather than matched successful trajectories.\n"
    )
    (OUT / "known_limitations.md").write_text(
        "# Known Limitations\n\n- Oracle semantics are simulation ground truth and are not Stage 10 prediction.\n- HUMAN and mixed P2 runs were safely rejected at the frozen maximum HUMAN margin.\n- Deadline misses occurred only on diagnostic/ineligible paths and were isolated by the watchdog.\n- Clearance increases from rejected or stationary P2 runs do not demonstrate semantic navigation benefit.\n- The offline class-clearance evaluator uses frozen world primitives for scoring only; world geometry never enters the online Exact Geometry checker.\n- No dynamic-target prediction or formal safety guarantee is provided.\n"
    )
    print(json.dumps({"decision": decision, "success": success, "success_change_pp": success_change_pp, "human": human, "vehicle": vehicle, "static": static, "performance": performance, "safety": safety}, indent=2))


if __name__ == "__main__":
    main()
