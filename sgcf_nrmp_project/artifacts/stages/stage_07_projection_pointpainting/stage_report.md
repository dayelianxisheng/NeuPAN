# Stage 07 — RGB–LiDAR Projection, Oracle Semantics, PointPainting and Margin Labels

## Status

`COMPLETED`

## Scope completed

- Vectorized pinhole projection with explicit `T_target_source` transforms.
- Deterministic lightweight z-buffer rendering of semantic/instance/depth/RGB-debug images from convex prisms.
- Oracle PointPainting that preserves every LiDAR point and its order.
- Nonnegative semantic-margin and deterministic reliability ground truth.
- Translation, rotation, image-age, dropout, boundary, occlusion, and moving-foreground checks.
- Three deterministic cases: wall+robot, human beside wall, and near wall occluding a vehicle.

No image network was trained. Sparse Local Soft Fusion, planner integration, ROS, Gazebo, Stage 08, and dynamic prediction were not started.

## Geometry/semantic boundary

Exact observable geometry remains the sole source of `d_geo`, `g_geo`, collision, and recheck. Semantic class only produces `m_sem >= 0` and reliability. Tests confirm identical LiDAR geometry produces bitwise-identical exact distance under different semantic metadata. RGB dropout preserves all LiDAR coordinates and sets semantic confidence/reliability to zero.

## Results

- Known center projection error: 0 px.
- Baseline projection validity: 100% for the deterministic primary case.
- Oracle PointPainting accuracy on valid projected nearest-hit points: 100%.
- Input/output point counts: 39/39; order preserved; no invalid point deletion.
- Calibration grid: 16 combinations covering 0/1/3/5 cm and 0/1/3/5 degrees.
- Label agreement decreases from 1.0 at nominal calibration to 0.667 at 5 cm + 5 degrees.
- Image ages: 0/50/100/300/500 ms; reliability becomes zero after the configured 100 ms freshness limit.
- After the semantic-margin consistency audit, the heatmap range is 0 to 0.3500000000000001 m, bounded by the configured 0.35 m HUMAN margin within floating-point tolerance. The earlier 0.4146 m value was fixed by making `d_geo` and `d_j` use the same observable LiDAR point set.

The rasterizer is an offline deterministic convex-prism oracle built from NumPy and Matplotlib only. RGB debug colors are visualization metadata and are never decoded into semantic IDs.

## Verification

Stage-07 tests and the full standard-library suite passed (102/102 after the semantic-margin audit); exact counts are in `test_output.txt`. `compileall` and `git diff --check` passed. Protected NeuPAN directories show no new worktree changes.

Stage 08 was not started.
