"""Planner status mapping and structured result."""

from __future__ import annotations

from dataclasses import dataclass,field
from enum import Enum
import numpy as np


class PlannerStatus(str,Enum):
    SOLVED_SAFE="SOLVED_SAFE"; SOLVED_WITH_SLACK="SOLVED_WITH_SLACK"; REJECTED_BY_GEOMETRY_CHECK="REJECTED_BY_GEOMETRY_CHECK"; INFEASIBLE="INFEASIBLE"; MAX_ITERATIONS="MAX_ITERATIONS"; SOLVER_TIMEOUT="SOLVER_TIMEOUT"; NUMERICAL_ERROR="NUMERICAL_ERROR"; EMERGENCY_STOP="EMERGENCY_STOP"


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
