# Stage 03 report

## Status

COMPLETED

## 1. Completed work

- Added a versioned `geometry_v1` schema and fixed-point LiDAR conversion for
  N=180/256/360 with deterministic decimation, zero padding and valid masks.
- Added four-stratum query sampling: free, safety boundary, collision boundary
  and collision.
- Added deterministic scene-level train/validation/test splits.
- Added atomic compressed NPZ shards, SHA-256 manifests, config hashing,
  progress-based interrupted-build resume and corruption checks.
- Added a one-shard-at-a-time PyTorch Dataset, DataLoader support and explicitly
  seeded consistent-rotation augmentation.
- Generated, inspected and independently reproduced the bounded smoke dataset.

No network was trained. No field model, planner, RGB, ROS or Gazebo code was
implemented.

## 2. Data and label semantics

The future training target is `observable_clearance`, computed only from valid
points in the current LiDAR observation. `world_clearance` and
`world_collision` use full static scene geometry and are retained only for
evaluation and partial-observation analysis.

Both observable and world finite-difference gradients are stored with separate
valid masks. Empty observation, truncation proximity, collision-boundary
crossing and detected slope discontinuity invalidate the corresponding gradient.
Padding points are zero and excluded by `point_valid_mask`.

## 3. Smoke dataset

- Location: `sgcf_nrmp_project/artifacts/datasets/geometry_v1/`
- Schema: `geometry_v1`
- Scenes: 100
- Queries per scene: 32
- Samples: 3200
- Fixed points: 180
- Shards: 13
- Train: 70 scenes / 2240 samples
- Validation: 15 scenes / 480 samples
- Test: 15 scenes / 480 samples
- Config hash: `1ce0d06e548e20d69fc33b20102b203fa4dea1ed73446e44b51a746a35d06ec7`

## 4. Distribution and partial-observation risk

- Free: 31.25%
- Safety boundary: 25.00%
- Collision boundary: 28.125%
- Collision: 15.625%
- World collision: 15.625%
- Observable gradient valid: 94.96875%
- World gradient valid: 91.96875%
- Mean absolute observable/world difference: 0.29359 m
- Complete-world collision while observable clearance >= 0.6 m: 64 samples
  (2.0%)

The last statistic is a partial-observation hidden-collision case, not a model
false-safe result because no model exists yet.

## 5. Tests and integrity

The standard-library suite ran 34 tests: all passed, none skipped. It covers the
20 requested dataset behaviors plus the stage 01/02 tests. Compileall and
`git diff --check` passed.

Integrity validation reports 3200 readable samples, no NaN/Inf, no temporary
files and no scene leakage. A second full 100-scene generation in `/tmp`
produced identical hashes for all 13 shards.

Dataset and DataLoader shapes/dtypes were verified without computing labels in
`__getitem__`. Corrupt, extra and partial shards are rejected.

## 6. Performance and storage

- Generation: 50.08 s total, 0.501 s/scene
- Peak measured RSS: 648648 KiB
- Dataset files: approximately 351 KB with compression
- Estimated storage per 10000 samples: approximately 1.10 MB for this scene/query
  repetition pattern

These figures describe the smoke generator, not training or deployment speed.

## 7. Visible results

- `sample_grid.png`
- `clearance_distribution.png`
- `observable_vs_world_scatter.png`
- `gradient_validity_distribution.png`
- `query_category_distribution.png`
- `split_distribution.png`
- `dataset_summary.json`
- `dataset_schema.json`
- `split_summary.json`
- `generation_timing.json`
- `reproducibility_report.json`
- `integrity_report.json`

The sample grid overlays complete obstacle polygons, observed LiDAR hits and the
query footprint with both clearance labels, collision and gradient validity.

## 8. Known limitations

- The smoke set has no zero-hit sample because every generated scene produced at
  least one valid hit; the explicit zero-hit representation is covered by unit
  tests.
- Observable geometry remains discrete hit points rather than reconstructed
  continuous visible surfaces.
- NPZ compression is compact because all queries in a scene repeat one scan; a
  future large dataset may choose scene-level scan deduplication.
- The only loader augmentation is a label-consistent coordinate rotation.
- This is not an approved formal training dataset.

## 9. Upstream and layout checks

All new files are inside `sgcf_nrmp_project/`. The only root SGCF directory is
`sgcf_nrmp_project`. Protected status remains the pre-existing ` m neupan_ros`;
stage 03 introduced no upstream change.

## 10. Next stage

Stage 04 would define and smoke-train the LiDAR-only distance model after manual
approval. It has not been started. Scaling this dataset also requires separate
user confirmation.
