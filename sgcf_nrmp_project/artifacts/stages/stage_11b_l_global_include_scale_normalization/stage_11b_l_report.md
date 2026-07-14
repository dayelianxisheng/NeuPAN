# Stage 11B-L Global Include-scale Audit Report

## Decision

```text
BLOCKED_NONUNIT_MODEL_MATERIALIZATION_COMPLEX
```

All 13 historical invalid `include/scale` elements were classified: 8 are unit scale and 5 are non-unit scale. The four corridor / passage wall instances reference the simple static `static_obstacle` box and satisfy the automatic materialization preconditions. The fifth non-unit instance, `initial_collision_obstacle`, references `human_placeholder`, whose visual and collision geometry are cylinders (`radius=0.35`, `length=1.7`).

The authorized automatic non-unit migration is explicitly limited to simple box primitives. Converting this anisotropically scaled cylinder into a different explicit representation would require a newly authorized cylinder-specific rule or a deliberate redesign as an explicit box. Neither may be inferred here. The hard stop therefore occurred before modifying the source generator or any active asset.

No world, model, generator, Docker, Core, robot, sensor, Adapter, or algorithm was modified. No SDFormat runtime command or Gazebo process was started. All later gates are explicitly marked not executed.
