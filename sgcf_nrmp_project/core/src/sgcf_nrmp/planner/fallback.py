"""Safe fallback controls."""

import numpy as np
from sgcf_nrmp.planner.solver_result import PlannerStatus


def fallback_control(status:PlannerStatus,last_safe_control:np.ndarray|None)->np.ndarray:
    if status in (PlannerStatus.SOLVER_TIMEOUT,PlannerStatus.SOLVER_USER_LIMIT) and last_safe_control is not None: return np.asarray(last_safe_control,float).copy()
    return np.zeros(2,dtype=float)
