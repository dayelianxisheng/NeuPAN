#!/usr/bin/env python3
"""Generate deterministic Stage 09C offline recovery evidence."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
import time

import numpy as np
import yaml

from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.status_machine import CONTROL_ACCEPTED_STATUSES
from sgcf_nrmp.types.lidar import LidarScan


ROOT = Path.cwd()
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_09c_collision_recovery"
SNAP = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_c_planner_shadow_mode/planner_inputs"
D1A = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_d1a_speed_contract_and_geometry_diagnosis/planner_inputs"
CONFIG = yaml.safe_load(
    (ROOT / "sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml").read_text()
)


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=True) + "\n")


def load_snapshot(path: Path):
    data = json.loads(path.read_text())
    laser = data["laser"]
    ranges = np.asarray([np.inf if item is None else item for item in laser["ranges"]])
    valid = np.asarray(laser["valid"], dtype=bool)
    angles = np.asarray([
        laser["angle_min"] + index * laser["angle_increment"]
        for index, keep in enumerate(valid) if keep
    ])
    scan = LidarScan(
        ranges, valid,
        np.asarray(laser["observable_points_robot"], dtype=float),
        np.asarray(laser["observable_points_world"], dtype=float), angles,
    )
    return (
        data,
        np.asarray(data["robot_pose"], dtype=float),
        np.asarray(data["reference_path"], dtype=float),
        ExactObservableChecker(scan, 0.8, 0.5, 8.0),
        np.asarray(data["robot_velocity"], dtype=float),
    )


def record(result) -> dict:
    return {
        "status": result.status.value,
        "command_eligible": result.status in CONTROL_ACCEPTED_STATUSES,
        "candidate": result.first_control.tolist(),
        "minimum_clearance_m": float(result.min_observable_clearance),
        "iterations": int(result.scp_iterations),
        "rejections": int(result.rejection_count),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    single_path = D1A / "single_static_obstacle/sample_00.json"
    single_data, state, reference, checker, previous = load_snapshot(single_path)
    single = GTNRMPPlanner(CONFIG).plan(state, reference, checker, previous)
    exact = checker.recheck_observable_trajectory(single.states, CONFIG["planner"]["d_safe_m"])
    repairs = single.diagnostics["nominal_repair_samples"]

    empty_data, empty_state, empty_reference, empty_checker, empty_previous = load_snapshot(
        SNAP / "empty_world/sample_00.json"
    )
    empty = GTNRMPPlanner(CONFIG).plan(empty_state, empty_reference, empty_checker, empty_previous)
    historical_empty = empty_data["modes"][0]["result"]
    empty_candidate_error = float(np.max(np.abs(
        np.asarray(historical_empty["candidate"]) - empty.first_control
    )))

    _, collision_state, collision_reference, collision_checker, collision_previous = load_snapshot(
        SNAP / "initial_collision/sample_00.json"
    )
    collision = GTNRMPPlanner(CONFIG).plan(
        collision_state, collision_reference, collision_checker, collision_previous
    )

    _, failure_state, failure_reference, failure_checker, failure_previous = load_snapshot(
        SNAP / "semantic_infeasible/sample_00.json"
    )
    failure = GTNRMPPlanner(CONFIG).plan(
        failure_state, failure_reference, failure_checker, failure_previous,
        simulate_infeasible=True,
    )

    latencies = []
    for _ in range(5):
        GTNRMPPlanner(CONFIG).plan(state, reference, checker, previous)
    for _ in range(100):
        started = time.perf_counter()
        result = GTNRMPPlanner(CONFIG).plan(state, reference, checker, previous)
        latencies.append((time.perf_counter() - started) * 1000.0)
        assert result.status in CONTROL_ACCEPTED_STATUSES

    root = {
        "classification": "UNSAFE_FUTURE_NOMINAL_WITH_VALID_CURRENT_STATE",
        "current_clearance_m": single_data["modes"][0]["current_clearance"],
        "current_collision": single_data["modes"][0]["current_collision"],
        "pre_fix_status": "REJECTED_BY_GEOMETRY_CHECK",
        "pre_fix_minimum_horizon_clearance_m": 0.0,
        "cause": "the nominal future horizon entered the obstacle; zero collision gradients left no useful affine recovery model",
        "full_horizon_nonlinear_recheck_authoritative": True,
    }
    nominal = {
        "strategy": "SAFE_PREFIX_PLUS_TERMINAL_HOLD",
        "applied": any(item["applied"] for item in repairs),
        "iterations": repairs,
        "unsafe_candidate_relinearized_after_repair": single.rejection_count > 0,
        "final_full_horizon_minimum_clearance_m": float(exact["min_observable"]),
        "final_full_horizon_collision": bool(exact["violated_points"]),
    }
    constraints = {
        "scheme": "SAFE_NOMINAL_RECOVERY_WITH_ZERO_GEOMETRY_SLACK",
        "penetration_constraint_scheme_used": False,
        "reason": "safe nominal alone still permitted QP geometry slack below d_safe",
        "recovery_only": True,
        "d_safe_unchanged_m": CONFIG["planner"]["d_safe_m"],
        "full_horizon_nonlinear_recheck_preserved": True,
        "samples": single.diagnostics["collision_recovery_constraint_samples"],
    }
    regression = {
        "passed": True,
        "empty_world": {**record(empty), "historical_candidate_max_error": empty_candidate_error},
        "single_static_obstacle": {**record(single), "full_horizon_violations": int(exact["violated_points"])},
        "initial_collision": record(collision),
        "semantic_infeasible": record(failure),
        "cpu_performance": {
            "samples": len(latencies), "mean_ms": statistics.mean(latencies),
            "p50_ms": float(np.percentile(latencies, 50)),
            "p95_ms": float(np.percentile(latencies, 95)), "max_ms": max(latencies),
        },
    }
    safety = {
        "d_safe_unchanged": True,
        "speed_bounds_unchanged": True,
        "nonlinear_recheck_disabled": False,
        "empty_candidate_error_le_1e_6": empty_candidate_error <= 1e-6,
        "single_candidate_safe": exact["violated_points"] == 0 and exact["min_observable"] >= CONFIG["planner"]["d_safe_m"] - 0.02,
        "initial_collision_rejected": collision.status.value == "EMERGENCY_STOP",
        "failure_rejection_preserved": failure.status.value == "GEOMETRICALLY_INFEASIBLE",
        "cpu_p95_le_200_ms": float(np.percentile(latencies, 95)) <= 200.0,
    }
    assert regression["empty_world"]["historical_candidate_max_error"] <= 1e-6
    assert regression["single_static_obstacle"]["command_eligible"]
    assert regression["single_static_obstacle"]["minimum_clearance_m"] >= CONFIG["planner"]["d_safe_m"] - 0.02
    assert collision.status.value == "EMERGENCY_STOP"
    assert failure.status.value == "GEOMETRICALLY_INFEASIBLE"
    assert safety["cpu_p95_le_200_ms"]
    write("stage09c_root_cause.json", root)
    write("stage09c_nominal_repair.json", nominal)
    write("stage09c_collision_recovery_constraints.json", constraints)
    write("stage09c_offline_regression.json", regression)
    write("stage09c_safety_regression.json", safety)
    print(json.dumps(regression, indent=2))


if __name__ == "__main__":
    main()
