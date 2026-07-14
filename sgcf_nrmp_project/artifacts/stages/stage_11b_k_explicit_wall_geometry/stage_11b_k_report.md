# Stage 11B-K Include-scale Scope Audit Report

## Decision

```text
BLOCKED_SCALE_SCOPE_EXPANSION_REQUIRED
```

The mandatory repository-wide include audit found **13** `include/scale` elements across **11** worlds. Four belong to the two authorized targets, but **9** occur in other worlds: `human_path_center, human_path_side, initial_collision, outdated_rgb_contract, rgb_dropout_contract, robot_obstacle, semantic_infeasible, single_static_obstacle, vehicle_path`.

The source-of-truth generator emits `<scale>` for every obstacle include, including unit scale. More importantly, `initial_collision` uses a non-unit include scale, so this is not merely redundant syntax outside the two target worlds. Repairing only `static_corridor` and `narrow_passage` would leave the same schema defect elsewhere; repairing all affected scenes would exceed the authorized scope.

No generator, world, model, Docker, Core, robot, sensor, Adapter, or algorithm asset was modified. No Gazebo process was started. SDF runtime validation and the four-scene targeted Gate were not executed after the immediate-stop condition.
