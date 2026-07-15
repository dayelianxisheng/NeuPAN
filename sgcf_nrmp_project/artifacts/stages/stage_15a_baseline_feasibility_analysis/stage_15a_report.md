# Stage 15A Oracle Baseline Feasibility Analysis

## Decision

`STAGE_15A_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS`

## Root cause

Stage 15 used a 6 s active command window for a 4 m goal. At the frozen 0.30 m/s reference speed, the theoretical minimum is 13.33 s. This is a protocol floor for goal-reaching statistics, but it is not the sole failure: most runs also contain repeated exact-geometry rejection, geometric infeasibility, or semantic infeasibility.

The global straight and avoidance paths both end at the configured goal. Saved snapshot paths are rolling planner horizons, so their nearer endpoints are expected and are not a goal/path mismatch. Safe stops were not counted as runtime errors.

## Per-scene diagnosis

- `human_path_center`: P0 [PLANNER_COMPLETENESS_LIMITATION=3], max progress 0.017330 m; P2 [SEMANTICALLY_INFEASIBLE=3], max progress 0.000000 m. Role: `SAFETY_REJECTION_OR_COMPLETENESS_DIAGNOSTIC`.
- `human_path_side`: P0 [PLANNER_COMPLETENESS_LIMITATION=3], max progress 0.013617 m; P2 [SEMANTICALLY_INFEASIBLE=3], max progress 0.000000 m. Role: `SAFETY_REJECTION_OR_COMPLETENESS_DIAGNOSTIC`.
- `mixed_static_human_vehicle`: P0 [PLANNER_COMPLETENESS_LIMITATION=2, PROGRESS_WITHOUT_GOAL_REACH=1, SAFE_REJECTION=20], max progress 0.049841 m; P2 [SAFE_REJECTION=14, SEMANTICALLY_INFEASIBLE=9], max progress 0.000000 m. Role: `PARTIAL_PROGRESS_BASELINE_ONLY`.
- `semantic_infeasible`: P0 [PLANNER_COMPLETENESS_LIMITATION=3], max progress 0.023994 m; P2 [SEMANTICALLY_INFEASIBLE=3], max progress 0.000000 m. Role: `SAFETY_REJECTION_OR_COMPLETENESS_DIAGNOSTIC`.
- `vehicle_path`: P0 [PLANNER_COMPLETENESS_LIMITATION=2, TIMEOUT_TOO_SHORT=1], max progress 0.177986 m; P2 [REVERSE_OR_DIVERGENT_PROGRESS=3], max progress 0.083592 m. Role: `SAFETY_REJECTION_OR_COMPLETENESS_DIAGNOSTIC`.

## Minimal reruns

3 P0 reruns used a 20 s window without changing the goal, scene, planner, speed, or safety parameters. Goal success established: False. Stable progress established: True.

- `human_path_center`: progress 0.003172 m, final distance 3.996828 m, status `REJECTED_BY_GEOMETRY_CHECK`, interpretation `PLANNER_COMPLETENESS_LIMITATION`.
- `mixed_static_human_vehicle`: progress 0.089052 m, final distance 3.910948 m, status `GEOMETRICALLY_INFEASIBLE`, interpretation `PARTIAL_PROGRESS`.
- `vehicle_path`: progress 0.010810 m, final distance 3.989190 m, status `REJECTED_BY_GEOMETRY_CHECK`, interpretation `PLANNER_COMPLETENESS_LIMITATION`.

## Stage 16

Stage 16 remains blocked. Semantic-infeasible and no-legal-path cases are safety-rejection tests, not navigation-success comparison scenes.
