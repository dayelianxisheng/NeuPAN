"""Trust-region SCP planner driven only by exact observable geometry."""

from __future__ import annotations

import time
import numpy as np

from sgcf_nrmp.planner.angle_utils import wrap_angle
from sgcf_nrmp.planner.dynamics import rollout
from sgcf_nrmp.planner.fallback import fallback_control
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.qp_problem import PersistentPlannerQP
from sgcf_nrmp.planner.solver_result import PlannerStatus, SolverResult
from sgcf_nrmp.planner.solver_result import GeometryRecheckReason
from sgcf_nrmp.planner.status_machine import CONTROL_ACCEPTED_STATUSES, semantic_failure_status
from sgcf_nrmp.planner.trust_region import TrustRegion


class GTNRMPPlanner:
    def __init__(self, config: dict):
        self.config = config; self.T = int(config["planner"]["horizon"]); self.dt = float(config["planner"]["dt_s"])
        self.previous_controls = None; self.last_safe_control = None; self.qp = PersistentPlannerQP(config)

    def _initial_controls(self, state, reference):
        if self.previous_controls is not None:
            return np.vstack((self.previous_controls[1:], self.previous_controls[-1:]))
        controls = []; bounds = self.config["bounds"]
        for k in range(self.T):
            delta = reference[k + 1, :2] - reference[k, :2]
            heading = np.arctan2(delta[1], delta[0]) if np.linalg.norm(delta) > 1e-8 else reference[k, 2]
            v = np.linalg.norm(delta) / self.dt; omega = wrap_angle(heading - reference[k, 2]) / self.dt
            controls.append([np.clip(v, bounds["v_min_mps"], bounds["v_max_mps"]), np.clip(omega, bounds["omega_min_radps"], bounds["omega_max_radps"])])
        return np.asarray(controls)

    def _result(self, status, state, controls, slack, **kwargs):
        return SolverResult(status=status, states=rollout(state, controls, self.dt), controls=controls, slack=slack, **kwargs)

    def _recheck_record(self, iteration, nominal, candidate, qp_controls, qp_slack,
                        distances, gradients, check, trust, semantic_margins):
        exact=np.asarray(check["observable"],float); linearized=np.asarray(distances,float)+np.einsum("ij,ij->i",np.asarray(gradients,float),candidate-nominal)
        offending=list(check.get("offending_indices",np.flatnonzero(exact<self.config["planner"]["d_safe_m"]-1e-4).tolist()))
        trust_state=np.abs(candidate[1:]-nominal[1:]); trust_control=np.abs(qp_controls-self.qp.nominal_controls.value)
        trust_violation=bool(np.any(trust_state[:,:2]>trust.xy_m+1e-5) or np.any(trust_state[:,2]>trust.yaw_rad+1e-5) or np.any(trust_control[:,0]>trust.linear_velocity_mps+1e-5) or np.any(trust_control[:,1]>trust.angular_velocity_radps+1e-5))
        mismatch=any(linearized[index]>=self.config["planner"]["d_safe_m"]-1e-4 and exact[index]<self.config["planner"]["d_safe_m"]-1e-4 for index in offending)
        reasons=[]
        if check.get("nonfinite_indices"): reasons.append(GeometryRecheckReason.NONFINITE_GEOMETRY.value)
        if trust_violation: reasons.append(GeometryRecheckReason.TRUST_REGION_VIOLATION.value)
        if mismatch: reasons.append(GeometryRecheckReason.LINEARIZATION_MISMATCH.value)
        for index in offending:
            if exact[index]<=0:
                reasons.append((GeometryRecheckReason.NEXT_STATE_COLLISION if index==1 else GeometryRecheckReason.HORIZON_STATE_COLLISION).value)
        if offending: reasons.append(GeometryRecheckReason.CLEARANCE_BELOW_THRESHOLD.value)
        reasons=list(dict.fromkeys(reasons))
        index=offending[0] if offending else None
        return {
            "iteration":iteration,"reason_codes":reasons,"primary_reason":reasons[0] if reasons else None,
            "offending_horizon_index":index,"offending_indices":offending,
            "state":candidate[index].tolist() if index is not None else None,
            "candidate_control":qp_controls[max(0,index-1)].tolist() if index is not None else None,
            "candidate_trajectory":candidate.tolist(),"minimum_exact_observable_clearance":float(check["min_observable"]),
            "required_clearance":float(self.config["planner"]["d_safe_m"]),"semantic_margin":np.asarray(semantic_margins,float).tolist(),
            "linearized_clearance":linearized.tolist(),"exact_rechecked_clearance":exact.tolist(),
            "linearization_error":(exact-linearized).tolist(),"trust_region":trust.__dict__.copy(),
            "trust_region_violation":trust_violation,"solver_status":self.qp.last_solve_diagnostics.get("solver_status"),
            "slack":np.asarray(qp_slack,float).tolist(),
        }

    def plan(self, state, reference, checker: ExactObservableChecker, previous_control=None, simulate_timeout=False, simulate_infeasible=False, trust_override: TrustRegion | None = None):
        cycle_started = time.perf_counter()
        timing = {"observable_distance_gradient_ms": [], "parameter_update_ms": [], "solve_wall_ms": [], "osqp_internal_ms": [], "observable_recheck_ms": [], "fallback_status_selection_ms": [], "nominal_states_samples": [], "exact_distance_samples": [], "exact_gradient_samples": [], "gradient_valid_samples": [], "qp_status_samples": [], "solver_detail_samples": [], "geometry_recheck_samples": []}
        state = np.asarray(state, float); previous_control = np.zeros(2) if previous_control is None else np.asarray(previous_control, float)
        semantic_context=dict(getattr(checker,"semantic_context",{})); timing["semantic_context"]=semantic_context.copy()
        controls = self._initial_controls(state, reference); bounds = self.config["bounds"]; prior = previous_control.copy()
        for control in controls:
            control[0] = np.clip(control[0], prior[0] + bounds["acceleration_min_mps2"] * self.dt, prior[0] + bounds["acceleration_max_mps2"] * self.dt)
            control[1] = np.clip(control[1], prior[1] + bounds["angular_acceleration_min_radps2"] * self.dt, prior[1] + bounds["angular_acceleration_max_radps2"] * self.dt); prior = control.copy()
        nominal = rollout(state, controls, self.dt); trust = trust_override or TrustRegion.from_dict(self.config["trust_region"])
        total_time = 0.; rejections = 0; last_status = PlannerStatus.MAX_ITERATIONS; last_candidate = None
        started = time.perf_counter(); current = checker.recheck_observable_trajectory(state[None, :], self.config["planner"]["d_safe_m"]); timing["observable_recheck_ms"].append((time.perf_counter() - started) * 1000.)
        if current["min_observable"] < self.config["planner"]["emergency_distance_m"]:
            timing["geometry_recheck_samples"].append({"primary_reason":GeometryRecheckReason.CURRENT_STATE_COLLISION.value,"state":state.tolist(),"minimum_exact_observable_clearance":current["min_observable"],"required_clearance":self.config["planner"]["emergency_distance_m"]})
            zeros = np.zeros((self.T, 2)); timing["online_planner_ms"] = (time.perf_counter() - cycle_started) * 1000.
            return self._result(PlannerStatus.EMERGENCY_STOP, state, zeros, np.zeros(self.T), min_observable_clearance=current["min_observable"], diagnostics=timing)
        for iteration in range(1, int(self.config["planner"]["scp_iterations"]) + 1):
            started = time.perf_counter(); distances, gradients, valid = checker.linearization(nominal); timing["observable_distance_gradient_ms"].append((time.perf_counter() - started) * 1000.); timing["nominal_states_samples"].append(nominal.tolist()); timing["exact_distance_samples"].append(distances.tolist()); timing["exact_gradient_samples"].append(gradients.tolist()); timing["gradient_valid_samples"].append(valid.tolist())
            semantic_margins=checker.semantic_margins(nominal) if hasattr(checker,"semantic_margins") else np.zeros(len(nominal)); timing.setdefault("semantic_margin_ms",[]).append(float(getattr(checker,"last_semantic_latency_ms",0.))); timing.setdefault("semantic_margin_samples",[]).append(semantic_margins.tolist())
            timing["parameter_update_ms"].append(self.qp.update(state, reference, nominal, controls, previous_control, distances, gradients, valid, trust, semantic_margins))
            status, values, elapsed, internal = self.qp.solve(simulate_timeout, simulate_infeasible); timing["solve_wall_ms"].append(elapsed); timing["osqp_internal_ms"].append(internal); timing["qp_status_samples"].append(status.value); timing["solver_detail_samples"].append(dict(self.qp.last_solve_diagnostics)); total_time += elapsed; last_status = status
            if values is None:
                raw_status=status
                if status==PlannerStatus.INFEASIBLE:
                    if semantic_context.get("semantic_enabled") and np.any(np.asarray(semantic_margins)>0):
                        geometry_planner=GTNRMPPlanner(self.config); geometry_result=geometry_planner.plan(state,reference,semantic_context["exact_checker"],previous_control)
                        allow=bool(self.config.get("semantic",{}).get("allow_semantic_degradation",False))
                        status=semantic_failure_status(status,geometry_result.status,allow)
                        timing["semantic_failure_comparison"]={"original_semantic_status":raw_status.value,"geometry_status":geometry_result.status.value,"fallback_reason":"SEMANTIC_QP_INFEASIBLE","semantic_margin_before_fallback":np.asarray(semantic_margins).tolist(),"semantic_margin_after_fallback":np.zeros_like(semantic_margins).tolist(),"control_source":"GEOMETRY_P0" if status==PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY else "SAFE_STOP"}
                        if status==PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY:
                            geometry_result.status=status; geometry_result.diagnostics.update(timing); return geometry_result
                    else: status=PlannerStatus.GEOMETRICALLY_INFEASIBLE
                self.qp.invalidate_warm_start(); self.previous_controls=None
                fallback_started=time.perf_counter(); fallback = fallback_control(status, self.last_safe_control); fallback_controls = np.tile(fallback, (self.T, 1)); timing["fallback_status_selection_ms"].append((time.perf_counter()-fallback_started)*1000.); timing["online_planner_ms"] = (time.perf_counter() - cycle_started) * 1000.
                return self._result(status, state, fallback_controls, np.zeros(self.T), solve_time_ms=total_time, scp_iterations=iteration, diagnostics=timing)
            _, qp_controls, qp_slack = values; candidate = rollout(state, qp_controls, self.dt)
            started = time.perf_counter(); check = checker.recheck_observable_trajectory(candidate, self.config["planner"]["d_safe_m"]); timing["observable_recheck_ms"].append((time.perf_counter() - started) * 1000.)
            last_candidate = (candidate, qp_controls, qp_slack, self.qp.problem.value, check)
            if check["violated_points"]:
                timing["geometry_recheck_samples"].append(self._recheck_record(iteration,nominal,candidate,qp_controls,qp_slack,distances,gradients,check,trust,semantic_margins))
                rejections += 1; trust = trust.scaled(.5); last_status = PlannerStatus.REJECTED_BY_GEOMETRY_CHECK
                if rejections > int(self.config["planner"]["max_rejections"]): break
                continue
            difference = float(np.linalg.norm(qp_controls - controls)); nominal = candidate; controls = qp_controls
            if difference < self.config["planner"]["convergence_tolerance"]: break
        timing["online_planner_ms"] = (time.perf_counter() - cycle_started) * 1000.
        if last_candidate is None:
            zeros = np.zeros((self.T, 2)); return self._result(last_status, state, zeros, np.zeros(self.T), solve_time_ms=total_time, scp_iterations=iteration, diagnostics=timing)
        candidate, controls, slack, objective, check = last_candidate
        if check["violated_points"]:
            zeros = np.zeros((self.T, 2))
            return self._result(PlannerStatus.REJECTED_BY_GEOMETRY_CHECK, state, zeros, slack, objective=objective, solve_time_ms=total_time, scp_iterations=iteration, min_observable_clearance=check["min_observable"], violated_points=check["violated_points"], rejection_count=rejections, diagnostics=timing)
        maximum = float(np.max(slack)); final_status = PlannerStatus.SOLVED_WITH_SLACK if maximum > self.config["planner"]["slack_acceptance_m"] else PlannerStatus.SOLVED_SAFE
        if semantic_context.get("explicit_failure_active"):
            timing["explicit_failure_fallback"]={"original_semantic_status":"SEMANTIC_INPUT_DISABLED","fallback_geometry_status":final_status.value,"fallback_reason":semantic_context.get("explicit_failure_reasons",[]),"semantic_margin_before_fallback":np.asarray(semantic_margins).tolist(),"semantic_margin_after_fallback":np.zeros_like(semantic_margins).tolist(),"control_source":"GEOMETRY_P0"}
            final_status=PlannerStatus.EXPLICIT_FAILURE_GEOMETRY_FALLBACK
        self.previous_controls = controls.copy(); self.last_safe_control = controls[0].copy()
        return SolverResult(status=final_status, states=candidate, controls=controls, slack=slack, objective=objective, solve_time_ms=total_time, scp_iterations=iteration, min_observable_clearance=check["min_observable"], violated_points=check["violated_points"], rejection_count=rejections, diagnostics=timing)
