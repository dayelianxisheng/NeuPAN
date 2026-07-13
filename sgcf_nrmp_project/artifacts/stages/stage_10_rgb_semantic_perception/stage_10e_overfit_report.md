# Stage 10E Authoritative 48-image Overfit Gate Recheck

## Decision

```text
48_IMAGE_OVERFIT_GATE_PASSED
READY_FOR_FULL_STAGE10_TRAINING
```

This decision authorizes only a separately requested full Stage 10 training
run. Stage 10E stops here without validation/test evaluation, PointPainting,
Semantic Margin evaluation, CPU benchmarking, Planner work, Stage 09B, ROS, or
Gazebo.

## Frozen data and inherited pipeline

The single authorized run used the post-Stage-10A repaired train scenes 0–47,
exactly 48 images. The scene IDs, geometry/appearance/camera seeds, RGB and label
SHA-256 hashes, class counts, and presence flags are frozen in
`stage10e_48_image_selection.json`. All records belong to the train split. The
first four hashes were additionally matched byte-for-byte against the Stage 10D
authoritative selection. No scene was regenerated, replaced, or selected after
viewing results.

The run retained the Stage 10D pipeline without modification:

- `TinySemanticSegmentation`, 118,341 parameters, 120×160 RGB input;
- raw logits with five channels ordered UNKNOWN, STATIC, HUMAN, VEHICLE, ROBOT;
- current normalized square-root inverse-frequency weighted CrossEntropy;
- AdamW, learning rate 0.002, batch size 8, deterministic scene order;
- no augmentation, dropout, weight decay, pretrained weights, or test data.

The actual weights are `[0.3282637900, 0.8115540257, 1.5283809716,
1.2388608540, 1.0929403587]` in class-ID order 0–4. Recalculation from the
frozen 48 masks differs from Stage 10D by at most floating-point roundoff below
`1e-12`.

## Pre-training contract

The static gate confirmed logits `[8,5,120,160]`, targets `[8,120,160]`, target
dtype `torch.int64`, label IDs exactly 0–4, raw-logit CrossEntropy, UNKNOWN as a
normal class rather than `ignore_index`, finite inputs, valid labels, and full
optimizer coverage of every trainable parameter. The initial model state hash
is `f52c92334e3602ead517dfdf6fe4709a5f2b04a3dad86a82f516aa08affa57d6`,
the same initialization recorded by Stage 10D.

## Authoritative run

Exactly one run was executed for the fixed maximum of 5,000 optimizer steps.
No second seed, learning-rate search, batch-size search, weight search, early
restart, or best-checkpoint selection was performed.

| Metric | Result | Gate |
|---|---:|---:|
| Initial weighted CE | 1.585508 | — |
| Final weighted CE | 0.004733 | — |
| Final / initial loss | 0.002985 | < 0.55 |
| Training pixel accuracy | 0.998143 | anti-collapse evidence |
| Training macro F1 | 0.995166 | suggested ≥ 0.60 |
| UNKNOWN recall | 0.997603 | reported |
| STATIC recall | 0.999964 | reported |
| HUMAN recall | 0.998517 | > 0; suggested ≥ 0.50 |
| VEHICLE recall | 0.999301 | > 0; suggested ≥ 0.50 |
| ROBOT recall | 0.999736 | > 0; suggested ≥ 0.50 |

Predicted class fractions are 72.820% UNKNOWN, 11.943% STATIC, 3.470% HUMAN,
5.160% VEHICLE, and 6.607% ROBOT. They closely follow the frozen label
distribution and show no majority-class collapse.

## Error localization

Interior accuracy is `0.999990`; every foreground interior recall is `1.0`.
Boundary accuracy is `0.987748`, with all boundary class recalls above `0.9777`.
The remaining errors therefore concentrate almost entirely at hard semantic
boundaries. Core requested errors at the final step are:

- HUMAN→UNKNOWN: 46; HUMAN→STATIC: 0; HUMAN→ROBOT: 0;
- VEHICLE→UNKNOWN: 33; VEHICLE→STATIC: 0;
- ROBOT→UNKNOWN: 16; ROBOT→STATIC: 0; ROBOT→HUMAN: 0.

The four-image HUMAN/ROBOT separability result extends to the fixed 48-image
memorization problem: no direct HUMAN↔ROBOT error remains at the final step.

## Convergence interpretation

The best recorded loss is `0.001934` at step 4,100. The final loss remains far
below the hard gate. Over the last 20% of recorded points, the fitted slope is
`-3.00e-6` loss per optimizer step, but the loss range is `0.065998`: this is
classified as low-loss oscillation, not a perfectly monotone plateau. The final
all-class metrics still pass with substantial margin, and the authoritative
decision uses the final step rather than selecting the best point. This
oscillation should be handled by validation checkpoint selection only in a
future authorized full-training stage.

## Checkpoint scope

`stage10e_48_image_overfit_checkpoint.pt` is a diagnostic checkpoint only for
48-image pipeline verification, not the final Stage 10 model. Reloading it on
the same two train images produces a logits maximum absolute difference of
exactly `0.0`.

## Scope conclusion

Stage 10E proves that the fixed tiny model and weighted-CE pipeline can memorize
the authoritative repaired 48-image synthetic train subset without class
collapse. It does not establish validation/test generalization, predicted
PointPainting quality, Semantic Margin accuracy, CPU latency, or real-camera
deployment readiness.
