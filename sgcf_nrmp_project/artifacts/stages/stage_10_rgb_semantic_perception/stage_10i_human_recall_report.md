# Stage 10I HUMAN Recall Root-cause Report

## Executive summary

Stage 10I kept the original Test fully frozen, audited epoch-100 Train/Validation HUMAN behavior, and performed the one authorized optimizer-state-preserving continuation. The result is `BLOCKED_OPTIMIZATION_CONVERGENCE`: general validation quality improved, but HUMAN performance remained strongly oscillatory and no checkpoint simultaneously satisfied all class and aggregate gates.

## Original Test freeze

Only test scene IDs were read from `dataset_manifest.json`. `test.npz` was not opened; no Test dataset/DataLoader was created; no inference, metric recomputation, prediction inspection, or new Test plot occurred. Historical Stage 10H HUMAN recall `0.71340` and IoU `0.57726` are retained only as prior conclusions.

## Epoch-100 Train–Validation gap

| HUMAN metric | Train | Validation | Train − Validation |
|---|---:|---:|---:|
| Recall | 0.92222 | 0.77804 | 0.14418 |
| IoU | 0.71734 | 0.67316 | 0.04418 |
| Precision | 0.76354 | 0.83316 | — |

Train had learned HUMAN substantially but had not reached the example `0.95` high-recall threshold. Validation showed an additional recall gap. This is neither a pure train failure nor sufficient evidence for a pure synthetic domain gap.

Validation HUMAN error destinations at epoch 100 were:

| Destination | Pixels | Fraction |
|---|---:|---:|
| HUMAN | 9,538 | 0.77804 |
| UNKNOWN | 1,347 | 0.10988 |
| ROBOT | 1,291 | 0.10531 |
| VEHICLE | 71 | 0.00579 |
| STATIC | 12 | 0.00098 |

The dominant errors are HUMAN→UNKNOWN and HUMAN→ROBOT, not HUMAN→STATIC.

## Validation layering

- Boundary 1px HUMAN recall: `0.63957`; boundary errors are important.
- Boundary 3px recall: `0.74543`.
- Interior (>5px) recall: `0.73188`, with `25.36%` of HUMAN interior predicted ROBOT. Therefore the issue is not boundary-only.
- Small/medium/large mean instance recall: `0.73278 / 0.86017 / 0.65890`. Small objects are weaker than medium, but large cases are also difficult; size alone does not explain the failure.
- Near-occlusion recall: `0.79093`; other visible HUMAN recall: `0.77761`. Occlusion is not the dominant factor in this split.
- Only 36 visible HUMAN pixels were within the 10px image-border band and all were missed; this is real but too small to dominate the aggregate.

There are 19 visible HUMAN instances across 20 validation scenes; one scene has no visible HUMAN instance after hard UNKNOWN occlusion. The worst visible instance is scene 93 (recall `0.29032`), where errors split mainly to ROBOT (`0.37264`) and UNKNOWN (`0.27920`). No individual seed correlation establishes systematic seed domination in this small validation sample.

## Epoch-100 convergence evidence

The original best epoch equaled the epoch-100 budget. Across epochs 81–100, validation mIoU continued increasing by about `0.00557` per epoch while validation loss declined; validation HUMAN recall itself was oscillating with a slightly negative linear slope. The bounded continuation was therefore justified for aggregate convergence diagnosis, but not guaranteed to repair HUMAN.

## Continuation integrity

- Source epoch: 100.
- Continuation: epochs 101–146; 46 additional epochs.
- Source model, optimizer state, LR 0.002, config hash, manifest hash, architecture, normalization, class weights, train/validation hashes: all matched.
- Optimizer and learning rate were not reset.
- Scheduler: not applicable; the frozen training used no scheduler.
- Every diagnostic best checkpoint was atomically saved and reload-checked on fixed validation sentinels with maximum logit difference 0.
- Stop: `VALIDATION_HUMAN_RECALL_20_EPOCHS_NO_IMPROVEMENT`.

## Continuation outcome

The best validation mIoU checkpoint was epoch 145:

| Metric | Epoch 145 | Diagnostic gate |
|---|---:|---:|
| mIoU | 0.83307 | ≥ 0.78, pass |
| Macro F1 | 0.90478 | ≥ 0.87, pass |
| HUMAN IoU | 0.65543 | ≥ 0.65, pass |
| HUMAN recall | 0.75161 | ≥ 0.85, **fail** |
| VEHICLE recall | 0.85727 | ≥ 0.75, pass |
| ROBOT recall | 0.92553 | ≥ 0.80, pass |

HUMAN recall peaked at `0.88710` on epoch 126, but that epoch had mIoU `0.77372` and VEHICLE recall `0.66943`, so it did not meet simultaneous gates. No epoch from 101–146 met every condition.

This pattern is best classified as optimization convergence/class competition under the frozen configuration: improving one semantic class or aggregate mIoU can coincide with HUMAN regression. It is not legitimate to select the isolated HUMAN peak or continue with a second run.

## New untouched audit split

A 40–100 scene, fully disjoint audit split is specified in `stage10i_new_audit_split_plan.md`, but was neither generated nor read. Because validation recovery failed, the project is not yet `READY_FOR_NEW_UNTOUCHED_SYNTHETIC_AUDIT_SPLIT`.

## Decision and boundaries

Final decision: `BLOCKED_OPTIMIZATION_CONVERGENCE`.

No Test reuse, PointPainting, Semantic Margin, robustness, CPU benchmark, Planner, Stage 09B, ROS, Gazebo, network access, or new audit data generation occurred. The diagnostic checkpoint is not an accepted Stage 10 model and synthetic validation still does not establish real-camera validity.
