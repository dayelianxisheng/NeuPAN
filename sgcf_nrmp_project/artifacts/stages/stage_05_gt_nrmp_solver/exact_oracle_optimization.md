# Exact Observable Oracle Optimization

## Result

The performance repair passes without changing the observable-clearance definition, horizon, LiDAR point count, SCP iteration limit, trust region, or observable recheck. Stage 04 models are not imported.

The legacy definition is the minimum distance from the transformed 0.8 m × 0.5 m rectangular footprint to current valid LiDAR points, truncated at 8 m. The new CPU implementation broadcasts all queries and points, transforms points into each query frame, evaluates exact point-to-axis-aligned-rectangle distance, masks invalid points with infinity, and reduces by minimum. Torch autograd differentiates this analytic expression. Collision, ties, and nondifferentiable samples receive deterministic finite subgradients and are marked invalid for QP linearization.

Across 100 random scenes × 100 queries, maximum distance error versus Shapely MultiPoint was `1.78e-15 m`, MAE `1.77e-16 m`, collision agreement 100%, and nearest-obstacle agreement 99.978%. Among 9,147 valid gradient samples, translation cosine similarity averaged 0.999782; gx/gy/yaw MAE was 0.00286/0.00154/0.00134 against the legacy 0.02-step finite difference. No NaN/Inf occurred. Small sign disagreements (0.481% of components) were concentrated around near-zero legacy finite-difference components and did not indicate bulk direction reversal.

For 12 queries, legacy distance-plus-finite-difference P95 was 9.82 ms; batched exact distance-plus-autograd P95 was 0.486 ms. Closed-loop online P95 was 17.03 ms for single obstacle, 23.18 ms for corridor, and 21.97 ms for narrow passage. All succeeded without observable or world collision. Offline world-evaluation P95 remained approximately 0.12 ms and was excluded from the online gate.

One-time fresh CVXPY/OSQP setup still causes occasional maxima above 100 ms, but all three distribution P95 values pass the required 100 ms gate. No parameter search or scenario filtering was performed.
