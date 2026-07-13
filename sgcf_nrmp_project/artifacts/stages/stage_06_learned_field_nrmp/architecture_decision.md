# Architecture Decision: Exact Geometry with Learned Semantic Margin

## Decision

Adopt:

```text
REPLACE_WITH_EXACT_GEOMETRY_FOR_FINAL_SYSTEM
KEEP_LEARNED_GEOMETRY_FIELD_AS_RESEARCH_ABLATION_ONLY
```

## Stage-04 data flow

```text
points_xy + query_pose
  -> points_in_query_frame
  -> [local_x, local_y, range, squared_distance, valid]
  -> MaskedPointEncoder
  -> pooled query-conditioned feature
  -> query decoder
  -> observable clearance
```

The encoder inputs `local_x`, `local_y`, and squared distance all depend on the query pose. The model therefore repeats point encoding for every query even when queries are submitted as one batch. There is no query-independent `SceneEncoding` in the checkpointed architecture.

## Why caching requires retraining

Moving point encoding ahead of the query transform would change encoder inputs, feature statistics, pooling semantics, decoder inputs, and the checkpoint state-dict structure. Existing weights would no longer implement the trained function. A correct cached encoder would require a new architecture, dataset pass, training, calibration, and safety evaluation; wrapping raw points in an object would not satisfy “encode once” and would only disguise repeated encoding.

## Evidence from Stage 05

The batch analytic exact Oracle retains floating-point equivalence with Shapely and achieved online P95 of 17.03 ms for single obstacle, 23.18 ms for corridor, and 21.97 ms for narrow passage. Observable distance-plus-gradient P95 per SCP was below 0.55 ms. Thus exact geometry is already CPU-real-time and does not need a learned speed substitute.

## Exact recheck remains necessary

Stage 04 test MAE is 0.07308 m, near-boundary MAE 0.04746 m, gradient cosine 0.96195, and model false-safe 2/480. These are useful research results but not an independent safety guarantee. A learned planner would still require the Stage-05 exact observable recheck, weakening the engineering case for replacing an already-fast exact constraint source.

## Options considered

1. Redesign a cacheable learned scene encoder and retrain: rejected for current scope and unnecessary for exact geometry performance.
2. Force-integrate the query-conditioned checkpoint as a batched ablation: rejected because it violates the required interface and would not represent the intended deployment architecture.
3. Use exact geometry for physical safety and learn semantic margin/reliability: selected. It preserves exactness, CPU timing, graceful RGB degradation, and a clean future multimodal interface.

## Effect on paper contributions

The main contributions become CPU-real-time exact footprint clearance with trust-region planning, sparse RGB–LiDAR semantic fusion, nonnegative class-sensitive margin, reliability-based degradation, and explicit separation of physical geometry from learned semantic risk. “A learned geometry field replacing DUNE” is retained only as an ablation, not claimed as the final system contribution.

## CPU deployment impact

The safety-critical geometry path has deterministic analytic computation and no model backward pass. Learned compute is limited to semantic margin and reliability. With RGB absent or stale, `r -> 0`; the system runs the already validated exact LiDAR planner.

## Effect on later stages

Stage 07 now establishes projection, synchronization, semantic ground truth, nonnegative margin labels, and a PointPainting baseline without planner integration. Sparse Local Soft Fusion follows in Stage 08. Later integration may only add `r*m_sem` to the constraint right-hand side; it may not modify `d_geo` or `g_geo`.
