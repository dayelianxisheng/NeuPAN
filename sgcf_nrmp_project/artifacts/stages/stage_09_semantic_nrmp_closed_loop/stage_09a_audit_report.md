> **SUPERSEDED BY STAGE 09 FINAL REVALIDATION**
>
> This file records an earlier blocked or audit state. The current authoritative
> conclusions are in `stage_09_final_report.md` and `stage_report.md`.
>
> 该文件记录历史阻塞/审计状态，已被 Stage 09 最终复验结论取代。当前权威
> 结论以 `stage_09_final_report.md` 和 `stage_report.md` 为准。

# Stage 09A Closed-loop Lifecycle Audit

## Decision

`AUDIT_FIXED_READY_TO_REVALIDATE_STAGE09`

Stage 09 itself remains `BLOCKED_PLANNER_INTEGRATION` until its deterministic acceptance suite is explicitly rerun. No random Stage 09 suite or Stage 10 work was started.

## Root Causes

The reported empty-scene rejection was a test-fixture defect. `make_scene()` recognized names beginning with `empty`, while the scenarios were named `no_obstacle_*`; both therefore received a circle obstacle on a straight collision course. The exact empty-point Oracle was already correct. The semantic margin provider had a separate empty-reduction bug and now returns the mathematically required zero margin when no observable semantic points exist.

The 125–175 ms figures mixed first-solve CVXPY canonicalization/setup, failed-path rejection retries, and a short-sample percentile. They were not steady-state P0 latency. The planner builds one persistent DPP QP per planner instance and retains OSQP warm start. P0 directly composes the Stage 05 `GTNRMPPlanner`; there is no second geometry planner.

## P0 Equivalence

Across eight synchronized cycles with identical state, reference, scan, seed, configuration, previous control, and separate planner instances, maximum absolute differences were exactly zero for states, controls, exact distances, exact gradients, and slack. P0 supplies a zero semantic-margin vector to the same parameterized constraint.

Configuration remains unchanged: horizon 12, dt 0.2 s, three SCP iterations, original trust region, weights, OSQP tolerances, 0.08 s solver time limit, warm start, and exact recheck.

## Minimal Reproduction

R0 empty straight and R1 empty turn ran 12 cycles in Stage 05/P0/P1/P2: every status was `SOLVED_SAFE`; rejection, solver timeout, emergency stop, and planner-induced collision counts were zero. Empty clearance is 8 m, gradient zero, gradient-valid false, and recheck passes. R2 static and R3 HUMAN were collision-free. R4 intentionally starts in collision; all four modes returned `EMERGENCY_STOP`, while `planner_induced_collision` remained false.

No solver timeout occurred. A real `SOLVER_TIMEOUT` now remains specifically attributable to OSQP/CVXPY `USER_LIMIT`; episode maximum steps and SCP completion are represented separately by lifecycle termination reasons.

## Latency Audit

Representative steady-state online P95 results:

| Scenario | Stage 05 | P0 | P1 | P2 |
|---|---:|---:|---:|---:|
| Empty straight | 10.66 ms | 10.29 ms | 37.01 ms | 10.42 ms |
| Empty turn | 11.16 ms | 12.27 ms | 11.11 ms | 11.98 ms |
| Static | 17.50 ms | 16.46 ms | 18.42 ms | 18.07 ms |
| HUMAN | 18.42 ms | 18.09 ms | 32.39 ms | 32.27 ms |

All are below 100 ms and P0 remains close to Stage 05. First cycles are reported separately and can exceed 100 ms because they contain the one-time CVXPY canonicalization/OSQP setup path. Offline world evaluation is after control selection and excluded from online samples. Plotting, JSON, and GIF work occur outside the simulator cycle.

## Lifecycle Repairs

- Goal is checked before planning and after execution.
- Termination reason, step, final status/action, goal/yaw error, and warm-start validity are recorded.
- Rejected trajectories do not update the planner warm start.
- Initial, planner-induced, trajectory, and world collisions are separate.
- LiDAR observation, checker/semantic preparation, query margin, QP update/solve, recheck, fallback, offline evaluation, first-cycle, and steady-state timings are separate.
- Per-solve status, OSQP iterations/internal time, and CVXPY wrapper/canonicalization estimate are retained.

## Verification

The complete standard-library suite passed: 126 tests in 12.736 s. Compileall and `git diff --check` passed. Protected directories have no Stage 09A increment.
