"""Static-world closed loop with strict online/offline information separation."""

from __future__ import annotations

import time
import numpy as np

from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.planner.dynamics import step
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker, OfflineWorldEvaluator
from sgcf_nrmp.planner.reference import local_reference
from sgcf_nrmp.planner.solver_result import PlannerStatus
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


def run_closed_loop(planner, scene, path, config, lidar_config: LidarConfig, max_steps=120, seed=0, checker_factory=None):
    state = path[0].copy(); length = config["robot"]["footprint_length_m"]; width = config["robot"]["footprint_width_m"]
    footprint = rectangular_footprint(length, width); world_evaluator = OfflineWorldEvaluator(scene, footprint, lidar_config.range_max)
    states = [state.copy()]; controls = []; statuses = []; results = []; cycle_times = []; online_times = []; world_times = []
    world_results = []; observable_executed = []; fallback_count = 0; emergency_count = 0; rejections = 0
    rng = np.random.default_rng(seed); previous = np.zeros(2); lidar_prepare_times = []; checker_prepare_times=[]; reference_times = []; semantic_prepare={}
    termination_reason = "EPISODE_MAX_STEPS"; termination_step = 0; last_valid_action = np.zeros(2); warm_start_valid = False
    initial_scan = scene.scan(Pose2D(*map(float, state)), lidar_config, np.random.default_rng(seed))
    initial_checker = ExactObservableChecker(initial_scan, length, width, lidar_config.range_max)
    initial_observable_collision = bool(initial_checker.distance(state[None, :])[0] <= 0.0)
    initial_world = world_evaluator.evaluate_trajectory(state[None, :], initial_checker.distance(state[None, :]), config["planner"]["d_safe_m"])
    initial_collision = bool(initial_observable_collision or initial_world.world_collision)
    planner_induced_collision = False; trajectory_collision = False
    for cycle_index in range(max_steps):
        if np.linalg.norm(state[:2] - path[-1, :2]) < .25:
            termination_reason = "GOAL_REACHED_BEFORE_PLAN"; termination_step = cycle_index; break
        online_started = time.perf_counter(); started = time.perf_counter()
        scan = scene.scan(Pose2D(*map(float, state)), lidar_config, rng)
        lidar_prepare_times.append((time.perf_counter() - started) * 1000.)
        started=time.perf_counter()
        exact_checker = ExactObservableChecker(scan, length, width, lidar_config.range_max)
        checker = exact_checker if checker_factory is None else checker_factory(scan, exact_checker)
        checker_prepare_times.append((time.perf_counter()-started)*1000.)
        for key,value in getattr(checker,"preparation_timings_ms",{}).items(): semantic_prepare.setdefault(key,[]).append(float(value))
        started = time.perf_counter(); reference = local_reference(state, path, planner.T, config["planner"]["reference_speed_mps"] * planner.dt); reference_times.append((time.perf_counter() - started) * 1000.)
        result = planner.plan(state, reference, checker, previous); control = result.first_control
        online_elapsed = (time.perf_counter() - online_started) * 1000.; online_times.append(online_elapsed); cycle_times.append(online_elapsed)
        if result.status not in (PlannerStatus.SOLVED_SAFE, PlannerStatus.SOLVED_WITH_SLACK): fallback_count += 1
        if result.status == PlannerStatus.EMERGENCY_STOP: emergency_count += 1
        next_state = step(state, control, planner.dt); next_state[2] = (next_state[2] + np.pi) % (2 * np.pi) - np.pi
        executed_observable = exact_checker.distance(next_state[None, :])
        offline = world_evaluator.evaluate_trajectory(next_state[None, :], executed_observable, config["planner"]["d_safe_m"])
        world_times.append(offline.evaluation_time_ms); world_results.append(offline); observable_executed.append(float(executed_observable[0]))
        executed_collision = bool(executed_observable[0] <= 0.0)
        planner_induced_collision |= bool(not initial_collision and executed_collision)
        trajectory_collision |= bool(result.min_observable_clearance <= 0.0)
        state = next_state; states.append(state.copy()); controls.append(control.copy()); statuses.append(result.status.value); results.append(result)
        rejections += result.rejection_count; previous = control
        if result.status in (PlannerStatus.SOLVED_SAFE, PlannerStatus.SOLVED_WITH_SLACK): last_valid_action = control.copy(); warm_start_valid = planner.previous_controls is not None
        termination_step = cycle_index + 1
        if np.linalg.norm(state[:2] - path[-1, :2]) < .25: termination_reason = "GOAL_REACHED_AFTER_EXECUTE"; break
        if result.status == PlannerStatus.EMERGENCY_STOP: termination_reason = "EMERGENCY_STOP"
        elif result.status == PlannerStatus.SOLVER_TIMEOUT: termination_reason = "OSQP_OR_SOLVER_USER_LIMIT"
        elif result.status == PlannerStatus.REJECTED_BY_GEOMETRY_CHECK: termination_reason = "GEOMETRY_RECHECK_REJECTION"
        elif result.status == PlannerStatus.INFEASIBLE: termination_reason = "QP_INFEASIBLE"
        if result.status in (PlannerStatus.EMERGENCY_STOP, PlannerStatus.INFEASIBLE, PlannerStatus.SOLVER_TIMEOUT, PlannerStatus.NUMERICAL_ERROR, PlannerStatus.REJECTED_BY_GEOMETRY_CHECK): break
    states = np.asarray(states); controls = np.asarray(controls); observable = np.asarray(observable_executed) if observable_executed else np.asarray([lidar_config.range_max])
    world = np.asarray([item.minimum_world_clearance for item in world_results]) if world_results else np.asarray([lidar_config.range_max])
    success = bool(np.linalg.norm(states[-1, :2] - path[-1, :2]) < .25)
    smooth = float(np.mean(np.linalg.norm(np.diff(controls, axis=0), axis=1))) if len(controls) > 1 else 0.; length_m = float(np.sum(np.linalg.norm(np.diff(states[:, :2], axis=0), axis=1)))
    qp_iterations = [value for result in results for value in result.diagnostics.get("solve_wall_ms", [])]
    timing_keys = ("observable_distance_gradient_ms", "semantic_margin_ms", "parameter_update_ms", "solve_wall_ms", "osqp_internal_ms", "observable_recheck_ms", "fallback_status_selection_ms")
    timing = {key: [value for result in results for value in result.diagnostics.get(key, [])] for key in timing_keys}
    timing.update({"lidar_data_preparation_ms": lidar_prepare_times, "checker_and_semantic_preparation_ms":checker_prepare_times, "reference_and_control_logic_ms": reference_times, "online_equivalent_planner_ms": online_times, "offline_world_evaluation_ms": world_times}); timing.update(semantic_prepare)
    percentile = lambda values, p: float(np.percentile(values, p)) if values else 0.
    metrics = {
        "success": success, "steps": len(controls), "navigation_time_s": len(controls) * planner.dt, "path_length_m": length_m, "control_smoothness": smooth,
        "min_observable_clearance_m": float(observable.min()), "min_world_clearance_m": float(world.min()), "observable_collision": bool(np.any(observable <= 0)),
        "world_collision": bool(any(item.world_collision for item in world_results)), "partial_observation_world_risk": bool(any(item.partial_observation_world_risk for item in world_results)),
        "initial_collision": initial_collision, "planner_induced_collision": planner_induced_collision, "trajectory_collision": trajectory_collision,
        "correct_emergency_stop": bool(initial_collision and statuses and statuses[0] == PlannerStatus.EMERGENCY_STOP.value),
        "average_qp_solve_ms": float(np.mean(qp_iterations)) if qp_iterations else 0., "p95_qp_solve_ms": percentile(qp_iterations, 95), "max_qp_solve_ms": float(max(qp_iterations, default=0.)),
        "average_end_to_end_ms": float(np.mean(online_times)) if online_times else 0., "p95_end_to_end_ms": percentile(online_times, 95), "max_end_to_end_ms": float(max(online_times, default=0.)),
        "average_offline_world_evaluation_ms": float(np.mean(world_times)) if world_times else 0., "p95_offline_world_evaluation_ms": percentile(world_times, 95),
        "end_to_end_over_100ms_count": int(np.count_nonzero(np.asarray(online_times) > 100.)), "scp_iterations_mean": float(np.mean([r.scp_iterations for r in results])) if results else 0.,
        "max_slack": float(max((np.max(r.slack) for r in results), default=0.)), "geometry_recheck_rejections": rejections, "fallback_count": fallback_count, "emergency_stop_count": emergency_count,
    }
    metrics.update({"termination_reason":termination_reason,"termination_step":termination_step,"last_valid_action":last_valid_action.tolist(),"last_planner_status":statuses[-1] if statuses else "NOT_PLANNED","goal_distance_m":float(np.linalg.norm(states[-1,:2]-path[-1,:2])),"yaw_error_rad":float(abs((states[-1,2]-path[-1,2]+np.pi)%(2*np.pi)-np.pi)),"warm_start_valid":warm_start_valid,"first_cycle_online_ms":float(online_times[0]) if online_times else 0.,"steady_state_mean_ms":float(np.mean(online_times[1:])) if len(online_times)>1 else 0.,"steady_state_p50_ms":percentile(online_times[1:],50),"steady_state_p95_ms":percentile(online_times[1:],95),"steady_state_p99_ms":percentile(online_times[1:],99)})
    return {"states": states, "controls": controls, "statuses": statuses, "results": results, "cycle_times_ms": cycle_times, "timing_samples_ms": timing, "offline_world_results": world_results, "metrics": metrics}
