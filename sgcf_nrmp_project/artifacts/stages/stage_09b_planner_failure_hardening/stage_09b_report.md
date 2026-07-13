# Stage 09B Planner Failure Hardening Report

## 1. Executive Summary

```text
STAGE_09B_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
READY_FOR_GAZEBO_PREPARATION_WITH_RESTRICTIONS
```

Stage 09B completes the missing semantic-specific statuses and replaces generic
geometry/solver failures with structured, online-safe diagnostic taxonomies.
Exact geometry, semantic margin, safety distance, scenario seeds, solver
settings, and Stage 09 mode definitions remain frozen.

The regression preserves Stage 05/P0 numerical equivalence, fixed random success
rates, and zero planner-induced observable collisions. `human_path_side` remains
unsuccessful but is now causally classified rather than an unknown timeout.

## 2. Implemented State Machine

The following are formally represented and tested:

- `SEMANTICALLY_INFEASIBLE`: semantic QP infeasible and same-input P0 feasible;
- `SEMANTIC_DEGRADED_TO_GEOMETRY`: the above plus explicit fallback permission;
- `EXPLICIT_FAILURE_GEOMETRY_FALLBACK`: RGB dropout, stale image, invalid
  projection, or UNKNOWN disables semantic contribution and records P0 as the
  control source.

Timeout/user limit alone cannot establish semantic infeasibility. The frozen
production config does not silently enable control-changing semantic fallback.
See `planner_status_state_machine.md` and `planner_status_mapping.json`.

## 3. Selected Minimal Lifecycle Repair

The selected primary repair is solver-status mapping plus failed warm-start
invalidation. OSQP status text/value, iterations, residuals, objective, timings,
problem dimensions, and warm-start use are retained. Failed primal seeds are
cleared before later cycles. No solver parameter was tuned.

Status-machine completion accompanies this one lifecycle repair. Exact geometry
and semantic constraints are unchanged.

## 4. Geometry Recheck Diagnosis

Across deterministic and random regressions, 44 diagnostic recheck events were
recorded, including three initial-collision checks. Reason occurrences include:

- clearance below threshold: 41;
- solver-level trust-region violation: 22;
- horizon collision: 9;
- linearization mismatch: 9;
- current-state collision: 3.

Reasons can co-occur. The 533 linearization samples have MAE `0.00325 m`, P95
absolute error `0.01389 m`, and maximum absolute error `0.20596 m`; 155 signed
errors are optimistic. Exact recheck remains authoritative and never uses world
clearance.

## 5. Solver Failure Diagnosis

Four failures in the combined fixed regressions are all explicitly classified
as `OSQP_MAX_ITER_REACHED`; no time-limit, primal/dual infeasibility,
canonicalization, or unknown solver failure was observed. Two belong to
`human_path_side` P1/P2 and two to random episode 5 P1/P2. This replaces the old
ambiguous `SOLVER_TIMEOUT` presentation without changing solver settings.

## 6. `human_path_side`

The original result reproduced exactly in outcome class:

| Mode | Stage 09B status | Root cause |
|---|---|---|
| P0 | `REJECTED_BY_GEOMETRY_CHECK` | Exact `0.24652 m < 0.25 m`; slack plus small trust-bound numerical excess |
| P1 | `SOLVER_USER_LIMIT` | OSQP maximum 10,000 iterations |
| P2 | `SOLVER_USER_LIMIT` | OSQP maximum 10,000 iterations |

P1/P2 are not classified as semantic infeasible because P0 does not produce an
accepted geometry solution. See `human_path_side_root_cause.md` and the full
cycle trace.

## 7. Stage 05 / P0 Equivalence

The synchronized eight-cycle audit reports:

```text
planner status difference = 0
control max absolute error = 0
state max absolute error = 0
distance max absolute error = 0
gradient max absolute error = 0
slack max absolute error = 0
```

Only diagnostic metadata and failure-state naming were added. Normal P0 control,
trajectory, exact distance, gradient, and slack are unchanged.

## 8. Deterministic Regression

The same 60 mode-scenario results produce:

- reached goal: 50;
- geometry recheck rejection: 5;
- solver user limit: 2;
- intentional initial-collision emergency stop: 3.

Four successful P2 explicit-failure fixtures now end with
`EXPLICIT_FAILURE_GEOMETRY_FALLBACK` while retaining P0-equivalent control.
Empty scenes have no false rejection. HUMAN and STATIC behavior remain the
Stage 09 values.

## 9. Random Smoke Regression

The original 20 episodes and seeds retain:

| Mode | Stage 09 | Stage 09B |
|---|---:|---:|
| P0 | 70% | 70% |
| P1 | 85% | 85% |
| P2 | 85% | 85% |

Failures remain ten geometry rejections and two OSQP user-limit cases. No
failure was hidden or counted as success.

## 10. Collision and Information Boundary

The combined regression records three intentional initial collisions, three
correct emergency stops, and zero planner-induced observable collisions.
`trajectory_collision_count = 6` includes the three intentional initial
collisions plus three unexecuted rejected trajectories in the deterministic
geometry-infeasible fixture; it does not mean six executed collisions.

World evaluation remains after control selection and cannot alter status,
fallback, warm start, or control. Equal observable inputs retain equal online
outcomes under different hidden worlds.

## 11. Latency

| Scope | Mean | P50 | P95 | P99 | Maximum |
|---|---:|---:|---:|---:|---:|
| First cycle/setup-inclusive | 154.37 | 127.33 | 279.26 | 297.33 | 318.25 ms |
| Steady-state online-equivalent | 20.91 | 18.96 | 37.72 | 57.40 | 235.69 ms |
| Solver calls | 5.68 | 2.66 | 10.99 | 92.68 | 284.80 ms |
| Exact recheck | 0.24 | 0.19 | 0.30 | 1.35 | 179.17 ms |

First-cycle setup is retained separately. The formal recurring P95 remains below
100 ms. Rare steady-state maxima are disclosed rather than removed.

## 12. Verification and Decision

The final decision is complete with known Planner limitations because:

- semantic and failure taxonomies are complete;
- P0 equivalence is exact;
- no planner-induced collision appears;
- steady-state P95 passes;
- `human_path_side` has explicit, reproducible causes;
- random performance is not degraded.

The scene still fails and random navigation is not 100%, so unrestricted Planner
readiness is not claimed. Gazebo preparation may proceed only with these
restrictions and without altering the frozen exact-geometry foundation.
