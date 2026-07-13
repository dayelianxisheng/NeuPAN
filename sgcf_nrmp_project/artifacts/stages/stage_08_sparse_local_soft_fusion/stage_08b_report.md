# Stage 08B — Deployable Reliability-Only Semantic Safety Gate

## Status

`BLOCKED` — mandatory stop condition 3: current online features cannot distinguish correct and incorrect association.

Final decision: `RELIABILITY_NOT_IDENTIFIABLE`.

## Failure module and evidence

The failure occurs before rule implementation or training, at the information-identifiability boundary. A paired counterexample has identical values for every permitted online point/frame feature but opposite reliability labels. Any R2 rule or R3 MLP must output the same reliability for both.

## Baseline comparison

- R0 ALWAYS_ON retains the correct case but also trusts the incorrect case.
- R1 BASIC_RULE_GATE correctly closes RGB dropout, stale images, invalid projections, and UNKNOWN labels, as already validated in Stage 07; it cannot detect the counterexample.
- R2 OBSERVABLE_CONSISTENCY_RULE_GATE receives identical entropy, border, range-edge, semantic-edge, and transition-consistency evidence for both cases; it cannot separate them.
- R3 LIGHTWEIGHT_LEARNED_RELIABILITY_GATE cannot map one identical feature vector to both 1 and 0. Training would learn dataset prevalence rather than association correctness.

No threshold can simultaneously guarantee high normal retention and close the indistinguishable incorrect case. Raising reliability preserves both; lowering it shuts down both and can violate the 95% correct-semantic retention objective.

## Reliability Gate behavior still available

Deterministic hard shutdown remains valid for directly observable failures: RGB dropout, image age beyond threshold, invalid projection, and UNKNOWN. It is not evidence that calibration correctness is identifiable.

## Semantic and geometry impact

No semantic-margin or exact-geometry code was changed. Stage-07 bounds remain `[0,0.35]`. Stage-05 exact geometry remains the safety branch, so disabling semantics leaves geometry-only planning intact.

## Options

1. Provide an independently observable calibration-health signal from an approved online calibration monitor.
2. Add causal temporal consistency/history and evaluate whether it resolves the pair; do not use future frames.
3. Conservatively disable semantics whenever alignment health is not externally verified.
4. Keep only R1 for dropout/staleness/invalid/UNKNOWN shutdown and make no claim that it detects silent misalignment.

Recommended: option 4 now, with option 1 as a separately scoped future research task. Do not train R3 on the current features.

## Downstream effect

Real RGB segmentation noise will not solve this ambiguity and can worsen it. Planner integration remains blocked for learned semantic reliability, but exact geometry safety is unaffected. Stage 09 was not started.
