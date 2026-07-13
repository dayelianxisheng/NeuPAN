# Stage 09B Planner Status State Machine

## Fixed priority

Online status selection uses the following deterministic priority:

1. `EMERGENCY_STOP` (including initial collision)
2. `INVALID_INPUT`
3. `EXPLICIT_FAILURE_GEOMETRY_FALLBACK`
4. `GEOMETRICALLY_INFEASIBLE`
5. `SEMANTICALLY_INFEASIBLE`
6. `SEMANTIC_DEGRADED_TO_GEOMETRY`
7. `SOLVER_USER_LIMIT`
8. `SOLVER_TIMEOUT`
9. `NUMERICAL_ERROR`
10. `REJECTED_BY_GEOMETRY_CHECK`
11. `SOLVED_WITH_SLACK`
12. `SOLVED_SAFE`
13. `SUCCESS`
14. `GOAL_REACHED`

Initial collision is evaluated before planning and therefore cannot be
overwritten by semantic, solver, recheck, reporting, or offline-world results.
`GOAL_REACHED` remains a closed-loop lifecycle outcome rather than a QP result.

## Semantic-specific states

`SEMANTICALLY_INFEASIBLE` requires a raw semantic QP infeasibility and a
successful geometry-only P0 counterfactual under the same state, observation,
reference, and exact geometry. Timeout or user limit is never sufficient.

`SEMANTIC_DEGRADED_TO_GEOMETRY` requires the same counterfactual plus an explicit
`allow_semantic_degradation` policy. Metadata records the original semantic
status, P0 status, reason, margins before/after fallback, and `GEOMETRY_P0`
control source. The frozen Stage 09 production configuration does not silently
enable this control-changing policy; the path is implemented and tested for an
explicitly enabled configuration.

`EXPLICIT_FAILURE_GEOMETRY_FALLBACK` covers only R1-observable failures: RGB
dropout, stale image, invalid projection, and all-UNKNOWN semantics. The
semantic margin becomes zero and the accepted control comes from the unchanged
geometry problem. This differs from semantic infeasibility because perception
is invalid before semantic optimization.

## Solver states

- OSQP maximum iterations → `SOLVER_USER_LIMIT` with
  `OSQP_MAX_ITER_REACHED`.
- OSQP time limit → `SOLVER_TIMEOUT` with `OSQP_TIME_LIMIT_REACHED`.
- Primal infeasibility → geometry/semantic counterfactual classification.
- Dual infeasibility, numerical errors, canonicalization errors, and unknown
  solver failures → `NUMERICAL_ERROR` with a retained reason code.

Raw status text/value, iterations, solve/setup time, residuals, objective,
problem size, warm-start use, mode, and prior status remain diagnostic fields.

## Geometry recheck states

Every rejected candidate retains exact and linearized clearance arrays,
signed error, offending index, candidate trajectory/control, trust region,
solver status, and slack. The reason taxonomy is:

- `RECHECK_CURRENT_STATE_COLLISION`
- `RECHECK_NEXT_STATE_COLLISION`
- `RECHECK_HORIZON_STATE_COLLISION`
- `RECHECK_CLEARANCE_BELOW_THRESHOLD`
- `RECHECK_NONFINITE_GEOMETRY`
- `RECHECK_LINEARIZATION_MISMATCH`
- `RECHECK_TRUST_REGION_VIOLATION`

World clearance is never a rejection reason.

## Online/offline boundary

`ExactObservableChecker` may affect status and control.
`OfflineWorldEvaluator` runs only after online selection and cannot modify
status, control, fallback, or warm start. Equal observable inputs with different
hidden worlds therefore retain identical online outcomes.
