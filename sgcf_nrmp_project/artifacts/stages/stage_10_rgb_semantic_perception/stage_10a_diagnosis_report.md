# Stage 10A Small-data Pipeline Diagnosis Report

## Decision

```text
BLOCKED_UNRESOLVED_PIPELINE
```

## Earliest failed diagnosis layer

Layer 1, RGB-label alignment. The renderer applied class-independent texture
across the whole object bounding box rather than clipping it to the current
instance mask. HUMAN, VEHICLE, and ROBOT therefore contained visible RGB texture
outside their semantic labels. The ROBOT antenna was also drawn only into RGB.

## RGB-label alignment

Twelve fixed train scenes were inspected as RGB, semantic label, alpha overlay,
class-colored mask, and instance-boundary overlay. Shapes and indices match and
labels contain only IDs 0–4, but code and overlays expose the systematic
foreground/UNKNOWN mismatch described above. No resize or flip occurs.

## Implemented minimal fix

Only the identified alignment defect was changed:

1. class-independent texture is now composed through the current instance mask;
2. the ROBOT antenna is written consistently to RGB, semantic, and instance
   images.

The original split, scene IDs, seeds, resolution, model width, loss family, and
`< 0.55` gate were retained. The same-seed dataset was regenerated. For the
diagnostic gate, stochastic augmentation and dropout were off and weight decay
was zero as specified by the Stage 10A diagnosis configuration.

## Diagnosis layers intentionally not run

The Stage 10A instruction says that after detecting pixel misalignment, fix it,
stop subsequent diagnosis, and only rerun the same 48-image gate. Therefore no
class-distribution/component analysis, single-image overfit, four-image overfit,
dedicated gradient-flow/parameter-update audit, normalization experiment, or
CE-vs-Dice comparison was executed. Their JSON files explicitly say `NOT_RUN`;
no values are fabricated.

## 48-image recheck

The same train scene IDs 0–47 were used once:

| Metric | Before | After alignment fix |
|---|---:|---:|
| Initial loss | 1.56634164 | 1.56525165 |
| Final loss | 1.17822164 | 1.16890355 |
| Relative loss | 0.75221243 | 0.74678315 |
| Required | < 0.55 | < 0.55 |
| Pass | no | no |

Auxiliary post-recheck metrics are training pixel accuracy `0.7328754`, macro F1
`0.2545702`, and recalls `[0.9203966, 0.5119493, 0, 0, 0]` for UNKNOWN, STATIC,
HUMAN, VEHICLE, and ROBOT. These do not replace the loss gate. The failed gate
and zero core-class recalls trigger immediate stop condition 9.

## Explicit root cause status

The alignment defect was real and fixed, but it was not the sole cause of the
failed gate. Because later diagnosis layers were intentionally skipped, the
remaining cause cannot safely be assigned to class imbalance, loss interface,
gradient flow, normalization, or model capacity. The correct decision is
`BLOCKED_UNRESOLVED_PIPELINE`, not a speculative capacity diagnosis.

## Remaining options

1. **Recommended:** in a separately authorized Stage 10A continuation, resume at
   layer 2 using the already fixed renderer: class pixel/component distribution,
   then loss interface, single-image overfit, four-image overfit, gradient flow,
   normalization, and loss components. Do not run the 48-image gate again until
   a second explicit defect is demonstrated and authorized.
2. If distribution proves core classes too small, select a balanced 48-image
   subset strictly from train without changing the split.
3. If single/four-image tests prove capacity insufficient after all interfaces
   pass, consider one small width increase below two million parameters.

No broad hyperparameter search, pretrained weight, test data, or Planner change
is recommended.

## Impact

- Full Stage 10 remains blocked; no accepted RGB checkpoint exists.
- Real RGB deployment has no supporting evidence.
- PointPainting, Semantic Margin gap, robustness, and CPU benchmark remain not
  evaluated.
- Stage 05/07/08/09 remain frozen and unaffected.
- Stage 09B, Planner closed loop, ROS, and Gazebo were not started.
