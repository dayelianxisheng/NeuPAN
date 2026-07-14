# Stage 11C-D3A Decision

```text
STAGE_11C_D3A_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
HUMAN_CENTER_SEMANTIC_SAFE_REJECTION_VALIDATED
ORACLE_SEMANTIC_RUNTIME_SAFETY_VALIDATED
EXACT_GEOMETRY_INVARIANCE_VALIDATED
R1_DROPOUT_AND_OUTDATED_FALLBACK_VALIDATED
SEMANTIC_NONZERO_CLOSED_LOOP_NOT_DEMONSTRATED
READY_FOR_STAGE_11C_FINAL_EVALUATION_WITH_RESTRICTIONS
```

`human_path_center` is reclassified as `EXPECTED_SEMANTIC_SAFE_REJECTION`. `vehicle_path` produced safe, eligible, positive-margin P2 commands and 80 nonzero actuation messages, but those commands were effectively pure rotation and did not reduce goal distance by `0.05 m`. Semantic navigation progress is therefore not claimed.
