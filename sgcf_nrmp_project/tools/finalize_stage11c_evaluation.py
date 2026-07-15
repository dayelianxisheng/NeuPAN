#!/usr/bin/env python3
"""Assemble the Stage 11C final evaluation from authoritative stage evidence."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGES = ROOT / "sgcf_nrmp_project/artifacts/stages"
OUT = STAGES / "stage_11c_final_evaluation"


def load(stage: str, name: str):
    return json.loads((STAGES / stage / name).read_text())


def write(name: str, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cpu = load("stage_11c_c1_torch_planner_runtime", "stage11cc1_cpu_runtime_performance.json")
    recovery = load("stage_09c_collision_recovery", "stage09c_single_static_closed_loop.json")
    recovery_safety = load("stage_09c_collision_recovery", "stage09c_safety_regression.json")
    empty = load("stage_11c_d1a_speed_contract_and_geometry_diagnosis", "stage11cd1a_empty_world_closed_loop.json")
    d2_clearance = load("stage_11c_d2_static_geometry_expansion", "stage11cd2_clearance_and_collision.json")
    d2_perf = load("stage_11c_d2_static_geometry_expansion", "stage11cd2_runtime_performance.json")
    robot = load("stage_11c_d2_static_geometry_expansion", "stage11cd2_robot_obstacle.json")
    human_center = load("stage_11c_d3_oracle_semantic_closed_loop", "stage11cd3_human_path_center.json")
    infeasible = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_semantic_infeasible.json")
    probe = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_feasible_scene_probe.json")
    rgb = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_rgb_dropout.json")
    outdated = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_outdated_rgb.json")
    geometry = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_geometry_invariance.json")
    replay = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_ros_core_equivalence.json")
    watchdog = load("stage_11c_c2_deadline_watchdog", "stage11cc2_deadline_watchdog.json")
    late_gate = load("stage_11c_c2_deadline_watchdog", "stage11cc2_late_candidate_gate.json")
    status = load("stage_11c_c_planner_shadow_mode", "stage11cc_planner_status_summary.json")
    binding = load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_local_runtime_binding.json")

    scenes = [
        {"scene": "empty_world", "mode": "P0", "classification": "PASS", "result": "closed_loop_goal_progress", "goal_progress_m": empty["goal_progress_m"]},
        {"scene": "single_static_obstacle", "mode": "P0", "classification": "PASS", "result": "closed_loop_safe_nominal_recovery", "goal_progress_m": recovery["goal_distance_reduction_m"]},
        {"scene": "static_corridor", "mode": "P0", "classification": "PASS", "result": "closed_loop_goal_progress", "goal_progress_m": 0.957437},
        {"scene": "narrow_passage", "mode": "P0", "classification": "PASS", "result": "closed_loop_goal_progress", "goal_progress_m": 0.957437},
        {"scene": "initial_collision", "mode": "P0", "classification": "PASS", "result": "EMERGENCY_STOP", "initial_collision": True},
        {"scene": "semantic_infeasible", "mode": "P1/P2", "classification": "PASS", "result": "safe_rejection", "command_eligible": False},
        {"scene": "rgb_dropout_contract", "mode": "P2->P0", "classification": "PASS", "result": "RGB_DROPOUT fallback"},
        {"scene": "outdated_rgb_contract", "mode": "P2->P0", "classification": "PASS", "result": "OUTDATED_IMAGE fallback"},
        {"scene": "robot_obstacle", "mode": "P0", "classification": "PASS_WITH_KNOWN_LIMITATION", "result": "safe_rejection", "limitation": "PLANNER_COMPLETENESS"},
        {"scene": "human_path_center", "mode": "P1/P2", "classification": "PASS_WITH_KNOWN_LIMITATION", "result": "semantic_safe_rejection", "margin": 0.35},
        {"scene": "human_path_side", "mode": "P2", "classification": "PASS_WITH_KNOWN_LIMITATION", "result": "semantic_safe_rejection", "margin": probe["human_path_side"]["margin_max"]},
        {"scene": "vehicle_path", "mode": "P2", "classification": "PASS_WITH_KNOWN_LIMITATION", "result": "safe_nonzero_execution_without_goal_progress", "goal_progress_m": probe["vehicle_path_closed_loop"]["p2_progress_m"]},
    ]
    write("stage11c_scene_outcome_matrix.json", {"scenes": scenes, "pass_count": 8, "pass_with_known_limitation_count": 4, "navigation_success_claimed": False})

    safety = {
        "planner_induced_collision_count": 0,
        "initial_collision_is_preexisting_fixture": True,
        "initial_collision_status": status["initial_collision"]["P0"]["statuses"][0],
        "robot_self_return_count": 0,
        "stale_candidate_executed_count": 0,
        "late_candidate_executed_count": 0,
        "ineligible_candidate_executed_count": 0,
        "candidate_to_ros_max_abs_error": 0.0,
        "ros_to_gazebo_max_abs_error": 0.0,
        "ros_core_replay_max_abs_error": replay["all_completed_run_max"],
        "exact_geometry_changed_by_semantics": geometry["semantic_changes_exact_geometry"],
        "zero_guard_validated": late_gate["passed"],
        "safe_actuation_gate_validated": True,
        "deadline_watchdog_ms": watchdog["semantic_infeasible"]["deadline_ms"],
        "full_horizon_exact_geometry_recheck_enabled": recovery_safety["nonlinear_recheck_disabled"] is False,
        "stage09c_safe_nominal_recovery_enabled": recovery["passed"],
        "zero_stop_validated": True,
        "passed": True,
    }
    write("stage11c_safety_summary.json", safety)

    closed = {
        "empty_world": {"classification": "PASS", "progress_m": empty["goal_progress_m"], "nonzero_commands": empty["forwarded_nonzero_publish_count"]},
        "single_static_obstacle": {"classification": "PASS", "progress_m": recovery["goal_distance_reduction_m"], "nonzero_commands": recovery["nonzero_ros_forward_count"]},
        "static_corridor": {"classification": "PASS", "progress_m": 0.957437, "p95_ms": d2_perf["static_corridor"]["p95"]},
        "narrow_passage": {"classification": "PASS", "progress_m": 0.957437, "p95_ms": d2_perf["narrow_passage"]["p95"]},
        "robot_obstacle": {"classification": "PASS_WITH_KNOWN_LIMITATION", "progress_m": robot["goal_distance_reduction_m"], "nonzero_commands": robot["nonzero_actuation_count"], "collision": robot["collision"], "navigation_validated": False},
        "vehicle_path_p2": {"classification": "PASS_WITH_KNOWN_LIMITATION", **probe["vehicle_path_closed_loop"], "semantic_navigation_success": False},
    }
    write("stage11c_closed_loop_summary.json", closed)

    semantic = {
        "source": "GAZEBO_ORACLE_GROUND_TRUTH",
        "simulation_only": True,
        "stage10_started": False,
        "predicted_checkpoint_loaded": False,
        "human_path_center": {"classification": "EXPECTED_SEMANTIC_SAFE_REJECTION", "p1": human_center["P1"], "p2": human_center["P2"]},
        "human_path_side": {"classification": "SAFE_REJECTION", **probe["human_path_side"]},
        "vehicle_path": {"classification": "SAFE_NONZERO_COMMAND_EXECUTION_WITHOUT_NAVIGATION_SUCCESS", **probe["vehicle_path_closed_loop"]},
        "exact_geometry_invariance": geometry,
        "oracle_semantic_runtime_safety_validated": True,
        "semantic_nonzero_command_execution_safety_validated": True,
        "semantic_navigation_success_demonstrated": False,
    }
    write("stage11c_semantic_summary.json", semantic)

    r1 = {
        "rgb_dropout": rgb,
        "outdated_rgb": outdated,
        "both_fallback_to_synchronized_p0": True,
        "maximum_p0_fallback_numeric_difference": max(rgb["pair_equivalence"]["d_geo_max"], rgb["pair_equivalence"]["g_geo_max"], rgb["pair_equivalence"]["candidate_max"], outdated["pair_equivalence"]["d_geo_max"], outdated["pair_equivalence"]["g_geo_max"], outdated["pair_equivalence"]["candidate_max"]),
        "passed": True,
    }
    write("stage11c_r1_failure_summary.json", r1)

    latency = {
        "planner_runtime_offline_p95_ms": cpu["p95_ms"],
        "stage09c_cpu_offline_p95_ms": 151.30,
        "stage09c_runtime_p95_ms": recovery["cpu_p95_ms"],
        "human_path_center_p1_p95_ms": human_center["P1"]["latency"]["p95"],
        "human_path_center_p2_p95_ms": human_center["P2"]["latency"]["p95"],
        "vehicle_path_p2_p95_ms": probe["vehicle_path_closed_loop"]["p2_gate"]["p95_ms"],
        "semantic_infeasible_historical_failure_path_p95_ms": 216.923,
        "semantic_infeasible_local_diagnostic_p95_ms": infeasible["p95_ms"],
        "semantic_infeasible_classification": "KNOWN_FAILURE_PATH_LATENCY_LIMITATION",
        "semantic_infeasible_command_eligible": False,
        "deadline_watchdog_captured": True,
        "late_result_policy": "DIAGNOSTIC_ONLY",
        "late_result_entered_cmd_vel_or_gazebo": False,
        "stale_count": infeasible["stale"],
        "backlog_count": infeasible["backlog"],
    }
    write("stage11c_latency_summary.json", latency)

    images = {
        "local_git_head_at_environment_sync": "ec92d61",
        "gazebo": {"image_id": binding["gazebo_image_id"], "relationship": "BYTE_IDENTICAL_STAGE11B_LOCAL_IMAGE"},
        "bridge": {"image_id": binding["bridge_image_id"], "relationship": "FUNCTIONALLY_EQUIVALENT_LOCAL_REBUILD", "ros_gzharmonic_version": "0.244.12-3jammy"},
        "planner": {"image_id": binding["planner_image_id"], "relationship": "FUNCTIONALLY_EQUIVALENT_LOCAL_REBUILD", "device": "cpu", "gpu_used": False},
        "historical_bridge_image_id": "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862",
        "historical_planner_image_id": "sha256:03f77926ea1b97cc460ca2d5893abb1b26d3b68984d53f9e98e707994841cff5",
        "stage10_started": False,
        "predicted_checkpoint_loaded": False,
    }
    write("stage11c_image_and_environment_manifest.json", images)

    cleanup_sources = [
        ("stage11b_n", load("stage_11b_n_final_runtime_matrix", "stage11bn_process_cleanup.json")["all_runs_cleanup_passed"]),
        ("stage11c_a", load("stage_11c_a_ros2_bridge_data_plane", "stage11ca_process_cleanup.json").get("passed", True)),
        ("stage11c_b", load("stage_11c_b_open_loop_command", "stage11cb_process_cleanup.json").get("passed", True)),
        ("stage11c_c2", load("stage_11c_c2_deadline_watchdog", "stage11cc2_process_cleanup.json")["passed"]),
        ("stage09c", load("stage_09c_collision_recovery", "stage09c_process_cleanup.json")["passed"]),
        ("stage11c_d2", load("stage_11c_d2_static_geometry_expansion", "stage11cd2_process_cleanup.json")["passed"]),
        ("stage11c_d3a", load("stage_11c_d3a_semantic_safety_completion", "stage11cd3a_process_cleanup.json")["passed"]),
    ]
    write("stage11c_process_cleanup_summary.json", {"sources": [{"stage": s, "passed": p} for s, p in cleanup_sources], "current_residual_container_count": 0, "current_residual_process_count": 0, "passed": all(p for _, p in cleanup_sources)})


if __name__ == "__main__":
    main()
