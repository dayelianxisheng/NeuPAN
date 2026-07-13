# LiDAR-only Robot Clearance Field — Learned Geometry Ablation

The exact stage-02 footprint-to-visible-point geometry is the
`observable_clearance` Oracle. `LidarClearanceField` is a lightweight,
differentiable proxy retained as a learned-geometry research ablation. Following
the Stage-06 architecture decision, it is not the final system's primary
geometry module and is not connected to the production planner.

The model transforms valid scan points into each candidate query frame, encodes
five per-point features with a shared MLP, applies masked max and mean pooling,
and decodes a bounded nonnegative clearance. An auxiliary collision logit helps
the boundary representation but is not a safety guarantee. There is no
independent gradient head: x/y/yaw gradients are obtained from distance through
autograd and the sin/cos chain rule.

Only `observable_clearance` and `observable_collision` enter training loss.
`world_clearance` and `world_collision` remain evaluation-only oracle fields.
The network cannot reconstruct occluded, out-of-FOV or dropped obstacles.
Consequently hidden-world collisions are reported separately from model
false-safe errors.

This first version is static and reactive: it predicts neither obstacle motion
nor future dynamic trajectories. It provides no formal safety guarantee.

The point encoder is query-conditioned: local x/y and squared-distance features
are formed before point encoding. Consequently the existing checkpoint cannot
encode a scene once and reuse that encoding across many queries. Refactoring
this dependency would change the learned architecture and require retraining.

The model uses a fixed 5 m output clip. It remains useful for paper ablations:
comparing learned versus exact distance and gradients, demonstrating feasibility,
and documenting why the final system selects exact geometry. It is preserved
unchanged and is not retrained.

The final system uses `BatchedRectangleObservableOracle` for exact physical
clearance and gradients. RGB–LiDAR learning is reserved for a nonnegative
semantic margin and reliability term. RGB cannot increase geometric clearance;
when RGB is unavailable, reliability tends to zero and planning reduces to the
Stage-05 exact LiDAR planner.
