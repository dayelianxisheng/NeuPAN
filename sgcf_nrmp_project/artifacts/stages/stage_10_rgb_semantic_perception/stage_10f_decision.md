# Stage 10F Decision

## Current authoritative decision

```text
BLOCKED_CLASS_COLLAPSE
```

The authorized audit correction passed, after which the only full training run
executed 24 epochs and stopped by validation early stopping. HUMAN, VEHICLE, and
ROBOT validation recall remained exactly zero at every epoch, so the model
persistently predicted only UNKNOWN/STATIC. No test or downstream evaluation
was run. A secondary `KeyError` occurred during validation threshold-summary
construction after the training loop; no accepted checkpoint was produced.

## Superseded historical decision

> `SUPERSEDED_PRETRAINING_AUDIT_FALSE_POSITIVE`: retained as historical evidence.
> No optimizer step or train/validation/test evaluation occurred before the
> authorized audit precision correction.

```text
SUPERSEDED_PRETRAINING_AUDIT_FALSE_POSITIVE
```

The stop occurred before training because an audit-only `float32` cast created a
maximum `2.8243541061456767e-08` difference that failed a `1e-12` comparison
against the Stage 10E `float64` reference. The YAML and Stage 10E weight values
are otherwise exactly equal, and authoritative scene 0–47 hashes passed.

No automatic repair or rerun was performed. Stage 10F requires separate
authorization to correct the audit comparison and restart.
