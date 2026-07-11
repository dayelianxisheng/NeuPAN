# geometry_v1 dataset

`geometry_v1` is a deterministic, static, programmatic 2D LiDAR smoke dataset.
Its training target is `observable_clearance`: footprint distance to valid hit
points in one scan. `world_clearance` and `world_collision` are complete-world
oracle fields for evaluation and partial-observation risk analysis.

Each sample stores fixed-size points and ranges with a boolean padding mask,
query pose `[x, y, sin(yaw), cos(yaw)]`, both clearances and collisions, finite
difference gradients and validity masks, query category, scene/query IDs and
seed. Invalid gradients must be excluded from gradient loss.

Splits are made by scene ID. Shards are compressed NPZ files written to a
temporary file and atomically renamed. `split_manifest.json` records every shard
count, size and SHA-256. `progress.json` exists only during an interrupted build
and allows verified shards to be reused on restart.

The loader opens shards lazily and caches only one shard. Optional augmentation
is an explicitly seeded, consistent global-frame rotation of points, query pose
and x/y gradient components; clearance labels remain invariant.

The stage 03 smoke dataset has 100 scenes and 3200 samples. It is not the formal
training dataset and must not be scaled without user approval.
