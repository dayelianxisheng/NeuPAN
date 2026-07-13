# Stage 11B-H Full Runtime Matrix Report

## Decision

```text
BLOCKED_GEOMETRY_RUNTIME_CONSISTENCY
```

The Stage 11B-F environment consistency gate passed. The authoritative `empty_world` evidence was integrated, and all remaining 11 worlds independently loaded, advanced simulation time, published LiDAR / Camera / Odometry, initialized OGRE2, and cleaned up without residual Gazebo processes.

## Immediate-stop finding

Runtime geometry consistency failed. The first LiDAR scan in every audited world contains the same near-field return cluster around 0.20 m. The nearest representative point is approximately `[-0.014, -0.200] m`, which lies inside the frozen 0.8 × 0.5 m rectangle. Consequently `single_static_obstacle`, `static_corridor`, `narrow_passage`, and `human_path_side` are incorrectly classified as runtime observable collisions with clearance 0.0 m. Only the intentional `initial_collision` classification agrees. Collision-classification agreement across the five required scenes is 20%.

The cross-scene invariance and presence of the same finite returns in Stage 11B-F `empty_world` identify robot self-observation, not world obstacle geometry, as the cause. Fixing the LiDAR installation / visibility or defining an explicitly safe self-return policy requires a separate authorized asset-contract decision. No filtering, asset change, Planner, PointPainting, Semantic Margin, Stage 10, ROS bridge, or Stage 11C operation was performed.

Startup repeat measurements were stopped as required after the geometry inconsistency was identified.
