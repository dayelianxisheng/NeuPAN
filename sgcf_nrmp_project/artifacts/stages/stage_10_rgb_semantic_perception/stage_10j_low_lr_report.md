# Stage 10J Low-Learning-Rate Stabilization Report

## Executive decision

```text
BLOCKED_OPTIMIZATION_CONVERGENCE
NO_FURTHER_STAGE10_TUNING_AUTHORIZED_FOR_CURRENT_CONFIGURATION
```

The one authorized validation-only continuation completed all 50 fixed epochs
(146–195). Lowering the learning rate from `0.002` to `0.0002` reduced metric
oscillation, but produced no checkpoint satisfying every hard validation gate.
The original Test and the planned untouched audit split were not accessed.

## Input checkpoint and optimizer state

- Source: `stage10i_validation_diagnostic_checkpoint.pt`, epoch 145.
- Checkpoint purpose: `VALIDATION_ONLY_DIAGNOSTIC`.
- Model/config/dataset hashes, normalization, weights, and train/validation
  hashes matched.
- Optimizer: AdamW, one parameter group.
- Full optimizer state was loaded; Adam moments were not reset.
- Only the learning-rate field changed: `0.002` → `0.0002`.
- Moment-state hash and all non-LR parameter-group fields were unchanged before
  the first Stage 10J optimizer step.

An initial pre-optimizer audit report incorrectly treated expected-false
non-access flags as required-true values. It was corrected before any optimizer
step and is marked `SUPERSEDED_PRE_OPTIMIZER_AUDIT_FALSE_POSITIVE`; it did not
change the checkpoint, training configuration, or authorized run.

## Fixed continuation

The run used the frozen model, renderer, split, weighted CrossEntropy, class
weights, optimizer type, batch size, augmentation, seed, and U0 argmax strategy.
It ran exactly once from epoch 146 through 195 without early stopping.

| Validation record | Epoch | mIoU | Macro F1 | HUMAN IoU | HUMAN recall | VEHICLE recall | ROBOT recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stage 10I source | 145 | 0.83307 | 0.90478 | 0.65543 | 0.75161 | 0.85727 | 0.92553 |
| Stage 10J best HUMAN recall | 146 | 0.83142 | 0.90366 | 0.65307 | 0.75610 | 0.87304 | 0.93658 |
| Stage 10J best mIoU | 148 | 0.83246 | 0.90433 | 0.65449 | 0.75438 | 0.87017 | 0.93139 |
| Final | 195 | 0.83016 | 0.90274 | 0.64689 | 0.74810 | 0.86560 | 0.93225 |

Across Stage 10J, validation mIoU had standard deviation `0.00048`; HUMAN,
VEHICLE, and ROBOT recall standard deviations were approximately `0.00185`,
`0.00193`, and `0.00075`. The low learning rate therefore stabilized the
trajectory, but around a region that still misses the HUMAN recall constraint.

## Hard-feasibility result

Each checkpoint was filtered using logical AND:

```text
mIoU >= 0.78
macro F1 >= 0.87
HUMAN IoU >= 0.65
HUMAN recall >= 0.85
VEHICLE recall >= 0.75
ROBOT recall >= 0.80
positive HUMAN/VEHICLE/ROBOT prediction fractions
finite metrics
```

Result:

```text
feasible epoch count = 0
stable feasible intervals (>=3 epochs) = 0
validation feasible checkpoint = not created
```

Aggregate, VEHICLE, and ROBOT gates generally passed near the beginning of the
continuation, while HUMAN recall did not. The best HUMAN recall remained below
the `0.85` threshold by `0.09390`. Low LR did not transfer the error to a newly
failing VEHICLE or ROBOT class; it simply did not move HUMAN into the required
region. HUMAN errors at epoch 146 primarily went to UNKNOWN (`0.14667`) and
ROBOT (`0.07627`).

## Checkpoints and information boundary

Only diagnostic checkpoints were retained:

- `stage10j_best_human_recall_checkpoint.pt`
- `stage10j_best_miou_checkpoint.pt`

All saves were atomic, followed by reload and validation-sentinel logits
comparison; maximum reload difference was `0`. No
`stage10j_validation_feasible_checkpoint.pt` exists.

The original Test was not instantiated, iterated, loaded, inferred, inspected,
or recomputed. The new audit split was neither generated nor read. No
PointPainting, Semantic Margin, robustness, CPU benchmark, Planner, Stage 09B,
ROS, or Gazebo work was performed.

## Interpretation and boundary

Stage 10I showed that the model can reach high HUMAN recall at other epochs,
but no epoch combined all required metrics. Stage 10J shows that a tenfold LR
reduction suppresses oscillation without finding a feasible local region from
epoch 145. This supports `BLOCKED_OPTIMIZATION_CONVERGENCE`, not validation
success and not synthetic RGB perception validation.

This is the final tuning attempt authorized for the current configuration.
Future work must either accept Stage 10 as blocked or begin a separately defined
model/data redesign protocol with new train/validation/audit rules. The original
Test cannot again serve as an untouched final set.
