# Stage 10H Early-stopping Policy Repair

## Root cause

Stage 10G showed that the original policy stopped at epoch 24, before validation first learned ROBOT (28), HUMAN (38), and VEHICLE (45). The failure was a lifecycle policy defect, not evidence of a validation pipeline, metric, loss, weight, or pure domain-gap defect.

## Fixed policy

```text
maximum_epochs = 100
minimum_training_epochs = 60
early_stopping_patience = 20
early_stopping_min_delta = 1e-4
monitor = validation mean IoU
```

No actual early stop or class-collapse stop was permitted through epoch 60. After warm-up, collapse required all three core validation recalls to remain zero for five consecutive epochs.

Checkpoint ranking remained validation mIoU, HUMAN IoU, HUMAN recall, then negative validation loss. Every new best checkpoint was atomically saved and reloaded before early-stopping or reporting logic.

## Result

The retry reached epoch 100 and selected epoch 100. First positive validation recall occurred at epoch 28/38/45 for ROBOT/HUMAN/VEHICLE, confirming that the warm-up repaired the premature stop. Validation readiness passed, but the subsequent one-time test failed the fixed HUMAN-recall gate.
