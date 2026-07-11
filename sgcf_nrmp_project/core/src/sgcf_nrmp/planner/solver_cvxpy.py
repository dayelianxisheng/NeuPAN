"""OSQP solve, warm-start and status mapping."""

from __future__ import annotations

import time
import cvxpy as cp

from sgcf_nrmp.planner.solver_result import PlannerStatus


def solve_osqp(problem,variables,config,warm_start=None,simulate_timeout=False,simulate_infeasible=False):
    if simulate_timeout: return PlannerStatus.SOLVER_TIMEOUT,None,0.
    if simulate_infeasible: return PlannerStatus.INFEASIBLE,None,0.
    if warm_start:
        for variable,value in zip(variables,warm_start): variable.value=value
    solver=config["solver"]; started=time.perf_counter()
    try:
        problem.solve(solver=cp.OSQP,warm_start=True,max_iter=solver["max_iter"],eps_abs=solver["eps_abs"],eps_rel=solver["eps_rel"],time_limit=solver["time_limit_s"],polishing=solver["polish"],verbose=False)
    except cp.error.SolverError:
        return PlannerStatus.NUMERICAL_ERROR,None,(time.perf_counter()-started)*1000
    elapsed=(time.perf_counter()-started)*1000
    if problem.status in (cp.OPTIMAL,cp.OPTIMAL_INACCURATE): return PlannerStatus.SOLVED_SAFE,[v.value for v in variables],elapsed
    if problem.status in (cp.INFEASIBLE,cp.INFEASIBLE_INACCURATE): return PlannerStatus.INFEASIBLE,None,elapsed
    if problem.status in (cp.USER_LIMIT,): return PlannerStatus.SOLVER_TIMEOUT,None,elapsed
    return PlannerStatus.NUMERICAL_ERROR,None,elapsed
