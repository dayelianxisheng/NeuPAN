# Stage 10D Four-image Separability and Loss-weighting Audit

## Decision

```text
FOUR_IMAGE_PIPELINE_VALIDATED
CURRENT_WEIGHTED_CE_RETAINED
READY_FOR_48_IMAGE_OVERFIT_RECHECK
```

This decision authorizes only a future separately requested 48-image overfit
recheck. Stage 10D itself stops without running it.

## Frozen four-image set

Train scene IDs 0, 1, 2, and 3 were selected once before results. Their RGB and
semantic SHA-256 hashes plus geometry/appearance/camera seeds are recorded in
`four_image_selection.json`. Each image contains UNKNOWN, STATIC, HUMAN, VEHICLE,
and ROBOT; class positions, backgrounds, colors, textures, and sizes differ.
No validation/test image is used.

## Static alignment audit

All RGB/label shapes match, labels use only IDs 0–4, texture remains clipped to
instances, and the ROBOT antenna is labeled. The four-image overlays show no new
systematic mismatch, so training was permitted.

## Current class weights

Weights are computed once from fixed train scenes 0–47 using normalized square
root inverse pixel frequency:

| Class | Pixel frequency | Actual weight |
|---|---:|---:|
| UNKNOWN | 0.729842 | 0.328264 |
| STATIC | 0.119410 | 0.811554 |
| HUMAN | 0.033668 | 1.528381 |
| VEHICLE | 0.051242 | 1.238861 |
| ROBOT | 0.065839 | 1.092940 |

The class order exactly matches IDs 0–4, weights are normalized once, and none
is extreme. HUMAN weight is 1.3984× ROBOT; Stage 10D does not design a third
weight scheme.

## Object-patch separability

A 1,426-parameter train-only HUMAN/ROBOT crop classifier uses eight GT crops from
the frozen scenes. It reaches 100% training accuracy and loss `0.00187`. Simple
shape statistics also separate HUMAN's narrow aspect ratio (about 0.11–0.13)
from ROBOT (about 0.36–0.40). Thus these four images contain learnable object-level
differences; `BLOCKED_VISUAL_IDENTIFIABILITY` does not apply. This diagnostic is
not a real-domain generalization claim.

## Fair L0/L1 comparison

Both runs load the same initial state hash, use scene IDs 0–3, AdamW, learning
rate 0.002, no augmentation/dropout/weight decay/shuffle, and exactly 1,200 full
batch steps.

| Metric | L0 unweighted CE | L1 current weighted CE |
|---|---:|---:|
| Relative loss | 0.35862 | 0.004252 |
| Pixel accuracy | 0.79641 | 0.99785 |
| Macro F1 | 0.33684 | 0.99484 |
| UNKNOWN recall | 0.99599 | 0.99724 |
| STATIC recall | 0.62092 | 0.99952 |
| HUMAN recall | 0.00000 | 0.99886 |
| VEHICLE recall | 0.00000 | 0.99930 |
| ROBOT recall | 0.04469 | 0.99937 |
| Interior accuracy | 0.84330 | 1.00000 |

L0 fails and collapses primarily to UNKNOWN/STATIC. L1 passes every four-image
criterion. The single-image observation that L0 looked better at 600 steps does
not generalize to the fixed four-image problem; it is not sufficient evidence to
change the default loss.

## HUMAN–ROBOT confusion

Under L0, every HUMAN pixel is UNKNOWN and 90.66% of ROBOT is UNKNOWN; confusion
is not primarily HUMAN↔ROBOT but broad minority suppression. Under L1, HUMAN
recall is 99.886%, ROBOT recall 99.937%, direct HUMAN↔ROBOT prediction is zero,
and both interior recalls are 1.0. Remaining errors are almost entirely a small
number of boundary-to-UNKNOWN activations.

## Loss decision and authoritative recheck

```text
selected_root_cause = single-image evidence was not representative of four-image loss behavior
selected_minimal_fix = none; retain current weighted CE
rejected_fix = switch default training loss to unweighted CE
authoritative_four_image_recheck = L1_current_weighted_CE
```

The fair L1 comparison result is reused as the authoritative four-image result;
there is no extra seed or training run. Since L1 passes, the current weighted CE
is retained and the pipeline is ready only for a future 48-image overfit recheck.

## Scope boundary

No 48-image overfit, full training, validation/test evaluation, PointPainting,
Semantic Margin, CPU benchmark, Planner, Stage 09B, ROS, or Gazebo was run. The
result validates four-image memorization only in the synthetic train domain.
