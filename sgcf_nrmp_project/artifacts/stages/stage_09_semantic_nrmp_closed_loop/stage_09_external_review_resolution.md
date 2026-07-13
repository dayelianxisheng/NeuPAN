# Stage 09 Independent Review Resolution

## 1. Independent Review Findings

The independent review accepted the semantic-margin core evidence but found the
prior final status too broad. It required explicit disclosure of incomplete
navigation episodes, planner lifecycle failures, collision scope, setup latency,
and unimplemented semantic-specific statuses. No experiment was rerun and no raw
metric was changed during this resolution.

## 2. Random Success-rate Disclosure

The existing 20-episode, three-mode smoke file reports:

| Mode | Reached goal | Success rate |
|---|---:|---:|
| P0 | 14/20 | 70% |
| P1 | 17/20 | 85% |
| P2 | 17/20 | 85% |
| Total | 48/60 | 80% |

The 12 failures comprise ten `GEOMETRY_RECHECK_REJECTION` and two
`OSQP_OR_SOLVER_USER_LIMIT`. No planner-induced observable collision occurred,
but collision-free stopping or rejection is not navigation success.

## 3. Deterministic Failure Disclosure

The 60 deterministic mode-scenario results comprise 50 reached goals, five
geometry-recheck rejections, two solver user-limit terminations, and three
intentional initial-collision emergency stops. `human_path_side` ends in
`REJECTED_BY_GEOMETRY_CHECK` for P0 and solver user limit for P1/P2. The final
reports no longer claim universal deterministic success.

## 4. Collision-scope Correction

The three observable collisions in the legacy aggregate are the three P0/P1/P2
instances of one intentional initial-collision fixture. Collision exists before
the first output, all three return `EMERGENCY_STOP`, and none is planner-induced:

```text
initial_collision_count = 3
correct_emergency_stop_count = 3
planner_induced_collision_count = 0
```

`initial_collision`, `planner_induced_collision`, `trajectory_collision`, and
`world_collision` remain distinct.

## 5. Latency-scope Correction

The retained `179.09349700494204 ms` value is labeled as a first-cycle,
canonicalization, setup-inclusive peak. Deterministic and random steady-state
P95 maxima are respectively `63.21148740025818 ms` and
`51.08097479569551 ms`. The accepted recurring-cycle statement remains
`steady-state online-equivalent P95 < 100 ms`; no slow sample was removed.

## 6. Unimplemented Planner Statuses

The planned statuses `SEMANTICALLY_INFEASIBLE`,
`SEMANTIC_DEGRADED_TO_GEOMETRY`, and
`EXPLICIT_FAILURE_GEOMETRY_FALLBACK` are not fully implemented. Semantic
infeasibility may map to geometry rejection or solver user limit. Explicit
dropout/staleness produces verified P0-equivalent controls, but the status enum
does not fully encode the degradation cause.

## 7. Superseded Historical Reports

`test_output.txt`, `test_output_stage_09a.txt`, and
`stage_09a_audit_report.md` are retained as historical evidence and marked
`SUPERSEDED BY STAGE 09 FINAL REVALIDATION`. Authority now rests with
`stage_09_final_report.md` and `stage_report.md`.

## 8. Revised Final Status

```text
STAGE_09_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
SEMANTIC_NRMP_CORE_VALIDATED
READY_FOR_STAGE_10_PERCEPTION_ONLY
```

This preserves the positive semantic-margin result without describing the
current planner as a fully stable final navigation system.

## 9. Stage 10 Perception-only Boundary

Stage 10 may only replace the Oracle semantic map with lightweight or real RGB
semantic perception under fixed calibration. It must freeze Stage 05 Exact
Geometry, Stage 07 Semantic Margin, Stage 09 planner core, and R1 explicit-failure
rules. It must not tune planner parameters or hide existing navigation failures.

## 10. Remaining Stage 09B Technical Debt

Before ROS/Gazebo, a separately authorized Stage 09B should cover:

- `SEMANTICALLY_INFEASIBLE` classification;
- `SEMANTIC_DEGRADED_TO_GEOMETRY` status;
- `EXPLICIT_FAILURE_GEOMETRY_FALLBACK` status;
- geometry-recheck rejection diagnosis;
- solver user-limit diagnosis;
- `human_path_side` regression.

This revision records but does not implement Stage 09B or Stage 10.
