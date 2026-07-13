# Gazebo Oracle Semantic Sidecar Specification

`GAZEBO_ORACLE_SEMANTIC_SIDECAR` is simulation ground truth, not RGB
perception. It maps frozen world model names to semantic IDs and may provide an
Oracle semantic image or one ordered class ID per LiDAR slot.

The sidecar is permitted only for Stage 07 PointPainting, Stage 07 Semantic
Margin, and P1/P2 interface validation. It must preserve every LiDAR range,
point, valid-mask entry, index, timestamp, and frame. UNKNOWN or R1-invalid
samples contribute zero semantic margin. Exact Geometry consumes the original
observable points and cannot read sidecar labels, model names, or world state.

Topics carrying this data must be marked `simulation_only`, `ground_truth_only`,
and `not_for_real_deployment`. P0 never subscribes to the sidecar.
