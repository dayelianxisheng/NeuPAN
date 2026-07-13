# Original Stage 08 Blocking Report

Status: `BLOCKED_NEEDS_DIFFERENT_FUSION_DESIGN`

The original 3×3/5×5 design stopped before training. With `fx=180`, 5° rotation creates approximately 15.75 px displacement; 5 cm translation adds 2.25–5 px over the evaluated depth range. At 5 cm + 5°, Hard, uniform 3×3, and uniform 5×5 all achieved 66.67% class coverage, and none of the Hard-misclassified points had the correct class within the local window. A learned selector cannot recover a candidate that is absent.

Stage 08 was therefore split. Stage 08A audits sparse multiscale candidate coverage without training. Stage 08B remains unauthorized.

## Stage 08A outcome

Stage 08A also stopped at its mandatory coverage gate. Best coverage was 96.46% at 1 cm + 1° and 93.28% at 3 cm + 3°, below the required 99% and 95%. Radius-24 and multiscale search stayed below 64 candidates and below 1 ms P95 at N=360, so compute is not the blocker. Expanding radius increased semantic and instance ambiguity without reaching the entry threshold. Final decision: `RELIABILITY_ONLY_NO_RECOVERY`; Stage 08B must not start without a different candidate design.

This is a completed negative design result, not an implementation failure. Local 3×3/5×5 coverage is insufficient for severe offsets; radius-24 improves coverage but misses the original entry gate and increases class/instance ambiguity. No association recovery module was trained.
