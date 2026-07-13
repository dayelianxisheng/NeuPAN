# Stage 10 Progress Report

## Current authoritative status

```text
BLOCKED_OPTIMIZATION_CONVERGENCE
```

Stage 10H repaired the early-stopping policy, completed the authorized formal
retry, passed validation readiness, froze the validation-selected checkpoint
and confidence policy, and performed the one allowed test evaluation. Test
HUMAN recall was `0.71340`, below the fixed `0.80` gate, so downstream
PointPainting, Semantic Margin, robustness, and CPU evaluation were not run.
Stage 10I subsequently kept Test frozen and performed one optimizer-state-preserving validation-only continuation. Aggregate validation metrics improved, but HUMAN recall failed the simultaneous diagnostic gate and stopped after 20 epochs without a new high. Stage 10J then completed the final authorized low-learning-rate stabilization attempt from epoch 145. No validation epoch met all hard feasibility conditions, so no further tuning is authorized for the current configuration. The report below preserves earlier diagnostic states as history.

## Original Stage 10 stop decision (superseded by Stage 10A–10E follow-ups)

```text
BLOCKED_MODEL_OR_DATA_PIPELINE
```

Stage 10 stopped at the mandatory 48-image overfit gate. Full smoke training,
test evaluation, predicted PointPainting, semantic-margin comparison, robustness
evaluation, and CPU benchmarking were not started. No Planner closed loop,
Stage 09B, ROS, Gazebo, networking, dependency installation, or upstream change
was performed.

## Blocking stage

The blocking point is step 3 of the required training sequence: overfitting a
small 32–64-image subset. With 48 training images, weighted cross-entropy loss
decreased from `1.5663416385650635` to `1.1782216429710388`, a relative value of
`0.7522124254134085`. This did not satisfy the predeclared significant-overfit
gate (`final < 0.55 * initial`), so the script exited before full training.

## Data source

No local real RGB semantic dataset or eligible cached RGB weights were found.
Stage 07 `rgb_debug_image` directly fills objects with `visual_color` and was
rejected as training input due to its fixed class-color shortcut. A separate
synthetic Stage 10 appearance renderer generated 120 deterministic scenes split
80/20/20 by scene ID. It uses only NumPy and Pillow and records disjoint geometry,
appearance, and camera seeds.

## Visual identifiability

The new synthetic renderer makes classes observable through coarse structure:
STATIC box/wall/column, HUMAN head/torso proportions, VEHICLE low wide body and
wheels, and ROBOT chassis/module/antenna. All classes share the same randomized
color palette; classes are shuffled across image slots. Texture, background,
lighting, exposure, contrast, blur, noise, scale, and occlusion vary. Human
inspection confirms that examples are structurally distinguishable, so the stop
status is not `BLOCKED_VISUAL_IDENTIFIABILITY`.

## Label-leakage risk

- Stage 07 RGB debug colors: prohibited, high shortcut risk.
- New model input: current RGB only.
- Semantic and instance masks: labels only, never model inputs.
- Numeric filenames/scene IDs do not encode class.
- Scenes and all three seed domains are disjoint across splits.
- Remaining risk: the programmatic shapes are simplified synthetic icons; their
  structural templates may still be easier than real imagery and cannot support
  a real-camera claim.

## Model performance

The Tiny U-Net-style model was initialized from scratch; no pretrained weight was
used. Only the 48-image overfit-gate loss is available. No validation checkpoint
or test prediction exists because continuing would violate the mandatory stop
condition.

## HUMAN metrics

Not evaluated. HUMAN IoU and recall are unavailable because the overfit gate
failed before validation/test inference. Stage 10 cannot be declared successful.

## PointPainting gap

Not evaluated. Stage 07 Hard PointPainting remains frozen and unchanged. No
predicted semantic map was accepted for PointPainting evaluation.

## Semantic Margin gap

Not evaluated. Stage 07 Semantic Margin remains frozen and unchanged. There are
no predicted-margin MAE, miss, false-activation, or bound results.

## CPU latency

Not evaluated. Training stopped before an accepted checkpoint existed, so model
and total perception-pipeline P95 values would not be meaningful.

## Information boundary

The implemented dataset/model path accepts current RGB only. Semantic GT,
instance GT, depth GT, LiDAR class, world geometry, hidden obstacles, margin GT,
future frames, and calibration-error truth are not model inputs. Oracle masks are
stored only as loss/evaluation targets. No Planner or world-geometry path was
invoked.

## Options

1. **Recommended, separately authorized diagnostic turn:** inspect per-class
   pixel counts, a few target overlays, gradient/loss components, and predictions
   on the 48-image subset; then correct a demonstrated data-pipeline or model
   defect without changing Stage 05/07/09 definitions. Re-run the same gate once.
2. Simplify the synthetic task only if the audit demonstrates label/rendering
   ambiguity. This risks making the domain less representative and must retain
   class-independent colors and split isolation.
3. Provide a licensed local real RGB semantic dataset with an independent test
   split. This changes the possible final decision but requires a new explicit
   authorization and provenance audit.

The recommended next action is option 1. Broad hyperparameter search, larger
training data, pretrained downloads, and Planner modification are not acceptable
workarounds.

## Impact

- **Real RGB:** no deployment evidence; synthetic training is not validated.
- **Stage 09B:** unaffected and not started; its planner failure-mode debt remains
  separate.
- **ROS/Gazebo:** remain blocked because no accepted RGB checkpoint or offline
  Oracle-to-predicted semantic gap exists.

Stage 10 stops here.

## Stage 10H final follow-up

The repaired policy used 100 maximum epochs, 60 minimum training epochs,
patience 20, and mIoU `min_delta=1e-4`. The formal retry reached epoch 100 and
passed validation readiness (mIoU `0.75563`, macro F1 `0.85422`, HUMAN recall
`0.77804`, VEHICLE recall `0.76422`, ROBOT recall `0.85118`). Validation chose
`U0_argmax_always` and froze checkpoint/thresholds before the one-time test.

Test mIoU was `0.67510`, but HUMAN IoU was `0.57726` and HUMAN recall was
`0.71340`. The fixed HUMAN recall gate therefore failed. Current authoritative
decision: `BLOCKED_HUMAN_RECALL`. See `stage_10h_final_report.md`.

## Stage 10I validation-only follow-up

The source epoch-100 checkpoint and optimizer restored exactly. Train/validation
HUMAN recall at epoch 100 was `0.92222/0.77804`, with validation errors dominated
by UNKNOWN (`10.99%`) and ROBOT (`10.53%`). The one continuation ran epochs
101–146 and stopped after 20 epochs without a new HUMAN-recall high.

The mIoU-selected epoch-145 diagnostic checkpoint reached validation mIoU
`0.83307`, macro F1 `0.90478`, HUMAN IoU `0.65543`, VEHICLE recall `0.85727`,
and ROBOT recall `0.92553`, but HUMAN recall was only `0.75161`. An isolated
HUMAN peak of `0.88710` at epoch 126 coincided with mIoU and VEHICLE failures;
no epoch met all gates. Current status: `BLOCKED_OPTIMIZATION_CONVERGENCE`.
The original Test was not reopened. See `stage_10i_human_recall_report.md`.

## Stage 10A follow-up

Stage 10A subsequently found and fixed a systematic renderer alignment defect
(unclipped texture and an RGB-only ROBOT antenna). The one authorized recheck of
the same train scene IDs 0–47 still failed with relative loss
`0.7467831455009948` versus the unchanged `< 0.55` requirement. The current
follow-up decision is `BLOCKED_UNRESOLVED_PIPELINE`. See
`stage_10a_diagnosis_report.md`; full Stage 10 remains blocked.

## Stage 10B follow-up

Stage 10B confirms class collapse to UNKNOWN/STATIC but finds valid class mapping,
broad class presence, finite nonzero gradients, real parameter updates, and no
BatchNorm. The mandatory single-image extreme-overfit diagnostic still fails
(`relative_loss=0.37930947`, ROBOT recall `0.24848485`), so the ordered diagnosis
stops before four-image/loss-weight comparison and before any new 48-image gate.
Current decision: `BLOCKED_UNRESOLVED_PIPELINE`. See
`stage_10b_diagnosis_report.md`.

## Stage 10C follow-up

Stage 10C passes label-copy and direct-logits sanity and localizes the largest
residuals to broad UNKNOWN false activation and ROBOT→HUMAN confusion, including
ROBOT interior. A single finite-step fix (80→1200 steps) passes the loss ratio but
fails accuracy, macro F1, HUMAN recall, and ROBOT recall criteria. Current
decision: `BLOCKED_OPTIMIZATION_CONVERGENCE`. See
`stage_10c_diagnosis_report.md`. No second fix or downstream stage was started.

## Stage 10D follow-up

Stage 10D fixes train scenes 0–3 and fairly compares identical-initialization
L0/L1 runs. L0 unweighted CE fails; L1 current weighted CE passes with accuracy
`0.99785`, macro F1 `0.99484`, and all recalls above `0.997`. Current weighted CE
is retained, the L1 comparison is the authoritative four-image recheck, and the
status is `FOUR_IMAGE_PIPELINE_VALIDATED` / `READY_FOR_48_IMAGE_OVERFIT_RECHECK`.
No 48-image run was started. See `stage_10d_diagnosis_report.md`.

## Stage 10E follow-up

The separately authorized Stage 10E authoritative 48-image overfit recheck is
complete:

```text
48_IMAGE_OVERFIT_GATE_PASSED
READY_FOR_FULL_STAGE10_TRAINING
```

The only run used repaired train scene IDs 0–47, current Stage 10D weighted CE,
the unchanged 118,341-parameter model, and 5,000 fixed optimizer steps. It
reached final/initial loss `0.002985`, accuracy `0.998143`, macro F1 `0.995166`,
and all class recalls above `0.9976`, without class collapse. This overfit result
validates the training pipeline only; full training and every downstream Stage
10 evaluation remain not executed.

## Stage 10F pre-training stop

The first Stage 10F attempt stopped before any optimizer step with:

```text
BLOCKED_DATA_INCONSISTENCY
```

The configured class-weight values exactly match Stage 10E, but the new audit
cast them to `float32` before comparing with the Stage 10E `float64` JSON at an
absolute tolerance of `1e-12`. The resulting maximum rounding difference was
`2.8243541061456767e-08`. Per the mandatory static-failure stop rule, this
audit-only issue was not repaired and training was not automatically rerun.
See `stage_10f_training_report.md`.

## Stage 10F-A audit fix and resumed training

The authorized dtype-aware class-weight audit passed: float64 source difference
was `0`, float32 runtime cast difference was `2.8243541061456767e-08`, and the
audited runtime tensor was used directly by weighted CrossEntropyLoss. The
single full training run then executed 24 epochs before early stopping. All 24
validation epochs had HUMAN, VEHICLE, and ROBOT recall equal to zero, so the
current authoritative Stage 10F decision is:

```text
BLOCKED_CLASS_COLLAPSE
```

No test, PointPainting, Semantic Margin gap, robustness, or CPU benchmark was
executed. A secondary threshold-summary `KeyError` occurred after the epoch
loop, but the validation collapse already independently required stopping.

## Stage 10G lifecycle diagnosis

The single 50-epoch diagnostic replay reproduces original best epoch 14 and
simulated stop epoch 24. With early stopping disabled only for diagnosis,
validation ROBOT/HUMAN/VEHICLE recall first becomes positive at epochs 28/38/45,
and the diagnostic best moves to epoch 49. Train and validation follow similar
timelines; split preprocessing, labels, metric isolation, deterministic batch
coverage, and weighted-loss contributions pass. The authoritative decision is:

```text
BLOCKED_EARLY_STOPPING_POLICY
```

The threshold-summary KeyError and atomic checkpoint ordering are repaired, but
the checkpoint remains diagnostic-only. No threshold selection, test, or
downstream evaluation was executed. See `stage_10g_lifecycle_report.md`.

## Stage 10J final stabilization attempt

Stage 10J loaded the complete epoch-145 AdamW state, preserved all moments and
non-learning-rate fields, and changed only the learning rate from `0.002` to
`0.0002`. One fixed continuation covered epochs 146–195. The original Test and
the planned new audit split were not accessed.

The lower rate substantially reduced metric variation but did not recover the
required multi-objective point. Best validation HUMAN recall was `0.75610` at
epoch 146; best validation mIoU was `0.83246` at epoch 148, where HUMAN recall
was `0.75438`. Across all 50 epochs HUMAN recall ranged only from `0.74810` to
`0.75610`. There were zero feasible epochs and no three-epoch feasible interval.
The final decision is `BLOCKED_OPTIMIZATION_CONVERGENCE`.

```text
NO_FURTHER_STAGE10_TUNING_AUTHORIZED_FOR_CURRENT_CONFIGURATION
```
