# Stage 10I Decision

```text
BLOCKED_OPTIMIZATION_CONVERGENCE
```

The epoch-100 checkpoint restored model and optimizer state exactly, and the single validation-only continuation ran from epoch 101 through 146 without reading the original Test. Aggregate validation mIoU, macro F1, VEHICLE recall, and ROBOT recall improved substantially, but HUMAN recall oscillated and then went 20 epochs without a new high.

No single validation-selected checkpoint met all simultaneous gates. Epoch 126 reached HUMAN recall `0.88710`, but mIoU was `0.77372` and VEHICLE recall was `0.66943`. The mIoU-selected diagnostic checkpoint at epoch 145 reached mIoU `0.83307`, macro F1 `0.90478`, VEHICLE recall `0.85727`, and ROBOT recall `0.92553`, while HUMAN recall was only `0.75161`.

The diagnostic checkpoint remains:

```text
VALIDATION_ONLY_DIAGNOSTIC
NOT_EVALUATED_ON_UNTOUCHED_TEST
NOT_ACCEPTED_AS_FINAL_STAGE10_MODEL
```

Stage 10I is not ready to generate or evaluate a new audit split.
