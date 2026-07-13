# Stage 10C Single-image Residual and Optimization Audit

## Decision

```text
BLOCKED_OPTIMIZATION_CONVERGENCE
```

The same frozen scene passed metric and direct-logits sanity, but the one allowed
single-image recheck after a finite-step optimization fix did not meet the full
all-pixel/class criteria. Stage 10C stops without four/48-image work.

## Frozen sample

```text
scene_id = image_id = 0
geometry_seed = 10000
appearance_seed = 10001
camera_seed = 10002
RGB SHA-256 = e74f3e9e3eb80ce611a404aff30103540c515ad46da5cbfe13aea2939744bb27
label SHA-256 = 76eff64116cf5a7dd9fcd4a9fe4d6448dd00b1e566a824d8170a7e6ca40b2325
```

All diagnostics and the final recheck use exactly these bytes.

## Residual localization at the Stage 10B endpoint

Overall 6,057/19,200 pixels are wrong. By GT class, error rates are UNKNOWN
38.43%, STATIC 0%, HUMAN 18.89%, VEHICLE 0.49%, and ROBOT 75.15%. ROBOT is
predicted primarily as HUMAN (537 pixels), then UNKNOWN (280), VEHICLE (51), and
correct ROBOT (287).

ROBOT failure is not confined to its antenna or boundary. Recall is 0.188 in the
main body, 0.326 in the upper structure, 0.305 in the antenna, 0.588 on the
boundary, and only 0.133 in the eroded interior. This excludes a pure
`BOUNDARY_OR_THIN_STRUCTURE_LIMITATION` explanation and shows strong
ROBOT→HUMAN confusion inside the body.

UNKNOWN errors are also not boundary-only: 5,061 UNKNOWN pixels are predicted as
foreground. Semantic-boundary error is elevated (43.12% within one pixel), but
the broad background false activation means hard-edge aliasing is not the sole
cause. The renderer applies RGB blur without blurring the hard label, so some
boundary-label noise is present and retained as a limitation.

## Local consistency and visual identifiability

After Stage 10A, texture is clipped to instance masks and the ROBOT antenna has a
consistent label. The renderer uses no antialiasing, although RGB-only blur can
soften hard edges. The frozen train image's quantized 5×5 patch audit finds
19,121 unique hashes and zero hashes shared across semantic classes. Under this
finite diagnostic there is no evidence for a large identical-local-patch
ambiguity block. This does not establish real-image identifiability.

## Loss and metric sanity

The label-copy evaluator returns pixel accuracy, macro F1, and all class recalls
of exactly 1. Direct per-pixel trainable logits reduce the same weighted CE from
`1.6094377` to `0.0000445`, reaching perfect metrics. Thus the target, CE,
optimizer, and evaluator can represent and optimize the exact mask; no hidden
loss/metric implementation failure is observed.

## Bounded convergence and class weights

Two 600-step diagnostics were run on scene 0 only:

| Method | Relative loss | Accuracy | Macro F1 | HUMAN recall | ROBOT recall |
|---|---:|---:|---:|---:|---:|
| D0 unweighted CE | 0.05162 | 0.97635 | 0.93321 | 0.84520 | 0.84589 |
| D1 current sqrt-weighted CE | 0.08178 | 0.96651 | 0.86772 | 0.86378 | 0.57922 |

D1's recent loss slope remained negative, so the original 80 steps were clearly
insufficient and the model had not plateaued. D0 improved aggregate/ROBOT results,
but changing weights together with steps would confound the selected fix; it was
rejected for this Stage 10C recheck. Current loss is already CE-only, so no Dice
comparison or loss change applies.

## Selected one minimal fix

```text
root_cause = insufficient and class-unstable single-image optimization at 80 steps
selected_minimal_fix = finite single-image optimizer steps 80 -> 1200
```

Everything else remained fixed: scene bytes, tiny architecture (118,341
parameters), D1 loss/weights, learning rate, RGB scaling, no augmentation,
dropout, or weight decay. Rejected alternatives were loss/metric repair (sanity
passes), residual label repair (no systematic interior mismatch demonstrated),
class-weight change (would be a second change), CE-only change (already CE-only),
and width doubling (capacity preconditions were not met before selecting the
optimization fix).

## One final single-image recheck

After 1,200 steps:

| Metric | Result | Required |
|---|---:|---:|
| Relative loss | 0.06058 | ≤0.10 |
| Pixel accuracy | 0.97927 | ≥0.98 |
| Macro F1 | 0.90967 | ≥0.95 |
| UNKNOWN recall | 0.99560 | ≥0.95 suggested |
| STATIC recall | 0.99900 | ≥0.95 |
| HUMAN recall | 0.63932 | ≥0.95 |
| VEHICLE recall | 0.99918 | ≥0.95 |
| ROBOT recall | 0.91082 | ≥0.95 |

The loss and UNKNOWN/STATIC/VEHICLE metrics pass, but accuracy is marginally low,
macro F1 and HUMAN/ROBOT recalls fail. Class recalls oscillate materially between
800–1,200 steps even while loss declines (for example HUMAN 0.896→0.639 and
ROBOT 0.646→0.911 from step 1,100 to 1,200). Finite additional steps alone do not
produce stable class-wise memorization. Immediate-stop condition 8 applies.

## Final interpretation and impact

The pipeline is not blocked by metric identity, direct-logits optimization,
gross mapping, or a total gradient disconnect. It remains blocked by unstable
single-image class-wise convergence under the current tiny model/weighted CE.
Because the single allowed recheck failed, no capacity comparison, further class
weight change, second recheck, four/48-image run, complete training, validation/
test evaluation, PointPainting, Semantic Margin, CPU benchmark, Planner,
Stage 09B, ROS, or Gazebo was performed.

A future separately authorized step must choose between a controlled weighting/
optimization investigation or a capacity audit; it must not combine both or
reuse test data. Real RGB and deployment remain unvalidated.
