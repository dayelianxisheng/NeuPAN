# Stage 11B-N Final Runtime Matrix Report

## Decision

```text
STAGE_11B_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS
GAZEBO_HEADLESS_RUNTIME_VALIDATED
SDF_SCHEMA_NORMALIZATION_VALIDATED
LIDAR_SELF_VISIBILITY_FIX_VALIDATED
EXACT_RUNTIME_GEOMETRY_VALIDATED
READY_FOR_STAGE_11C_WITH_RESTRICTIONS
```

A fresh 12-world matrix completed under the immutable `99de6309…` image. All worlds parsed, loaded, advanced simulation time, published their required sensors, preserved expected entities, produced zero robot self-return, and cleaned up. Clearance errors remained below 0.02 m with 5/5 collision agreement. The external initial-collision cylinder remained visible and colliding. Oracle semantic and both R1 contracts passed. Three startup samples were recorded for each required scene; the sample size is explicitly small. The intentional initial-collision contact response displaced the dynamic robot by 2.41 mm before pose capture; the external obstacle pose remained exact and the safety classification remained correct, so this is retained as a known runtime limitation rather than hidden.

Stage 11C was not started. Stage 09B Planner limitations and the simulation-only status of Oracle semantics remain in force.
