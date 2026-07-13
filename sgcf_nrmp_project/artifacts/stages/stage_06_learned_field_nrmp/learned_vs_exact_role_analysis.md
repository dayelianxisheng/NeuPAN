# Learned versus Exact Geometry Roles

| Property | Stage-05 exact geometry | Stage-04 learned geometry |
|---|---|---|
| Physical clearance | Exact rectangle-to-visible-point distance | Approximation |
| Gradient | Analytic/autograd over exact formula | Model autograd |
| CPU online timing | 17–23 ms planner P95 | No cacheable scene interface |
| Exact recheck needed | Native same definition | Required for safety |
| False-safe | None relative to observable point definition | 2/480 test samples |
| Final role | Main physical safety branch | Research ablation |

Stage 04 remains valuable for showing that a compact neural proxy can learn footprint clearance, for distance/gradient comparison, and for documenting the architecture tradeoff. It has no demonstrated advantage sufficient to displace the exact Oracle, especially while exact recheck remains necessary.

The final learned branch addresses a different problem: semantic risk that geometry alone cannot express. It may only add a nonnegative margin. This separation makes failure behavior explicit and prevents RGB errors from erasing LiDAR obstacles.
