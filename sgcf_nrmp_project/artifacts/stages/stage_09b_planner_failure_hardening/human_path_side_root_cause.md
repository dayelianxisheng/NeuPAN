# `human_path_side` Root-cause Analysis

## Frozen reproduction

The Stage 09 scene reproduced without changing geometry, start, goal, reference,
LiDAR, semantic map, or seed:

```text
P0: REJECTED_BY_GEOMETRY_CHECK
P1: SOLVER_USER_LIMIT / OSQP_MAX_ITER_REACHED
P2: SOLVER_USER_LIMIT / OSQP_MAX_ITER_REACHED
```

This satisfies the mandatory reproduction gate.

## P0 geometry rejection

P0 first obtains one acceptable SCP candidate, then rejects candidates in SCP
iterations 2 and 3. At the final rejection:

- exact minimum observable clearance: `0.2465197271 m`;
- required clearance: `0.25 m`;
- offending horizon indices: 9 and 10;
- maximum absolute exact-vs-linearized difference: `0.0070667455 m`;
- linearized clearance at the offending indices is already below `0.25 m`;
- QP slack at the two active points is approximately `0.00447/0.00390 m`;
- OSQP reports solved after 4,375 iterations, with primal residual
  `3.38e-4` and dual residual `2.15e-5`.

The rejection is therefore not caused by hidden world geometry and is not a
semantic failure. The soft QP constraint accepts small slack, while the final
exact physical recheck intentionally does not. Solver tolerance also produces a
small trust-bound excess, now explicitly classified as
`RECHECK_TRUST_REGION_VIOLATION`. Exact recheck correctly stops the candidate.

## P1/P2 solver user limit

P1 and valid-input P2 are numerically identical in this Oracle-semantic case.
Both stop on the first QP solve with:

```text
OSQP status text: maximum iterations reached
status value: 7
iterations: 10000
primal residual: 8.44e-5
dual residual: 1.67e-4
warm start used: false
```

This is now `SOLVER_USER_LIMIT / OSQP_MAX_ITER_REACHED`, not a generic timeout.
Because P0 also fails its exact acceptance test, neither P1 nor P2 can be called
`SEMANTICALLY_INFEASIBLE`.

## Selected lifecycle repair

Stage 09B chose one primary lifecycle repair: explicit solver-status mapping and
invalid warm-start cleanup after failures. No solver tolerance, iteration limit,
trust-region parameter, reference, horizon, control bound, safety distance, or
semantic margin was changed. This improves causal diagnosis but does not claim
that `human_path_side` now reaches its goal.

## Conclusion

The unknown-failure debt is resolved: P0 is an exact-recheck acceptance failure,
while P1/P2 exhaust OSQP iterations. Navigation stability for this lateral HUMAN
reference remains a known Planner limitation.
