# Stage 10F-A Weight-audit Precision Fix

## 1. Original False-positive Condition

The first Stage 10F attempt stopped before optimization because the audit cast
the configured weights to `float32` and compared them against the Stage 10E
`float64` values using `atol=1e-12`. Normal float32 rounding reached
`2.8243541061456767e-08`, causing a false `BLOCKED_DATA_INCONSISTENCY` result.

## 2. Float64 Authoritative Comparison

The corrected source audit compares YAML and Stage 10E values as float64 in the
fixed order UNKNOWN, STATIC, HUMAN, VEHICLE, ROBOT. It records elementwise and
maximum differences, order equality, `atol=1e-12`, and `rtol=1e-12`. No dtype
conversion occurs before this definition-level comparison.

## 3. Float32 Runtime Cast

Only after source equality passes, the authoritative list is converted with
`torch.tensor(..., dtype=torch.float32)`. A separate audit compares the runtime
tensor with the float64 definition using dtype-aware `atol=rtol=1e-7` and
requires the tensor dtype to be exactly `torch.float32`.

## 4. Dtype-aware Tolerance Rationale

Float32 has about seven decimal digits of precision. The observed cast error is
normal representational rounding, below `1e-7`, and does not redefine the
authoritative weights. The float64 source comparison retains the much stricter
`1e-12` tolerance.

## 5. Evidence That Frozen Weights Did Not Change

The YAML and Stage 10E lists are elementwise identical before casting. No YAML
number, class order, normalization, loss, optimizer, learning rate, model,
renderer, resolution, dataset, or split was modified. CrossEntropyLoss retains
the exact audited runtime tensor object.

## 6. Optimizer-step Count Before Fix

```text
optimizer_steps_before_fix = 0
validation_metrics_read_before_fix = false
test_metrics_read_before_fix = false
```

The historical false-positive report is retained.

## 7. Authorization to Resume the Single Stage 10F Run

The user explicitly authorized this audit-only correction and continuation of
the original single Stage 10F run after all true static checks pass. The failed
pre-optimizer audit is not counted as a training seed.

The corrected audit subsequently passed with source maximum difference `0.0`,
runtime cast maximum difference `2.8243541061456767e-08`, and the audited tensor
used directly by CrossEntropyLoss. The resumed unique run later stopped for the
independent `BLOCKED_CLASS_COLLAPSE` condition documented in
`stage_10f_training_report.md`.
