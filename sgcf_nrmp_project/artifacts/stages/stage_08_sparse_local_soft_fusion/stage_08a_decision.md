# Stage 08A Decision

Status: `COMPLETE WITH NEGATIVE DESIGN DECISION`

Archive markers:

```text
STAGE_08A_COMPLETE
RELIABILITY_ONLY_NO_RECOVERY
STAGE_08B_NOT_STARTED
```

Decision: `RELIABILITY_ONLY_NO_RECOVERY`

Stage 08B is not authorized. The strongest candidate sets, C5 radius-24 and C7 multiscale, reached only 93.28% mean correct-class coverage at 3 cm + 3°, below the 95% entry gate. At 1 cm + 1° they reached 96.46%, below the 99% normal-region target.

This is not a CPU or candidate-count failure. C5 uses 49 candidates and its N=360 extraction P95 is approximately 0.62 ms. C7 uses about 30 valid candidates on average. The remaining failure is candidate observability near borders, occlusion boundaries, and mixed-instance regions. Radius-24 raises mean semantic/instance ambiguity to 1.79 distinct labels per point, compared with 1.55 for radius-16.

At 5 cm + 5°, maximum coverage was 90.48%; recovery is not required there. The safe behavior is to detect ambiguity/miscalibration and close semantic reliability, leaving Stage-05 exact geometry unchanged. Training an association model now would conceal a known candidate-recall ceiling.

Options for a future redesign:

1. Add a GT-free projection-offset estimator before sparse search.
2. Use temporal neighboring-projection consistency, with no future frames.
3. Add adaptive anisotropic search driven by online image/point structure.
4. Revisit the 95/99 gates only with explicit user approval; do not tune on test scenes.

Recommendation: keep reliability-only safe degradation for the current design and redesign candidate generation before Stage 08B. No learned association or gate training should begin from this candidate set.
