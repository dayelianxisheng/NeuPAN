# LiDAR-only Robot Clearance Field

The exact stage-02 footprint-to-visible-point geometry is the
`observable_clearance` Oracle. `LidarClearanceField` is a lightweight,
differentiable proxy intended for batched queries and later optimization.

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

The model uses a fixed 5 m output clip during smoke training. Exact geometry is
still preferable when exactness or independent safety checking matters; the
proxy is useful when many differentiable queries must be evaluated together.
