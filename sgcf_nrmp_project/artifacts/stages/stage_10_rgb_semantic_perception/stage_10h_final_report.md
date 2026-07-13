# Stage 10H Final Report

## Executive summary

Stage 10H repaired the proven premature early-stopping policy and completed the one authorized formal Stage 10F retry from random initialization. Validation readiness passed, so the checkpoint and validation-only confidence policy were frozen before exactly one test evaluation. The test HUMAN recall was below the immutable acceptance gate; the stage therefore stops as `BLOCKED_HUMAN_RECALL`.

## Frozen method and data

- Model: unchanged 118,341-parameter `TinySemanticSegmentation`.
- Input: RGB only, 160×120.
- Loss: unchanged current weighted CrossEntropy with the authoritative Stage 10E class weights.
- Optimizer: unchanged AdamW, learning rate 0.002, batch size 8.
- Dataset: unchanged scene-disjoint 80/20/20 train/validation/test split.
- Renderer, class IDs, normalization, sampling, and augmentation remained frozen.
- Stage 05 geometry and Stage 07/08/09 definitions were not modified.

## Pretraining audit

The scene and seed splits were disjoint; authoritative Stage 10E hashes matched; labels were 0–4; target dtype was `torch.int64`; logits had five raw channels; UNKNOWN was not an ignore index. Float64 source weights matched exactly and float32 runtime casting passed the dtype-aware audit. Test images and labels were not read before validation readiness.

## Training lifecycle

The fixed policy used 100 maximum epochs, 60 minimum training epochs, patience 20, and mIoU `min_delta=1e-4`. Training ran to epoch 100. First positive recall epochs were:

| Split | HUMAN | VEHICLE | ROBOT |
|---|---:|---:|---:|
| Train | 37 | 43 | 27 |
| Validation | 38 | 45 | 28 |

This confirms the old epoch-24 stop occurred before minority-class learning. The best checkpoint was epoch 100. All best saves were atomic, occurred before reporting/threshold work, and reloaded with maximum logit difference 0.

## Validation readiness

| Metric | Result | Gate |
|---|---:|---:|
| mIoU | 0.75563 | ≥ 0.50 |
| Macro F1 | 0.85422 | ≥ 0.60 |
| HUMAN recall | 0.77804 | ≥ 0.75 |
| VEHICLE recall | 0.76422 | ≥ 0.50 |
| ROBOT recall | 0.85118 | ≥ 0.50 |

All readiness checks passed and no UNKNOWN/STATIC collapse remained.

## Validation policy freeze

Validation-only comparison selected `U0_argmax_always`; probability and entropy thresholds are null. The frozen checkpoint SHA-256 is `6385b1bd1233d967ac2d4f0999d617fc18af97f3f5b24770a2959cc05ee7c4e7`. Checkpoint and thresholds were frozen before test access.

## One-time test result

| Metric | Result | Stage 10 target |
|---|---:|---:|
| Pixel accuracy | 0.90442 | — |
| mIoU | 0.67510 | ≥ 0.60 |
| Macro F1 | 0.79438 | — |
| HUMAN IoU | 0.57726 | ≥ 0.60 |
| HUMAN recall | 0.71340 | ≥ 0.80 |
| VEHICLE recall | 0.71684 | — |
| ROBOT recall | 0.74585 | — |

The overall mIoU target passed, but both HUMAN recall and HUMAN IoU missed their targets. The fixed immediate-stop rule is therefore triggered. No test-driven tuning was performed.

## Region evidence

Errors are materially larger on semantic boundaries: boundary-1px accuracy is 0.59488 versus object-interior accuracy 0.88262. This helps localize the error but does not override all-pixel acceptance metrics.

## Downstream status

- Predicted PointPainting: `NOT_EXECUTED_DUE_TO_TEST_HUMAN_RECALL_FAILURE`.
- Semantic Margin gap: `NOT_EXECUTED_DUE_TO_TEST_HUMAN_RECALL_FAILURE`.
- Robustness: `NOT_EXECUTED_DUE_TO_TEST_HUMAN_RECALL_FAILURE`.
- CPU benchmark: `NOT_EXECUTED_DUE_TO_TEST_HUMAN_RECALL_FAILURE`.
- Planner, Stage 09B, ROS, Gazebo, and real robot: not started.

## Reporting incident

After the test metrics and region metrics had been written, visualization attempted to transpose an already H×W×3 RGB array and raised `TypeError`. The plotting code was corrected and the HUMAN gate was moved before plotting. No second test evaluation was run. This reporting-only error did not change checkpoint, threshold, or test metrics.

## Decision and impact

Final decision: `BLOCKED_HUMAN_RECALL`.

The early-stopping lifecycle is repaired, but synthetic RGB perception is not validated for semantic-margin use. The checkpoint must not be used to claim real-camera readiness, and it must not enter Planner, Stage 09B, Gazebo, ROS, or deployment work without a separately authorized remediation stage.
