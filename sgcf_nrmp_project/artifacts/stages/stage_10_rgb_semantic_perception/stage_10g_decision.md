# Stage 10G Decision

```text
BLOCKED_EARLY_STOPPING_POLICY
```

The simulated original lifecycle reproduces best epoch 14 and stop epoch 24.
With early stopping disabled only for the one bounded diagnostic replay,
validation ROBOT, HUMAN, and VEHICLE recall first become positive at epochs 28,
38, and 45. Train recalls begin on nearly the same timeline, while split
preprocessing, labels, metrics, batch coverage, class weights, and weighted-loss
contributions pass their audits.

The threshold-summary `KeyError` is fixed with a validated fixed schema, and
diagnostic best checkpoints are now atomically persisted before early-stopping
or reporting. The epoch-49 checkpoint reload is exact but remains:

```text
DIAGNOSTIC_ONLY_NOT_ACCEPTED_FOR_STAGE10
```

Formal UNKNOWN threshold selection was not executed, test was not accessed,
and Stage 10F was not retried. A separate authorization is required to design
and validate a revised early-stopping policy without changing the frozen model,
loss, weights, data, or renderer.
