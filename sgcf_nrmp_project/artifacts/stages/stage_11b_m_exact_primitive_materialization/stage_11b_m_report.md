# Stage 11B-M Exact Primitive Materialization Report

## Decision

```text
STAGE_11B_M_COMPLETE
GLOBAL_INCLUDE_SCALE_SCHEMA_DEFECT_REMOVED
BOX_PRIMITIVES_EXACTLY_MATERIALIZED
INITIAL_COLLISION_CYLINDER_EXACTLY_MATERIALIZED
ALL_CHANGED_WORLDS_RUNTIME_VALIDATED
READY_TO_RERUN_STAGE_11B_FULL_RUNTIME_MATRIX
```

The generator now removes unit include scales, emits four exact explicit boxes, and emits the initial-collision obstacle as an exact axis-aligned cylinder with radius 0.2 m and length 0.4 m. All 12 worlds pass SDFormat 14.9.0 validation. All 11 changed worlds independently passed runtime sensor, entity, self-visibility, and cleanup gates. Runtime clearance errors for all five authoritative scenes are below 0.02 m, and classification agreement is 5/5.

Stage 11B is not declared complete. A fresh full runtime matrix remains required. Stage 11C was not started.
