"""Persistent, DPP-compliant trust-region QP for SCP iterations."""

from __future__ import annotations

import time

import cvxpy as cp
import numpy as np

from sgcf_nrmp.planner.angle_utils import unwrap_reference
from sgcf_nrmp.planner.dynamics import linearize
from sgcf_nrmp.planner.solver_result import PlannerStatus, SolverFailureReason
from sgcf_nrmp.planner.trust_region import TrustRegion


class PersistentPlannerQP:
    """Build once and update only numeric Parameters thereafter."""

    def __init__(self, config: dict):
        self.config = config
        self.T = int(config["planner"]["horizon"])
        self.dt = float(config["planner"]["dt_s"])
        T = self.T

        self.states = cp.Variable((T + 1, 3), name="states")
        self.controls = cp.Variable((T, 2), name="controls")
        self.slack = cp.Variable(T, nonneg=True, name="slack")
        self.geometry_slack_max = cp.Parameter(nonneg=True, name="geometry_slack_max")
        self.initial_state = cp.Parameter(3, name="initial_state")
        self.reference = cp.Parameter((T + 1, 3), name="reference")
        self.nominal_states = cp.Parameter((T + 1, 3), name="nominal_states")
        self.nominal_controls = cp.Parameter((T, 2), name="nominal_controls")
        self.previous_control = cp.Parameter(2, name="previous_control")
        self.A = [cp.Parameter((3, 3), name=f"A_{k}") for k in range(T)]
        self.B = [cp.Parameter((3, 2), name=f"B_{k}") for k in range(T)]
        self.c = [cp.Parameter(3, name=f"c_{k}") for k in range(T)]
        self.clearance_gradient = [cp.Parameter(3, name=f"clearance_gradient_{k}") for k in range(T)]
        self.clearance_bias = cp.Parameter(T, name="clearance_bias")
        self.clearance_valid = cp.Parameter(T, nonneg=True, name="clearance_valid")
        self.d_safe = cp.Parameter(nonneg=True, name="d_safe")
        self.semantic_margin = cp.Parameter(T, nonneg=True, name="semantic_margin")
        self.trust_xy = cp.Parameter(nonneg=True, name="trust_xy")
        self.trust_yaw = cp.Parameter(nonneg=True, name="trust_yaw")
        self.trust_v = cp.Parameter(nonneg=True, name="trust_v")
        self.trust_omega = cp.Parameter(nonneg=True, name="trust_omega")
        self.v_min = cp.Parameter(name="v_min")
        self.v_max = cp.Parameter(name="v_max")
        self.omega_min = cp.Parameter(name="omega_min")
        self.omega_max = cp.Parameter(name="omega_max")
        self.accel_min = cp.Parameter(name="accel_min")
        self.accel_max = cp.Parameter(name="accel_max")
        self.alpha_min = cp.Parameter(name="alpha_min")
        self.alpha_max = cp.Parameter(name="alpha_max")

        cost = config["cost"]
        Q = np.diag(cost["track"])
        Qf = np.diag(cost["terminal"])
        R = np.diag(cost["control"])
        S = np.diag(cost["smooth"])
        P = np.diag(cost["proximal"])
        objective = 0
        constraints = [self.states[0] == self.initial_state]
        constraints += [self.slack <= self.geometry_slack_max]
        constraints += [self.controls[:, 0] >= self.v_min, self.controls[:, 0] <= self.v_max]
        constraints += [self.controls[:, 1] >= self.omega_min, self.controls[:, 1] <= self.omega_max]
        inactive_big_m = 100.0
        for k in range(T):
            constraints.append(
                self.states[k + 1] == self.A[k] @ self.states[k] + self.B[k] @ self.controls[k] + self.c[k]
            )
            constraints += [cp.abs(self.states[k + 1, :2] - self.nominal_states[k + 1, :2]) <= self.trust_xy]
            constraints += [cp.abs(self.states[k + 1, 2] - self.nominal_states[k + 1, 2]) <= self.trust_yaw]
            constraints += [cp.abs(self.controls[k, 0] - self.nominal_controls[k, 0]) <= self.trust_v]
            constraints += [cp.abs(self.controls[k, 1] - self.nominal_controls[k, 1]) <= self.trust_omega]
            # A fixed slot exists for every horizon state. Invalid slots are relaxed by M.
            constraints.append(
                self.clearance_gradient[k] @ self.states[k + 1]
                + self.clearance_bias[k] + self.slack[k]
                >= self.d_safe + self.semantic_margin[k] - inactive_big_m * (1.0 - self.clearance_valid[k])
            )
            objective += cp.quad_form(self.states[k + 1] - self.reference[k + 1], Q)
            objective += cp.quad_form(self.controls[k], R)
            objective += cp.quad_form(self.states[k + 1] - self.nominal_states[k + 1], P)
            objective += float(cost["slack"]) * cp.square(self.slack[k])
            prior = self.previous_control if k == 0 else self.controls[k - 1]
            objective += cp.quad_form(self.controls[k] - prior, S)
            constraints += [(self.controls[k, 0] - prior[0]) / self.dt >= self.accel_min]
            constraints += [(self.controls[k, 0] - prior[0]) / self.dt <= self.accel_max]
            constraints += [(self.controls[k, 1] - prior[1]) / self.dt >= self.alpha_min]
            constraints += [(self.controls[k, 1] - prior[1]) / self.dt <= self.alpha_max]
        objective += cp.quad_form(self.states[T] - self.reference[T], Qf)
        self.problem = cp.Problem(cp.Minimize(objective), constraints)
        if not self.problem.is_dcp() or not self.problem.is_qp():
            raise ValueError("planner problem is not a valid convex QP")
        if not self.problem.is_dpp():
            raise ValueError("persistent planner problem is not DPP compliant")
        self._last_primal = None
        self.solve_count = 0
        self.last_solve_diagnostics = {}
        self._set_static_parameter_values()

    def _set_static_parameter_values(self):
        bounds = self.config["bounds"]
        self.d_safe.value = float(self.config["planner"]["d_safe_m"])
        self.semantic_margin.value = np.zeros(self.T)
        self.geometry_slack_max.value = 100.0
        self.v_min.value = float(bounds["v_min_mps"])
        self.v_max.value = float(bounds["v_max_mps"])
        self.omega_min.value = float(bounds["omega_min_radps"])
        self.omega_max.value = float(bounds["omega_max_radps"])
        self.accel_min.value = float(bounds["acceleration_min_mps2"])
        self.accel_max.value = float(bounds["acceleration_max_mps2"])
        self.alpha_min.value = float(bounds["angular_acceleration_min_radps2"])
        self.alpha_max.value = float(bounds["angular_acceleration_max_radps2"])

    def update(self, initial_state, reference, nominal_states, nominal_controls, previous_control,
               distances, gradients, gradient_valid, trust: TrustRegion, semantic_margins=None,
               collision_recovery: bool = False) -> float:
        started = time.perf_counter()
        reference = unwrap_reference(np.asarray(reference, float), nominal_states)
        self.initial_state.value = np.asarray(initial_state, float)
        self.reference.value = reference
        self.nominal_states.value = np.asarray(nominal_states, float)
        self.nominal_controls.value = np.asarray(nominal_controls, float)
        self.previous_control.value = np.asarray(previous_control, float)
        valid = np.asarray(gradient_valid[1:], dtype=float)
        gradient_values = np.asarray(gradients[1:], float).copy()
        gradient_values[valid == 0.0] = 0.0
        # Precompute d - g*qbar outside CVXPY; Parameter*Parameter would violate DPP.
        bias = np.asarray(distances[1:], float) - np.einsum("ij,ij->i", gradient_values, nominal_states[1:])
        bias[valid == 0.0] = float(self.config["planner"]["d_safe_m"])
        for k in range(self.T):
            A, B, c = linearize(nominal_states[k], nominal_controls[k], self.dt)
            self.A[k].value, self.B[k].value, self.c[k].value = A, B, c
            self.clearance_gradient[k].value = gradient_values[k]
        self.clearance_bias.value = bias
        self.clearance_valid.value = valid
        margins=np.zeros(self.T) if semantic_margins is None else np.asarray(semantic_margins,float)[1:]
        if margins.shape!=(self.T,) or np.any(margins < -1e-6) or np.any(margins > .350001): raise ValueError("semantic margins must have shape [T+1] and lie in [0,0.35]")
        self.semantic_margin.value=np.clip(margins,0,.35)
        # A future-collision recovery nominal must not use geometry slack to
        # step back into the unsafe region.  Normal and semantic paths retain
        # the configured slack behavior.
        self.geometry_slack_max.value = 0.0 if collision_recovery else 100.0
        self.trust_xy.value = trust.xy_m
        self.trust_yaw.value = trust.yaw_rad
        self.trust_v.value = trust.linear_velocity_mps
        self.trust_omega.value = trust.angular_velocity_radps
        return (time.perf_counter() - started) * 1000.0

    def solve(self, simulate_timeout=False, simulate_infeasible=False):
        if simulate_timeout:
            self.last_solve_diagnostics = {"solver_status":"simulated_timeout","failure_reason":SolverFailureReason.OSQP_TIME_LIMIT_REACHED.value,"warm_start_used":self._last_primal is not None}
            return PlannerStatus.SOLVER_TIMEOUT, None, 0.0, 0.0
        if simulate_infeasible:
            self.last_solve_diagnostics = {"solver_status":"simulated_infeasible","failure_reason":SolverFailureReason.OSQP_PRIMAL_INFEASIBLE.value,"warm_start_used":self._last_primal is not None}
            return PlannerStatus.INFEASIBLE, None, 0.0, 0.0
        warm_start_used = self._last_primal is not None
        if warm_start_used:
            for variable, value in zip((self.states, self.controls, self.slack), self._last_primal):
                variable.value = value
        solver = self.config["solver"]
        started = time.perf_counter()
        try:
            self.problem.solve(
                solver=cp.OSQP, warm_start=True, max_iter=solver["max_iter"],
                eps_abs=solver["eps_abs"], eps_rel=solver["eps_rel"],
                time_limit=solver["time_limit_s"], polishing=solver["polish"], verbose=False,
                enforce_dpp=True,
            )
        except cp.error.SolverError as error:
            self.last_solve_diagnostics = {
                "solver_status":"solver_error",
                "failure_reason":SolverFailureReason.CVXPY_CANONICALIZATION_FAILURE.value,
                "exception_type":type(error).__name__,
                "warm_start_used":warm_start_used,
            }
            return PlannerStatus.NUMERICAL_ERROR, None, (time.perf_counter() - started) * 1000.0, 0.0
        wall_ms = (time.perf_counter() - started) * 1000.0
        internal_ms = float(self.problem.solver_stats.solve_time or 0.0) * 1000.0
        setup_ms = float(self.problem.solver_stats.setup_time or 0.0) * 1000.0
        self.solve_count += 1
        extra = getattr(self.problem.solver_stats,"extra_stats",None); info=getattr(extra,"info",None)
        status_text=str(getattr(info,"status",self.problem.status)); status_value=getattr(info,"status_val",None)
        primal_residual=getattr(info,"prim_res",None); dual_residual=getattr(info,"dual_res",None)
        objective=getattr(info,"obj_val",None)
        self.last_solve_diagnostics = {
            "solver_status": str(self.problem.status),
            "solver_status_text":status_text,
            "solver_status_value":int(status_value) if status_value is not None else None,
            "osqp_iterations": int(self.problem.solver_stats.num_iters or 0),
            "osqp_setup_ms": setup_ms,
            "osqp_solve_ms": internal_ms,
            "cvxpy_wrapper_and_canonicalization_ms": max(0.0, wall_ms - internal_ms - setup_ms),
            "first_solve": self.solve_count == 1,
            "warm_start_used":warm_start_used,
            "primal_residual":float(primal_residual) if primal_residual is not None else None,
            "dual_residual":float(dual_residual) if dual_residual is not None else None,
            "objective":float(objective) if objective is not None else None,
            "problem_variables":int(sum(variable.size for variable in self.problem.variables())),
            "problem_constraints":len(self.problem.constraints),
        }
        if self.problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            values = [np.asarray(v.value).copy() for v in (self.states, self.controls, self.slack)]
            self._last_primal = values
            return PlannerStatus.SOLVED_SAFE, values, wall_ms, internal_ms
        if self.problem.status in (cp.INFEASIBLE, cp.INFEASIBLE_INACCURATE):
            self.last_solve_diagnostics["failure_reason"] = SolverFailureReason.OSQP_PRIMAL_INFEASIBLE.value
            return PlannerStatus.INFEASIBLE, None, wall_ms, internal_ms
        if self.problem.status in (cp.UNBOUNDED, cp.UNBOUNDED_INACCURATE):
            self.last_solve_diagnostics["failure_reason"] = SolverFailureReason.OSQP_DUAL_INFEASIBLE.value
            return PlannerStatus.NUMERICAL_ERROR, None, wall_ms, internal_ms
        if self.problem.status == cp.USER_LIMIT:
            reason=(SolverFailureReason.OSQP_TIME_LIMIT_REACHED if "time" in status_text.lower() else SolverFailureReason.OSQP_MAX_ITER_REACHED)
            self.last_solve_diagnostics["failure_reason"] = reason.value
            return PlannerStatus.SOLVER_USER_LIMIT, None, wall_ms, internal_ms
        self.last_solve_diagnostics["failure_reason"] = SolverFailureReason.UNKNOWN_SOLVER_FAILURE.value
        return PlannerStatus.NUMERICAL_ERROR, None, wall_ms, internal_ms

    def invalidate_warm_start(self) -> None:
        """Discard a failed primal seed without changing the persistent problem."""
        self._last_primal = None
        for variable in (self.states,self.controls,self.slack):
            variable.value = None


def build_qp(initial_state, reference, nominal_states, nominal_controls, previous_control,
             distances, gradients, gradient_valid, config, trust):
    """Compatibility helper for tests; production code retains one instance."""
    persistent = PersistentPlannerQP(config)
    persistent.update(initial_state, reference, nominal_states, nominal_controls, previous_control,
                      distances, gradients, gradient_valid, trust)
    return persistent.problem, persistent.states, persistent.controls, persistent.slack
