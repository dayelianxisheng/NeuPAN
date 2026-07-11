# Stage 04 acceptance report — LiDAR-only Robot Clearance Field

## 1. Status and scope

**Status: COMPLETED**

This stage implemented and smoke-trained only the LiDAR-only differentiable
`observable_clearance` proxy. It did not implement an independent gradient head,
NRMP/QP, RGB, multimodal fusion, ROS 2 or Gazebo, and did not enlarge the stage
03 dataset.

The exact stage-02 footprint-to-visible-point geometry is the Oracle. The neural
network is a batched differentiable proxy, not a replacement for complete-world
geometry and not a formal safety guarantee.

## 2. Environment and pinned runtime

| Item | Actual value |
|---|---|
| Conda environment | `neupan` |
| Python | `3.10.0` |
| Python executable | `/home/zq/miniconda3/envs/neupan/bin/python` |
| PyTorch | `2.8.0+cu128` |
| PyTorch CUDA build | `12.8` |
| `torch.cuda.is_available()` | `False` |
| Stage device | CPU |
| Package/network installation | None |

The user-specified torch/torchvision/torchaudio wheel paths and SHA-256 hashes
are recorded in `core/envs/torch_cp310_cu128.yaml`. Torch was already installed
at the requested version. Torchvision and torchaudio were not installed because
this stage does not import them.

## 3. Dataset and supervision boundary

The unchanged stage-03 smoke dataset was used:

- Dataset: `artifacts/datasets/geometry_v1`
- Scenes: 100
- Samples: 3200
- Train: 2240 samples / 70 scenes
- Validation: 480 samples / 15 scenes
- Test: 480 samples / 15 scenes
- Fixed LiDAR points: N=180

Training supervision:

- `observable_clearance`, clipped to `[0, 5 m]`
- `observable_collision` for the optional auxiliary head
- `query_category` for configured sample weights

The loss API does not accept `world_clearance` or `world_collision`. Those
fields are used only to split model error from partial-observation world risk.
The model cannot reconstruct occluded, outside-FOV or dropped obstacles.

## 4. Implemented model

Input tensors:

```text
points_xy          [B, N, 2]
ranges             [B, N]
point_valid_mask   [B, N]
query_pose         [B, 4] = [x, y, sin(yaw), cos(yaw)]
```

Pipeline:

1. Transform each valid LiDAR point into the query footprint frame using
   `R(-yaw) * (point - query_xy)`.
2. Form per-point features `[local_x, local_y, range, squared_distance, valid]`.
3. Shared MLP `5 -> 32 -> 64 -> 64`, using LayerNorm and SiLU.
4. Padding-safe masked max and mean pooling.
5. Decoder `132 -> 64 -> 32`.
6. Bounded nonnegative distance `5 * sigmoid(raw_distance)`.
7. Optional auxiliary observable-collision logit.

Parameter count: **17,634**.

There is no independent gradient output. Physical gradients are derived as:

```text
d/dx, d/dy = direct query-pose autograd components
d/dyaw = d/dsin(yaw) * cos(yaw) - d/dcos(yaw) * sin(yaw)
```

## 5. Actual training configuration

```yaml
device: cpu
training:
  seed: 20260711
  batch_size: 64
  max_epochs: 20
  learning_rate: 0.001
  weight_decay: 0.0001
  early_stopping_patience: 4
  gradient_clip_norm: 5.0
  distance_loss_weight: 1.0
  collision_loss_weight: 0.2
  local_linearity_weight: 0.0
  category_weights: [1.0, 1.5, 2.0, 2.0]
overfit:
  sample_count: 64
  steps: 250
  required_loss_ratio: 0.35
```

Loss:

```text
L = 1.0 * weighted SmoothL1(observable distance)
  + 0.2 * BCEWithLogits(observable collision)
  + 0.0 * local linearity
```

Local-linearity loss was deliberately disabled for the first smoke run, as
allowed by the execution order. Gradient quality was still evaluated after
training.

## 6. Pre-training gates

| Gate | Result |
|---|---|
| Single batch forward | PASS |
| Single batch backward | PASS |
| Output finite/nonnegative | PASS |
| Query pose requires gradient | PASS |
| Autograd query gradient nonzero | PASS |
| 64-sample overfit | PASS |

Overfit result:

- Initial total loss: `2.0446208`
- Final total loss: `0.0113326`
- Final/initial ratio: `0.00554265`
- Required maximum ratio: `0.35`

## 7. Smoke training result

| Metric | Initial | Final/best |
|---|---:|---:|
| Train total loss | 0.539005 | 0.019154 |
| Validation total loss | 0.205824 | 0.024351 |
| Train distance loss | 0.432054 | 0.005760 |
| Validation distance loss | 0.133400 | 0.012544 |

- Epochs run: 20
- Best epoch: 20
- CPU wall time: 76.61 s
- Checkpoint: `best_model.pt`
- NaN/Inf: none

Both train and validation losses decreased substantially. Early stopping did not
trigger because the best validation value occurred at the final allowed epoch.

## 8. Test-set distance and collision metrics

Distance metrics on 480 held-out samples:

| Metric | Value |
|---|---:|
| Observable clearance MAE | 0.073078 m |
| RMSE | 0.129930 m |
| Median absolute error | 0.056575 m |
| P90 absolute error | 0.125884 m |
| Near-boundary MAE | 0.047459 m |
| Collision-region MAE | 0.059989 m |
| Free-region MAE | 0.103610 m |
| Pearson correlation | 0.995201 |

Safety-threshold classification at `d_safe=0.6 m`:

| Metric | Value |
|---|---:|
| Accuracy | 0.987500 |
| Precision | 0.980100 |
| Recall | 0.989950 |
| F1 | 0.985000 |

Auxiliary observable-collision head:

| Metric | Value |
|---|---:|
| Accuracy | 0.979167 |
| Precision | 0.911111 |
| Recall | 0.872340 |
| F1 | 0.891304 |

The auxiliary head is an optimization aid only and is not treated as a safety
mechanism.

## 9. Autograd gradient evaluation

Only the 462 test samples with `observable_gradient_valid=true` were included.
Translation and yaw are reported separately because they have different units.

| Metric | Value |
|---|---:|
| Translation L1 | 0.142350 |
| Translation L2 | 0.224414 |
| Translation cosine similarity | 0.961950 |
| x MAE | 0.139890 |
| y MAE | 0.144810 |
| yaw MAE per radian | 0.149919 |
| yaw RMSE per radian | 0.182467 |
| Local linearization MAE | 0.0000752 m |

Autograd shape, nonzero gradient, yaw-chain conversion and agreement with model
finite differences on a smooth pooling branch are covered by unit tests.

## 10. Model false-safe and world-risk decomposition

Definition:

```text
model false-safe:
prediction >= 0.6 m AND observable_clearance < 0.6 m
```

Results:

| Risk | Count | Rate |
|---|---:|---:|
| Model false-safe | 2 / 480 | 0.4167% |
| Prediction-safe and world collision | 4 / 480 | 0.8333% |
| World risk caused by observable model error | 0 | 0% |
| World risk caused by partial LiDAR observation | 4 | 0.8333% |

The four hidden world collisions had observable clearance at or above the safe
threshold. They are therefore not mislabeled as ordinary neural prediction
errors.

## 11. Exact Oracle versus neural proxy benchmark

All results below are CPU measurements. Mean/P50/P95 are milliseconds per batch.

| Queries | Method | Mean | P50 | P95 | Mean/query |
|---:|---|---:|---:|---:|---:|
| 1 | Model forward | 0.351 | 0.349 | 0.381 | 0.351 |
| 1 | Model + autograd | 1.125 | 0.951 | 1.177 | 1.125 |
| 1 | Exact Oracle | 1.418 | 0.921 | 1.045 | 1.418 |
| 1 | Oracle finite diff | 6.085 | 5.535 | 7.103 | 6.085 |
| 10 | Model forward | 0.827 | 0.795 | 1.099 | 0.0827 |
| 10 | Model + autograd | 2.302 | 2.252 | 2.789 | 0.2302 |
| 10 | Exact Oracle | 7.486 | 7.437 | 7.960 | 0.7486 |
| 10 | Oracle finite diff | 57.306 | 57.197 | 57.945 | 5.7306 |
| 32 | Model forward | 1.601 | 1.378 | 2.439 | 0.0500 |
| 32 | Model + autograd | 4.719 | 4.498 | 6.978 | 0.1475 |
| 32 | Exact Oracle | 23.114 | 22.768 | 24.737 | 0.7223 |
| 32 | Oracle finite diff | 172.998 | 172.357 | 174.655 | 5.4062 |
| 128 | Model forward | 5.347 | 5.307 | 7.508 | 0.0418 |
| 128 | Model + autograd | 17.901 | 16.921 | 26.831 | 0.1399 |
| 128 | Exact Oracle | 96.108 | 94.283 | 100.789 | 0.7508 |
| 128 | Oracle finite diff | 734.017 | 731.551 | 738.235 | 5.7345 |

The 10-query row represents a complete nominal prediction horizon. The proxy
has clear batching value in this Python/Shapely comparison. Exact geometry is
still the correctness Oracle and remains preferable for independent rechecks.
Benchmark results do not establish a universal speed advantage over optimized
native geometry libraries.

## 12. Reproducibility

A second complete CPU training run used the same dataset, config and seed:

- Best epoch A/B: `20 / 20`
- Training-history CSV files: byte-identical
- Maximum absolute state-dict difference: `0.0`
- Final checkpoint outputs: deterministic

The reproduction run is in `/tmp/sgcf_stage04_repro`; only the primary
checkpoint is retained as a stage artifact.

## 13. Tests and exact commands

Final regression:

```bash
PYTHONPATH=sgcf_nrmp_project/core/src:sgcf_nrmp_project/core/tests \
python -m unittest discover -s sgcf_nrmp_project/core/tests -v
```

Result: **52 passed, 0 failed, 0 skipped**, in 12.230 s.

Additional checks:

```text
compileall: PASS
git diff --check: PASS
required artifact completeness: PASS
root SGCF directory check: PASS
protected upstream incremental check: PASS
```

Coverage includes all requested N sizes, batch size one, full/partial padding,
mask invariance, transform numerics, yaw periodicity, distance nonnegativity,
autograd, checkpoint and optimizer recovery, backward, synthetic and real-data
overfit gates, optional collision head, CPU forward, no NaN/Inf, observable-only
loss semantics, hidden-risk separation and fixed-seed training.

## 14. Created and modified files

Configuration:

- `core/envs/torch_cp310_cu128.yaml`
- `core/configs/model/lidar_clearance_field.yaml`
- `core/configs/train/lidar_clearance_smoke.yaml`
- `core/configs/eval/lidar_clearance.yaml`

Model:

- `core/src/sgcf_nrmp/models/lidar/query_transform.py`
- `core/src/sgcf_nrmp/models/lidar/point_encoder.py`
- `core/src/sgcf_nrmp/models/field/field_output.py`
- `core/src/sgcf_nrmp/models/field/lidar_clearance_field.py`

Training/evaluation:

- `core/src/sgcf_nrmp/training/`
- `core/src/sgcf_nrmp/evaluation/`
- `core/scripts/train_lidar_clearance_smoke.py`
- `core/scripts/evaluate_lidar_clearance.py`
- `core/scripts/benchmark_clearance_query.py`
- `core/scripts/visualize_lidar_clearance_field.py`

Tests and documentation:

- `core/tests/models/`
- `core/tests/training/`
- `core/tests/evaluation/`
- `docs/architecture/lidar_clearance_field.md`

The detailed manifest is `files_changed.txt`.

## 15. Required artifacts and visible results

Machine-readable results:

- `training_config.yaml`
- `model_summary.txt`
- `best_checkpoint_metadata.json`
- `best_model.pt`
- `training_history.csv`
- `test_metrics.json`
- `gradient_metrics.json`
- `oracle_benchmark.json`
- `false_safe_report.json`
- `reproducibility_report.json`
- `test_output.txt`
- `files_changed.txt`

Required figures:

- `loss_curve.png`
- `clearance_prediction_scatter.png`
- `clearance_error_distribution.png`
- `boundary_error_plot.png`
- `false_safe_cases.png`
- `field_heatmap_comparison.png`
- `gradient_comparison.png`
- `oracle_vs_model_latency.png`

All are under:

```text
sgcf_nrmp_project/artifacts/stages/stage_04_lidar_clearance_field/
```

## 16. Acceptance checklist

| Acceptance item | Result | Evidence |
|---|---|---|
| Small subset clearly overfits | PASS | loss ratio 0.00554 |
| Train loss decreases | PASS | 0.53901 -> 0.01915 |
| Validation loss decreases | PASS | 0.20582 -> 0.02435 |
| Prediction positively correlates with GT | PASS | Pearson 0.99520 |
| Near-boundary error reported | PASS | 0.04746 m |
| Model false-safe correctly reported | PASS | 2/480 |
| World risk decomposed | PASS | 0 model / 4 partial observation |
| Autograd gradient direction agrees | PASS | xy cosine 0.96195 |
| No NaN/Inf | PASS | tests and evaluation |
| Batch query 1/10/32/128 runs | PASS | Oracle benchmark |
| Oracle benchmark complete | PASS | `oracle_benchmark.json` |
| Fixed-seed training reproducible | PASS | exact state dict/history |
| Required tests pass | PASS | 52/52 |
| Protected upstream unchanged | PASS | only pre-existing ` m neupan_ros` |
| Independent gradient head absent | PASS | distance autograd only |
| Stage 05 not started | PASS | no NRMP/QP files |

## 17. Known limitations and next-stage boundary

- Output is clipped at 5 m, so raw Oracle distances above 5 m saturate.
- Training uses only the 100-scene smoke dataset, not a formal large dataset.
- The field is based on discrete visible LiDAR hit points.
- Max pooling is piecewise differentiable and can switch branches; the planning
  stage will still require trust regions and independent geometry rechecks.
- Local-linearity regularization was not trained in this first smoke run.
- CUDA performance was not measured because CUDA was unavailable.
- Dynamic obstacle prediction and formal safety are out of scope.

Stage 04 is complete. Stage 05 NRMP/QP integration has **not** started and
requires separate user approval.
