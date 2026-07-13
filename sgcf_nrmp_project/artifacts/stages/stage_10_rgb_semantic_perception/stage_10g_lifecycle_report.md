# Stage 10G Training Lifecycle Diagnosis

## Decision

```text
BLOCKED_EARLY_STOPPING_POLICY
```

The single authorized diagnostic replay used the exact Stage 10F seed,
initialization, model, weighted CrossEntropy, class weights, AdamW optimizer,
learning rate, batch size, deterministic order, train split, validation split,
normalization, resolution, and no-augmentation policy. It ran for the fixed
50-epoch ceiling while simulating—rather than obeying—the original early stop.
No test data, PointPainting, Semantic Margin, robustness, CPU benchmark,
Planner, Stage 09B, ROS, or Gazebo was accessed.

## Static lifecycle audit

The corrected lifecycle is:

```text
initialize model/optimizer
-> train epoch
-> stateless train evaluation
-> model.eval + no_grad validation
-> stateless validation evaluation
-> compare frozen best key
-> atomically save/fsync/rename/reload diagnostic checkpoint
-> update simulated early-stopping counter
-> record metrics/report
```

Train and validation metrics construct independent confusion matrices on every
call; no state is shared across splits or epochs. Each epoch explicitly starts
with `model.train()`, while validation uses `model.eval()` inside
`torch.no_grad()`. The best checkpoint is now persisted immediately when the
lexicographic validation key improves, before early-stopping or reporting.

Stage 10F failed to persist epoch 14 because it retained `best_state` only in
memory and deferred `torch.save` until after threshold summary generation. The
later reporting exception therefore prevented all persistence even though it
did not alter training.

## Threshold-summary KeyError

The root cause was Python evaluation order inside one `metrics.update({...})`:
the `selection_score` expression read `metrics["static_to_human_rate"]` before
the same update inserted that key. This was not a missing semantic definition.

All U0/U1/U2 paths now call one fixed-schema builder with:

```text
human_to_static_rate
human_to_unknown_rate
static_to_human_rate
robot_to_human_rate
human_to_robot_rate
unknown_rate
human_recall
macro_f1
```

Zero denominators produce `{value: null, valid: false,
reason: zero_denominator}`. Missing fields raise an explicit schema error.
Threshold summary is independent of checkpoint saving. Formal threshold
selection remains:

```text
THRESHOLD_SELECTION_NOT_EXECUTED_DUE_TO_CLASS_COLLAPSE
```

## Train/validation data comparison

Both splits use `RGBSemanticDataset`, uint8 RGB converted to float32 `[0,1]`,
RGB channel order, 120×160 images, uint8 stored labels converted to long, and
IDs 0–4. Validation contains nonempty HUMAN, VEHICLE, and ROBOT labels with
nonzero metric denominators.

| Class | Train pixel fraction | Validation pixel fraction | Train presence | Validation presence |
|---|---:|---:|---:|---:|
| UNKNOWN | 0.73347 | 0.71300 | 80/80 | 20/20 |
| STATIC | 0.11673 | 0.12673 | 80/80 | 20/20 |
| HUMAN | 0.03218 | 0.03192 | 80/80 | 19/20 |
| VEHICLE | 0.05250 | 0.05813 | 80/80 | 20/20 |
| ROBOT | 0.06512 | 0.07022 | 80/80 | 20/20 |

Component area and width/height distributions overlap materially. There is no
evidence of a preprocessing, label mapping, or gross appearance-distribution
break between train and validation.

## Batch and weighted-loss audit

All ten deterministic batches contain all five classes in all eight images.
Every batch has nonzero HUMAN, VEHICLE, and ROBOT weighted-CE contribution.
For batch 0, contributions are approximately UNKNOWN `0.675`, STATIC `0.288`,
HUMAN `0.160`, VEHICLE `0.195`, and ROBOT `0.270`, summing to `1.588`.
The runtime weights exactly remain the audited Stage 10D/E/F values. Thus
minority pixels are present and participate in the objective; sampling or a
silently disabled weight is not the cause.

## Diagnostic replay results

The reproduced initial state hash is
`f52c92334e3602ead517dfdf6fe4709a5f2b04a3dad86a82f516aa08affa57d6`,
identical to Stage 10D/E/F. The simulated original policy again selects epoch
14 and stops at epoch 24 after patience 10.

Minority learning begins only after that point:

| Class | First positive train recall | First positive validation recall |
|---|---:|---:|
| ROBOT | epoch 27 | epoch 28 |
| HUMAN | epoch 37 | epoch 38 |
| VEHICLE | epoch 43 | epoch 45 |

At epoch 49, the diagnostic best validation mIoU is `0.39349`, macro F1
`0.49913`, HUMAN recall `0.60290`, VEHICLE recall `0.01133`, and ROBOT recall
`0.25659`. At epoch 50, train/validation recall respectively is HUMAN
`0.80477/0.64752`, VEHICLE `0.01590/0.01693`, and ROBOT `0.38810/0.31415`.
Both splits therefore begin minority learning on similar timelines; this is not
a train-learns/validation-zero generalization split and not a validation metric
lifecycle error.

## Early-stopping analysis

The original monitor is lexicographic validation mean IoU, HUMAN IoU, HUMAN
recall, then negative validation loss; patience is 10, minimum delta is zero,
there is no warm-up, the counter starts at epoch 1, and there is no learning-rate
scheduler. UNKNOWN/STATIC dominate the early mean-IoU changes. Epoch 14 becomes
best before minority prediction appears, and ten subsequent non-improvements
stop training at epoch 24—three epochs before the first train ROBOT recall and
four before validation ROBOT recall.

Stage 10E required thousands of optimizer steps to memorize 48 images. Original
Stage 10F stopped after 240 steps over 80 images; Stage 10G reaches only 500
steps at the fixed 50-epoch ceiling. This explains why the 48-image
memorization capacity did not appear within the original lifecycle and why even
epoch 50 still has weak VEHICLE recall. No optimizer, loss, weight, or data
change was tested.

Candidate future policies—minimum training epochs before early stopping, longer
patience, minority-recall warm-up monitoring, or a composite validation
metric—are recorded as proposals only and were not implemented.

## Checkpoint lifecycle

`stage10g_diagnostic_best_checkpoint.pt` was atomically written with file fsync,
rename, directory fsync, and immediate reload whenever diagnostic validation
improved. The final diagnostic best is epoch 49 and reload logits differences
were exactly zero. It includes epoch, model and optimizer states, validation
metrics, class map, hashes, weights, normalization, and seed. It is explicitly:

```text
DIAGNOSTIC_ONLY_NOT_ACCEPTED_FOR_STAGE10
```

## Answers to Stage 10G questions

1. In the replay, train core recalls are also zero through the original stop;
   they become positive only at epochs 27/37/43.
2. Train and validation begin learning on similar timelines; preprocessing,
   labels, metric state, and eval mode pass. A pure synthetic generalization gap
   is not supported.
3. Yes. Original stopping at epoch 24 precedes every core class's first positive
   validation recall.
4. Stage 10F deferred persistence until after threshold summary instead of
   saving immediately at epoch 14.
5. `static_to_human_rate` was read inside a dict update before insertion.
6. The KeyError occurred after training and did not change weights, but the
   deferred save order allowed it to erase the usable lifecycle output.
7. Stage 10E used far more optimization steps on 48 images; the full 80-image
   lifecycle stopped at 240 steps, before minority learning emerged.

## Final boundary and recommendation

Stage 10G validates the metric, input, loss-contribution, reporting-schema, and
checkpoint mechanics, but confirms the original early-stopping policy is
incompatible with the delayed minority-learning phase. Therefore it does not
select `TRAINING_LIFECYCLE_VALIDATED` and does not authorize a Stage 10F retry.
A separately approved policy-design step is required. Test, downstream
perception evaluation, Stage 09B, Gazebo, ROS, and real-camera work remain
blocked or unstarted.
