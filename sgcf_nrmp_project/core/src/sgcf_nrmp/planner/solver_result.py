"""Planner status mapping and structured result."""

from __future__ import annotations

from dataclasses import dataclass,field
from enum import Enum
import numpy as np


class PlannerStatus(str, Enum):
    """Authoritative online planner states; all values are JSON serializable."""

    SOLVED_SAFE = "SOLVED_SAFE"
    SOLVED_WITH_SLACK = "SOLVED_WITH_SLACK"
    SUCCESS = "SUCCESS"
    GOAL_REACHED = "GOAL_REACHED"
    REJECTED_BY_GEOMETRY_CHECK = "REJECTED_BY_GEOMETRY_CHECK"
    INFEASIBLE = "INFEASIBLE"  # retained compatibility alias for raw QP mapping
    GEOMETRICALLY_INFEASIBLE = "GEOMETRICALLY_INFEASIBLE"
    SEMANTICALLY_INFEASIBLE = "SEMANTICALLY_INFEASIBLE"
    SEMANTIC_DEGRADED_TO_GEOMETRY = "SEMANTIC_DEGRADED_TO_GEOMETRY"
    EXPLICIT_FAILURE_GEOMETRY_FALLBACK = "EXPLICIT_FAILURE_GEOMETRY_FALLBACK"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    SOLVER_USER_LIMIT = "SOLVER_USER_LIMIT"
    SOLVER_TIMEOUT = "SOLVER_TIMEOUT"
    NUMERICAL_ERROR = "NUMERICAL_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class GeometryRecheckReason(str, Enum):
    CURRENT_STATE_COLLISION = "RECHECK_CURRENT_STATE_COLLISION"
    NEXT_STATE_COLLISION = "RECHECK_NEXT_STATE_COLLISION"
    HORIZON_STATE_COLLISION = "RECHECK_HORIZON_STATE_COLLISION"
    CLEARANCE_BELOW_THRESHOLD = "RECHECK_CLEARANCE_BELOW_THRESHOLD"
    NONFINITE_GEOMETRY = "RECHECK_NONFINITE_GEOMETRY"
    LINEARIZATION_MISMATCH = "RECHECK_LINEARIZATION_MISMATCH"
    TRUST_REGION_VIOLATION = "RECHECK_TRUST_REGION_VIOLATION"


class SolverFailureReason(str, Enum):
    OSQP_MAX_ITER_REACHED = "OSQP_MAX_ITER_REACHED"
    OSQP_TIME_LIMIT_REACHED = "OSQP_TIME_LIMIT_REACHED"
    OSQP_PRIMAL_INFEASIBLE = "OSQP_PRIMAL_INFEASIBLE"
    OSQP_DUAL_INFEASIBLE = "OSQP_DUAL_INFEASIBLE"
    OSQP_NUMERICAL_ERROR = "OSQP_NUMERICAL_ERROR"
    CVXPY_CANONICALIZATION_FAILURE = "CVXPY_CANONICALIZATION_FAILURE"
    UNKNOWN_SOLVER_FAILURE = "UNKNOWN_SOLVER_FAILURE"


@dataclass
class SolverResult:
    status: PlannerStatus
    states: np.ndarray
    controls: np.ndarray
    slack: np.ndarray
    objective: float=float("inf")
    solve_time_ms: float=0.
    scp_iterations: int=0
    min_observable_clearance: float=float("inf")
    violated_points: int=0
    rejection_count: int=0
    diagnostics: dict=field(default_factory=dict)

    @property
    def first_control(self) -> np.ndarray:
        return self.controls[0].copy() if len(self.controls) else np.zeros(2)
