# Stage 08 Final Decision

```text
STAGE_08A_COMPLETE
COMPLETE WITH NEGATIVE DESIGN DECISION
RELIABILITY_ONLY_NO_RECOVERY
STAGE_08B_BLOCKED
RELIABILITY_NOT_IDENTIFIABLE
```

Stage 08A established that sparse local candidate recovery misses its entry coverage gate. Stage 08B established a stronger information-theoretic limitation: silent alignment errors inside uniform semantic regions cannot be distinguished from correct association using the permitted single-frame online features.

The retained deployable behavior is a basic hard shutdown for directly observable failure states only. It must not be described as a general calibration-reliability predictor. Exact geometry remains unchanged and semantics must be disabled when alignment health is uncertain.
