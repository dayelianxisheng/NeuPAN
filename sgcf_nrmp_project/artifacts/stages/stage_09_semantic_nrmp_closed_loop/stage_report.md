# Stage 09 Final Stage Report

## Final Status

```text
STAGE_09_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
SEMANTIC_NRMP_CORE_VALIDATED
READY_FOR_STAGE_10_PERCEPTION_ONLY
```

Stage 09 validates the semantic-margin core without changing the Stage 05 exact
observable-geometry foundation. It validates HUMAN clearance widening, unchanged
STATIC behavior, deterministic geometry-only control under explicit visual
failure, bounded semantic margins, and steady-state CPU latency below 100 ms.

It does **not** establish a fully stable final planner: deterministic and random
evaluations retain geometry-recheck rejections, solver user-limit terminations,
and incomplete semantic-specific status classification. Stage 10 may therefore
address perception replacement only; it must not change or conceal planner
behavior.

## Core Positive Evidence

- P0 versus Stage 05 synchronized audit: zero planner-status differences and
  zero maximum absolute state, control, distance, gradient, and slack errors.
- HUMAN minimum observable clearance: P0 `0.3027139313 m`; P1/P2
  `0.5978830647 m`.
- STATIC minimum observable clearance: P0/P1/P2 `0.3027139313 m`.
- RGB dropout and outdated-image P2 controls are elementwise identical to P0.
- Semantic margin stays in `[0, 0.35]` within floating-point representation.
- Online planning does not consume world geometry; equal online observations
  with different hidden worlds produce equal controls.
- Initially safe normal scenarios have zero planner-induced observable collision.

## Completion and Failure Disclosure

Deterministic mode-scenario results: 50/60 reached the goal, five ended in
`GEOMETRY_RECHECK_REJECTION`, two in `OSQP_OR_SOLVER_USER_LIMIT`, and three were
intentional initial-collision `EMERGENCY_STOP` cases. In `human_path_side`, P0
was rejected by geometry recheck, while P1/P2 ended at solver user limit.

Random smoke results: P0 reached 14/20 goals (70%), P1 17/20 (85%), and P2
17/20 (85%); total 48/60 (80%). Across the 12 non-success results, ten were
geometry-recheck rejection and two solver user limit. No planner-induced
observable collision occurred. **No collision does not imply navigation
success**, and rejection or safe stopping is not counted as reaching the goal.

## Collision Scope

The three Stage 09 intentional initial-collision cases are already colliding
before the first control output. All correctly return `EMERGENCY_STOP`:

```text
initial_collision_count = 3
correct_emergency_stop_count = 3
planner_induced_collision_count = 0
```

`trajectory_collision` and `world_collision` remain separate metrics. The legacy
`observable_collisions = 3` aggregate refers only to these intentional initial
collisions, not to planner-induced collisions.

## Latency Scope

`online_p95_max_ms = 179.09349700494204` is retained as a
**first-cycle / canonicalization / setup-inclusive peak**. It is not a
steady-state P95. One-time initialization, first-cycle setup, and recurring
steady-state online cycles are reported separately. The deterministic
steady-state P95 maximum is `63.21148740025818 ms`; the random-smoke maximum is
`51.08097479569551 ms`. Therefore:

```text
steady-state online-equivalent P95 < 100 ms
```

## Status-system Limitation

`SEMANTICALLY_INFEASIBLE`, `SEMANTIC_DEGRADED_TO_GEOMETRY`, and
`EXPLICIT_FAILURE_GEOMETRY_FALLBACK` are planned but not fully implemented.
Semantic infeasibility currently maps to geometry rejection or solver user
limit; explicit failure produces the correct P0-equivalent controls but the
terminal status does not fully encode why degradation occurred. Status completion
and failure-mode hardening are Stage 09B technical debt before ROS/Gazebo.

## Decision and Boundary

The formal decision is `SEMANTIC_NRMP_CORE_VALIDATED`. Stage 10 is limited to
replacing Oracle semantic maps with lightweight/real RGB perception under fixed
calibration. Stage 05 Exact Geometry, Stage 07 Semantic Margin, the Stage 09
planner core, and R1 explicit-failure rules remain frozen. Stage 10 must not tune
planner parameters or hide current navigation failures. Stage 09B and Stage 10
are not started by this report revision.

See `stage_09_final_report.md`, `known_limitations.md`, and
`stage_09_external_review_resolution.md` for the complete record.
