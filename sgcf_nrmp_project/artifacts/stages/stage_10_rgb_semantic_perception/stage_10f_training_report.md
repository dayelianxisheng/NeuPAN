# Stage 10F Training Report

## Current authoritative decision

```text
BLOCKED_CLASS_COLLAPSE
```

After the authorized Stage 10F-A precision correction, all true pretraining
checks passed and the one allowed full train/validation run started from the
fixed seed. It executed 24 epochs before validation early stopping. Across all
24 epochs, validation recall for HUMAN, VEHICLE, and ROBOT remained exactly
zero; predictions contained only UNKNOWN and STATIC. This is the earliest
scientific stop condition and prevents checkpoint acceptance, threshold
selection, test access, PointPainting, Semantic Margin evaluation, robustness,
and CPU benchmarking.

The best validation record was epoch 14: weighted CE `1.240416`, pixel accuracy
`0.668036`, macro F1 `0.251479`, and mean IoU `0.195805`. HUMAN/VEHICLE/ROBOT IoU
and recall were all zero. At epoch 24, validation mean IoU was `0.182576` and the
three core recalls remained zero. Train loss reached approximately `1.12466` at
best, so the fixed full-training budget did not reproduce the much longer
Stage 10E memorization behavior before early stopping.

After the epoch loop, the validation threshold-summary code also raised a
`KeyError` because `policy_metrics` referenced `static_to_human_rate` inside the
same `dict.update` expression before that key had been written. This is a
secondary pipeline defect. It did not cause the already-observed class collapse,
and no checkpoint had been persisted before the exception.

No test metric was read. The final Stage 10F outputs therefore remain:

| Area | Result |
|---|---|
| Train | 24 epochs; best loss ≈ 1.12466 |
| Validation | best mIoU 0.195805; macro F1 0.251479 |
| Validation HUMAN recall | 0 for every epoch |
| Validation VEHICLE recall | 0 for every epoch |
| Validation ROBOT recall | 0 for every epoch |
| Test | Not accessed |
| PointPainting | Not executed |
| Semantic Margin gap | Not executed |
| Robustness | Not executed |
| CPU latency | Not executed |
| Oracle-to-prediction gap | Not executed |

Recommended next action, requiring separate authorization, is a narrowly scoped
training-lifecycle diagnosis: explain why validation early stopping occurs
before the minority classes begin learning, and fix the threshold-summary
ordering bug before any new run. It must not change the frozen model, renderer,
loss, class weights, data split, or use test data. Stage 09B, Gazebo, ROS, and
real-camera work remain blocked/unstarted.

## Historical pretraining false-positive

> `SUPERSEDED_PRETRAINING_AUDIT_FALSE_POSITIVE`: this historical stop preceded
> the explicitly authorized Stage 10F-A precision fix. The false positive was
> caused by comparing float32 runtime values against float64 authoritative values
> with a `1e-12` tolerance. No optimizer step, validation metric read, test metric
> read, or downstream evaluation occurred before correction.

### Historical decision

```text
BLOCKED_DATA_INCONSISTENCY
```

Stage 10F stopped during its pre-training static audit. No optimizer step,
train/validation inference, test inference, PointPainting, Semantic Margin gap,
robustness evaluation, or CPU benchmark was executed.

## Earliest failed stage

The authoritative Stage 10E scene 0–47 hashes passed, and the configured YAML
weight values are textually/numerically identical to the Stage 10E JSON values.
The audit then converted the configured weights to `float32` for the future
PyTorch loss and compared those rounded values against the `float64` JSON values
with an absolute tolerance of `1e-12`.

The largest cast-induced difference is `2.8243541061456767e-08`, so the audit
emitted:

```text
BLOCKED_DATA_INCONSISTENCY: frozen class weights changed
```

This is an audit-implementation precision mismatch, not evidence that the
frozen Stage 10E weight definition or dataset changed. Nevertheless, the Stage
10F instruction explicitly requires stopping after a static-check failure and
forbids fixing and automatically rerunning, so the process stopped before
training.

## Available metrics

| Area | Result |
|---|---|
| Train metrics | Not evaluated |
| Validation metrics | Not evaluated |
| Test metrics | Not evaluated |
| HUMAN metrics | Not evaluated |
| PointPainting | Not executed |
| Semantic Margin gap | Not executed |
| CPU latency | Not executed |
| Oracle-to-prediction gap | Not executed |

No `best_rgb_semantic_model.pt` or Stage 10F training history exists because
zero optimizer steps ran. The Stage 10E diagnostic checkpoint remains separate
and was not reused as a full-training checkpoint.

## Clear blocking reason

The frozen weights are:

```text
[0.3282637900393733,
 0.8115540256535101,
 1.5283809715797676,
 1.238860853978437,
 1.0929403587489122]
```

Both configuration and Stage 10E reference contain exactly these values. The
failure arose solely because `float32` rounding was applied before a
`float64`-precision equality check.

## Options

1. **Recommended:** authorize a Stage 10F restart with one audit-only repair:
   compare the YAML and Stage 10E reference arrays as `float64` using the
   existing `1e-12` tolerance, then cast the already-verified values to
   `float32` only when constructing `torch.nn.CrossEntropyLoss`. This does not
   alter runtime weights, model, loss, data, or any frozen definition.
2. Compare the runtime `float32` arrays with a documented tolerance such as
   `1e-7`. This directly checks the tensor values but uses a looser, dtype-aware
   tolerance.
3. Do not restart Stage 10F. In that case all perception generalization and
   downstream offline evaluations remain unavailable.

The recommended option is 1 because it separates definition consistency from
runtime dtype conversion and preserves the strongest equality audit.

## Impact

- **Stage 09B:** unaffected and not started.
- **Gazebo/ROS:** not started; Stage 10 perception remains unavailable for
  integration.
- **Real camera:** still unvalidated; no synthetic generalization result was
  produced in this attempt.
- **Frozen upstream modules:** Stage 05/07/08/09 were not modified or executed.

Separate user authorization is required before repairing the audit and
restarting the single full Stage 10F training run.
