# Stage 09 Final Report — Semantic NRMP Closed Loop

## 1. Executive Summary

Stage 09 is complete and the final decision is:

```text
STAGE_09_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
SEMANTIC_NRMP_CORE_VALIDATED
READY_FOR_STAGE_10_PERCEPTION_ONLY
```

The revalidation demonstrates that a nonnegative semantic safety margin can be
integrated into the exact observable-geometry Trust-Region NRMP-like planner
without changing its geometric safety foundation. HUMAN clearance increases
substantially, STATIC behavior remains unchanged, explicit RGB failures recover
the geometry-only controls, and steady-state CPU planning remains below the
100 ms target. The result does not validate real RGB perception, silent
calibration-drift detection, dynamic prediction, or formal safety.

The semantic-margin core is validated, but the planner is not claimed to be a
fully stable final navigation system. Geometry-recheck rejection, solver user
limit, and incomplete semantic-specific status classification remain known
limitations.

## 2. Stage 09 Objectives

Stage 09 evaluated P0 geometry-only planning, P1 Oracle-semantic planning, and
P2 gated-semantic planning in deterministic and fixed-seed random offline closed
loops. The objectives were to preserve exact geometry, add semantic behavioral
margin, verify explicit-failure degradation, enforce the information boundary,
classify collisions correctly, and separate setup latency from steady state.

## 3. Final Architecture

The planner retains the Stage 05 exact observable distance and gradient,
trust-region SCP, persistent parameterized CVXPY QP, OSQP warm start, exact
observable recheck, fallback, and emergency stop. Stage 09 supplies a bounded
semantic margin only on the clearance-constraint right-hand side. P0 supplies
an all-zero margin. World geometry is excluded from online control selection and
is used only by the offline evaluator.

## 4. Stage 05 / Stage 09 P0 Equivalence

The synchronized audit reports:

| Quantity | Difference / maximum absolute error |
|---|---:|
| Planner status | 0 differences |
| Control | 0 |
| State | 0 |
| Observable distance | 0 |
| Observable gradient | 0 |
| Slack | 0 |

P0 uses the same planner class and configuration and supplies twelve exact-zero
semantic-margin parameters. Stage 09 therefore neither copies nor changes the
Stage 05 geometric planning mathematics.

## 5. Semantic Margin Integration

The accepted bound is:

```text
0 <= semantic_margin <= 0.35 m
```

No negative margin or material upper-bound violation occurred. The recorded
`0.3500000000000001 m` maximum is floating-point representation of the configured
`0.35 m` bound. Semantic margin augments behavioral clearance; exact geometry
continues to define collision safety and final recheck.

## 6. Deterministic Scenario Results

The corrected empty straight and turn fixtures contain no obstacle. Across P0,
P1, and P2 they report zero geometry rejection, zero solver timeout, and zero
observable collision. Old results from the faulty fixture are superseded.

For HUMAN:

| Mode | Minimum observable clearance |
|---|---:|
| P0 | 0.3027139313 m |
| P1 | 0.5978830647 m |
| P2 | 0.5978830647 m |

For STATIC obstacles, P0/P1/P2 are all `0.3027139313 m`. The semantic planner
therefore widens HUMAN passage distance while `STATIC_OBSTACLE = 0` preserves
the geometry-only behavior.

Across all 60 deterministic mode-scenario results:

| Outcome | Count |
|---|---:|
| Reached goal | 50 |
| `GEOMETRY_RECHECK_REJECTION` | 5 |
| `OSQP_OR_SOLVER_USER_LIMIT` | 2 |
| Intentional initial-collision `EMERGENCY_STOP` | 3 |

In `human_path_side`, P0 ends in `REJECTED_BY_GEOMETRY_CHECK`; P1 and P2 end in
solver timeout/user limit. This is a planner lifecycle, linearization, or solver
stability limitation for this lateral-HUMAN/reference configuration. It is not
evidence that semantic margin itself has failed, and this report does not claim
that every deterministic scenario reached its goal.

## 7. Random Episode Results

The retained bounded revalidation contains 20 fixed-seed smoke episodes and 60
mode-level results:

| Mode | Reached goal | Success rate |
|---|---:|---:|
| P0 | 14/20 | 70% |
| P1 | 17/20 | 85% |
| P2 | 17/20 | 85% |
| Total | 48/60 | 80% |

The 12 non-success results comprise ten `GEOMETRY_RECHECK_REJECTION` and two
`OSQP_OR_SOLVER_USER_LIMIT` terminations. They contain no initial collision and
no planner-induced observable collision, but **no collision does not imply
navigation success**. Safe stopping and rejected trajectories are not counted
as reaching the goal. These smoke results support effective semantic behavior
and preservation of the geometry safety foundation; they are insufficient to
claim fully stable random closed-loop navigation. Their maximum steady-state
P95 is `51.08097479569551 ms`, and all raw episode measurements remain unchanged
in `random_episode_metrics.json`.

## 8. Explicit-failure Degradation

For RGB dropout and a 500 ms outdated image, every P2 control element equals P0.
The valid conclusion is:

```text
Explicit visual failure -> Geometry-only Planner
```

The R1 Gate also covers invalid projection and `UNKNOWN`. This conclusion cannot
be extended to silent extrinsic error: a single-frame feature cannot infer that
its calibration is wrong.

## 9. Collision Classification

`initial_collision` is evaluated before the first planner action.
`planner_induced_collision` requires an initially safe state followed by an
executed action entering observable collision. `trajectory_collision` records a
collision anywhere on the relevant trajectory and therefore remains true for an
already-colliding initial fixture.

For the three Stage 09 modes in the intentional fixture:

| Metric | Count |
|---|---:|
| `initial_collision_count` | 3 |
| `correct_emergency_stop_count` | 3 |
| `planner_induced_collision_count` | 0 |
| `trajectory_collision_count` | 3 |

All three return `EMERGENCY_STOP`. Formal safety conclusions use initially safe
normal scenarios, where planner-induced observable collision is zero.
The legacy `observable_collisions = 3` field refers exclusively to these three
intentional initial-collision cases; it is not a planner-induced collision count.

## 10. Latency Definition and Results

Latency has three distinct scopes:

- **One-time initialization:** Python objects, planner construction, and other
  process-lifecycle work outside recurring steady-state cycles.
- **First-cycle canonicalization/setup:** the first CVXPY/OSQP preparation and
  cache warm-up after planner construction.
- **Steady-state online cycle:** recurring field/query/planner work after the
  first cycle; offline world evaluation, plotting, and artifact writing are
  excluded.

The script-level `online_p95_max_ms = 179.09349700494204` is retained and labeled
as the **first-cycle / canonicalization / setup-inclusive peak**. It is not
silently removed or used
as steady-state P95. Each scenario/mode record retains:

```text
first_cycle_online_ms
steady_state_mean_ms
steady_state_p50_ms
steady_state_p95_ms
steady_state_p99_ms
```

The largest deterministic steady-state online-equivalent P95 is
`63.21148740025818 ms`; the random-smoke maximum is
`51.08097479569551 ms`. Thus:

```text
steady-state online-equivalent P95 < 100 ms
```

The first-cycle gap remains a deployment concern and requires solver persistence
or prewarming rather than selective removal of slow samples.

## 11. Information Boundary

The online planner inputs are state, reference, observable LiDAR points, painted
semantic probabilities, projection validity, explicit image availability/age,
and warm-start state. World geometry is not an input. It is accessed only by the
offline evaluator after control selection. The hidden-world audit confirms that
identical online observations with different hidden worlds yield identical
controls. Exact geometry is not modified by semantics.

## 12. Known Limitations

1. Semantics use an Oracle map and Hard PointPainting, not a real RGB network.
2. R1 handles explicit RGB absence, staleness, invalid projection, and UNKNOWN.
3. Silent extrinsic drift is not observable from one online frame.
4. Calibration is currently `CALIBRATION_ASSUMED_VALID`.
5. HUMAN/VEHICLE future motion is not predicted.
6. World geometry is offline-evaluation-only.
7. Semantic margin supplements rather than replaces exact geometry safety.
8. Setup-inclusive first-cycle latency exceeds steady state and requires
   deployment prewarming or a persistent solver lifecycle.
9. Random smoke goal-reaching rates are P0 70%, P1/P2 85%, and 80% overall.
10. Geometry-recheck rejection and solver user-limit terminations remain.
11. `human_path_side` fails in all modes: P0 by recheck, P1/P2 by user limit.
12. Semantic infeasible/degraded/fallback statuses are not fully implemented.
13. No formal safety guarantee is claimed.

Planned statuses `SEMANTICALLY_INFEASIBLE`,
`SEMANTIC_DEGRADED_TO_GEOMETRY`, and
`EXPLICIT_FAILURE_GEOMETRY_FALLBACK` are not yet fully activated. Semantic
infeasibility may currently map to `REJECTED_BY_GEOMETRY_CHECK` or solver
timeout/user limit. Dropout/outdated controls correctly degrade to P0, but the
status enum does not fully express the reason. This is Stage 09B technical debt.

## 13. Final Decision

The final acceptance checklist is complete:

1. P0 is numerically identical to Stage 05.
2. Corrected empty scenes have no erroneous geometry rejection.
3. Intentional initial collision is classified correctly and safely stopped.
4. Initially safe normal scenarios have zero planner-induced observable collision.
5. HUMAN clearance increases from approximately 0.303 m to 0.598 m.
6. STATIC clearance remains approximately 0.303 m.
7. Dropout and stale images deterministically recover P0 controls.
8. Semantic margin stays in `[0, 0.35]` within floating-point tolerance.
9. Online planning does not access world geometry.
10. Hidden-world changes do not affect controls under equal online observations.
11. Steady-state online-equivalent P95 is below 100 ms.
12. Protected upstream directories have no Stage 09 increment.

Formal decision: `SEMANTIC_NRMP_CORE_VALIDATED`, with known planner limitations.

Recommended paper wording:

> Stage 09 validates the core semantic-margin integration: the exact observable-geometry planner remains numerically equivalent to the Stage 05 baseline in geometry-only mode, semantic margins increase clearance around HUMAN obstacles, static-obstacle behavior remains nearly unchanged, and explicit RGB failures recover geometry-only control. Steady-state CPU latency remains below the 100 ms target and no planner-induced observable collisions were observed. However, deterministic and random evaluations still contain geometry-recheck rejections, solver user-limit terminations, and incomplete semantic-specific status classification. Therefore, the semantic NRMP core is validated, while planner failure-mode hardening remains required before final ROS/Gazebo deployment.

## 14. Stage 10 Entry Conditions

`READY_FOR_STAGE_10_PERCEPTION_ONLY` permits only real or lightweight RGB
semantic perception, replacement of Oracle semantic maps, and fixed-calibration
offline evaluation. Before entry:

```text
Exact Geometry unchanged
Semantic Margin definition unchanged
R1 explicit-failure Gate retained
Stage 09 planner used as frozen baseline
```

Stage 10 must not tune planner parameters or hide current navigation failures.
Before ROS/Gazebo, a separate Stage 09B must complete semantic-specific status
classification, geometry-recheck and solver-user-limit diagnosis, and the
`human_path_side` regression. Neither Stage 09B nor Stage 10 is started here.
