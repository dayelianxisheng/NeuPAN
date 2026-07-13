# Stage 10B Class-collapse and Training-pipeline Diagnosis

## Decision

```text
BLOCKED_UNRESOLVED_PIPELINE
```

Stage 10B stopped at the single-image extreme-overfit layer. No Stage 10B
minimal fix was selected and the 48-image gate was not rerun.

## Class distribution

The repaired train labels contain all classes in every selected image. For the
fixed scene IDs 0–47:

| Class | Pixel count | Fraction |
|---|---:|---:|
| UNKNOWN | 672,622 | 72.9842% |
| STATIC | 110,048 | 11.9410% |
| HUMAN | 31,028 | 3.3668% |
| VEHICLE | 47,225 | 5.1242% |
| ROBOT | 60,677 | 6.5839% |

All four foreground classes occur in all 48 images and have thousands of pixels.
The set is background-dominant but does not lack core-class presence, so no
balanced-subset replacement was justified before the stop.

## Class/channel mapping

Renderer, saved labels, loader, target, model output, metrics, and visualization
all use `UNKNOWN=0`, `STATIC=1`, `HUMAN=2`, `VEHICLE=3`, `ROBOT=4`. A handcrafted
perfect-logit check yields recall 1 for every class. Mapping is not the collapse
cause.

## Prediction collapse

At the end of the reproduced 24-epoch diagnostic, prediction fractions are
81.70% UNKNOWN, 18.30% STATIC, and 0% for HUMAN/VEHICLE/ROBOT. Their maximum
probabilities remain only 0.176/0.204/0.193. The approximately 73% accuracy is
therefore a majority-class result, not successful multiclass learning.

## Single-image extreme overfit

Scene 0 contains all IDs 0–4. With batch 1, no shuffle, no augmentation,
dropout, or weight decay, and the unchanged tiny model:

| Metric | Result |
|---|---:|
| Initial loss | 1.58146644 |
| Final loss | 0.59986520 |
| Relative loss | 0.37930947 |
| Pixel accuracy | 0.68453125 |
| Macro F1 | 0.58098238 |
| UNKNOWN recall | 0.61574672 |
| STATIC recall | 1.0 |
| HUMAN recall | 0.81114551 |
| VEHICLE recall | 0.99508197 |
| ROBOT recall | 0.24848485 |

The model begins to learn all foreground classes, proving they are not completely
invisible, but it does not approach the expected 10%–20% relative loss and ROBOT
recall remains far from one. This triggers immediate-stop condition 3.

## Gradient flow and parameter updates

The first single-image batch has finite nonzero norms in encoder, bottleneck,
decoder, and classifier. Non-finite gradient fraction is zero, the optimizer
contains all trainable parameters, and all four module groups change after
optimization. Hence there is no evidence of a disconnected classifier or omitted
optimizer parameters. A high zero-gradient fraction (`0.5602`) is compatible
with ReLU sparsity but should be investigated later; it is not a total gradient
failure.

## Normalization and resolution

Input is RGB uint8 converted to finite float32 in `[0,1]`; the model contains no
BatchNorm, GroupNorm, or dropout. Input and logits are both 120×160 and total
encoder stride is four. VEHICLE and ROBOT remain several bottleneck cells wide.
The thinnest HUMAN extremity can be 0.75 bottleneck cell wide, but HUMAN height is
large and single-image recall reaches 0.81, so complete visual disappearance is
not established.

## Loss and class weights

The current path uses raw-logit CrossEntropy with normalized square-root inverse
frequency weights and no Dice. The ordered diagnostic requires loss/weight
comparison after successful single/four-image tests; because single-image
memorization failed, unweighted-vs-weighted CE and class-weight alternatives were
not run. Assigning the root cause to loss weighting now would be speculative.

## Root cause and fixes

```text
selected_root_cause = unresolved after single-image memorization failure
selected_minimal_fix = none
```

Rejected alternatives in this run: balanced subset (coverage is already broad),
mapping fix (mapping passes), BatchNorm→GroupNorm (no BatchNorm exists), gradient
repair (major groups have gradients), resolution change (no general core-class
disappearance proven), width increase (capacity not yet isolated), and loss/
weight change (comparison not reached).

## Remaining recommendation

Authorize a narrowly scoped continuation beginning with a controlled single-image
loss/weight comparison and object-patch identifiability check. Only if one of
those demonstrates a specific cause should one minimal fix be selected. Do not
repeat the 48-image gate, enlarge the model, or run full Stage 10 beforehand.

Full Stage 10, real RGB validation, PointPainting, Semantic Margin, CPU benchmark,
Planner, Stage 09B, ROS, and Gazebo remain blocked/not started.
