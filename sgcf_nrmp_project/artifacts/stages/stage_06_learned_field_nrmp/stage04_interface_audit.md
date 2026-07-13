# Stage-04 Interface Audit

`LidarClearanceField.forward(points_xy, ranges, point_valid_mask, query_pose)` transforms every scene point into every query frame before its shared MLP. The five point features are local x, local y, range, local squared distance, and validity. Three of these are query-dependent.

Consequences:

- The checkpoint supports batched queries only by repeating the point cloud across the batch.
- The point encoder executes once per query, not once per control cycle.
- A query-independent `SceneEncoding` cannot reproduce the checkpointed function.
- Splitting encoder and decoder would change the function and requires retraining.
- Storing raw points in a `SceneEncoding` wrapper would not meet the caching requirement.

The audit stopped integration before creating an incompatible adapter. Checkpoint loading itself was previously validated; no checkpoint file was changed. Stage-04 results remain valid within their learned-geometry ablation scope.
