# Stage 09 Revalidation Report

## Status

`AUDIT_FIXED_READY_TO_REVALIDATE_STAGE09`

The Stage 09A lifecycle defects were fixed and the deterministic Stage 09 suite was rerun. The remaining Stage 09 blockers were not caused by the exact geometry or semantic-margin definitions. No Stage 10 work was started.

## What Passed in Revalidation

- The existing exact-geometry QP accepts a per-horizon semantic right-hand-side margin while P0 supplies exact zeros.
- A single HUMAN smoke case completed in all modes. Minimum observable clearance increased from 0.347 m (P0) to 0.597 m (P1/P2).
- STATIC smoke trajectories retained the same 0.347 m minimum clearance.
- P2 dropout and 500 ms stale-image controls were bitwise identical to P0 in the 20-step smoke run.
- Query margins remained in `[0, 0.35]`; semantic data did not alter exact distance, gradient, or recheck.
- P0 and Stage 05 are numerically identical on the synchronized audit cycles: state, control, exact distance, exact gradient, and slack max errors were all zero.
- Empty-scene fixtures now pass cleanly with no false geometry rejection.
- The initial-collision fixture is classified separately from planner-induced collision.
- Steady-state online P95 is below 100 ms for the named deterministic scenarios; the earlier 125-175 ms figures were first-cycle and short-sample artifacts.

## What Was Fixed

The bounded run originally mixed three separate issues:

- the `no_obstacle_*` fixtures incorrectly populated a circle obstacle because the scene builder only special-cased names beginning with `empty`;
- the semantic-margin provider had an empty-point reduction bug;
- the latency summary mixed first-cycle canonicalization/setup with steady-state planner samples.

After the fix, the named deterministic scenarios and the fixed-seed smoke run show:

- `R0` and `R1` empty scenes complete without `REJECTED_BY_GEOMETRY_CHECK`, `SOLVER_TIMEOUT`, `EMERGENCY_STOP`, or collision.
- `R2` static and `R3` HUMAN scenes preserve the expected semantic widening only for HUMAN.
- `R4` intentional initial collision ends in `EMERGENCY_STOP` in all modes, but is not counted as planner-induced collision.
- The measured steady-state P95 values remain below the 100 ms online-equivalent limit.

## Recommendation

1. Keep the Stage 05 exact geometry and Stage 07 semantic-margin definitions unchanged.
2. Treat `initial_collision` separately from `planner_induced_collision` in acceptance metrics.
3. Preserve the first-cycle / steady-state split in all future latency reports.

No lower exact safety distance, margin reduction, model training, or parameter search is recommended. Real-RGB and ROS/Gazebo integration must remain blocked until the CPU closed-loop lifecycle and status semantics stay consistent under the revalidated harness.
