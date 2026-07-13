# Stage 10D Decision

```text
FOUR_IMAGE_PIPELINE_VALIDATED
CURRENT_WEIGHTED_CE_RETAINED
READY_FOR_48_IMAGE_OVERFIT_RECHECK
```

L0 unweighted CE fails the frozen four-image gate and suppresses HUMAN/VEHICLE/
ROBOT. L1 current weighted CE passes with accuracy 0.99785, macro F1 0.99484,
and every class recall above 0.997. Train-only HUMAN/ROBOT crops are perfectly
separable in the bounded diagnostic. Therefore the proposed unweighted-loss fix
is rejected, current weighted CE is retained, and the fair L1 run is the
authoritative four-image recheck. No 48-image work is performed here.
