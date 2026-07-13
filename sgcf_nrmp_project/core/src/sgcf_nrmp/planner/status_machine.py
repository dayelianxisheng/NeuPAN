"""Deterministic Stage 09B planner-state priority and lifecycle helpers."""

from __future__ import annotations

from sgcf_nrmp.planner.solver_result import PlannerStatus


STATUS_PRIORITY = {
    PlannerStatus.EMERGENCY_STOP: 0,
    PlannerStatus.INVALID_INPUT: 1,
    PlannerStatus.EXPLICIT_FAILURE_GEOMETRY_FALLBACK: 2,
    PlannerStatus.GEOMETRICALLY_INFEASIBLE: 3,
    PlannerStatus.SEMANTICALLY_INFEASIBLE: 4,
    PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY: 5,
    PlannerStatus.SOLVER_USER_LIMIT: 6,
    PlannerStatus.SOLVER_TIMEOUT: 7,
    PlannerStatus.NUMERICAL_ERROR: 8,
    PlannerStatus.REJECTED_BY_GEOMETRY_CHECK: 9,
    PlannerStatus.SOLVED_WITH_SLACK: 10,
    PlannerStatus.SOLVED_SAFE: 11,
    PlannerStatus.SUCCESS: 12,
    PlannerStatus.GOAL_REACHED: 13,
}

CONTROL_ACCEPTED_STATUSES = frozenset({
    PlannerStatus.SOLVED_SAFE,
    PlannerStatus.SOLVED_WITH_SLACK,
    PlannerStatus.SUCCESS,
    PlannerStatus.EXPLICIT_FAILURE_GEOMETRY_FALLBACK,
    PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY,
})


def resolve_status(*statuses: PlannerStatus) -> PlannerStatus:
    """Select one status using the fixed online priority table."""
    if not statuses:
        raise ValueError("at least one planner status is required")
    return min(statuses, key=lambda status: STATUS_PRIORITY.get(status, 1000))


def semantic_failure_status(
    semantic_status: PlannerStatus,
    geometry_status: PlannerStatus,
    allow_degradation: bool,
) -> PlannerStatus:
    """Classify semantic infeasibility only after a feasible P0 counterfactual."""
    geometry_feasible = geometry_status in CONTROL_ACCEPTED_STATUSES
    if semantic_status not in (PlannerStatus.INFEASIBLE, PlannerStatus.GEOMETRICALLY_INFEASIBLE):
        return semantic_status
    if not geometry_feasible:
        return PlannerStatus.GEOMETRICALLY_INFEASIBLE
    return (
        PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY
        if allow_degradation
        else PlannerStatus.SEMANTICALLY_INFEASIBLE
    )
