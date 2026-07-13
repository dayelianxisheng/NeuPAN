# Stage 06 — Learned Geometry Interface Audit and Architecture Decision

## Status

`COMPLETE WITH ARCHITECTURE DECISION`

Decisions:

```text
REPLACE_WITH_EXACT_GEOMETRY_FOR_FINAL_SYSTEM
KEEP_LEARNED_GEOMETRY_FIELD_AS_RESEARCH_ABLATION_ONLY
```

## Objective and outcome

Stage 06 audited whether the existing Stage-04 LiDAR clearance model could enter the Stage-05 NRMP-like planner through a reusable scene encoding. The audit found that its point encoder is query-conditioned: points are transformed into each query frame and query-dependent local coordinates and squared distances are encoded. The current checkpoint therefore cannot encode a scene once and reuse it for many queries. Changing that dependency would change the model architecture and require retraining, both outside the approved scope.

This is an architecture selection, not a code failure. Stage 05 already supplies exact observable distance and gradient at CPU online P95 of 17.03–23.18 ms in the evaluated core scenarios. A learned geometry planner would still require exact observable recheck. The final system therefore uses exact geometry as its physical safety branch and concentrates learning on RGB–LiDAR semantic margin and reliability.

## Final architecture

```text
Exact LiDAR observable geometry: d_geo, g_geo
RGB–LiDAR semantic fusion: m_sem >= 0, reliability r
d_geo + g_geo^T(q-q_nom) + slack >= d_safe + r*m_sem
Trust-Region NRMP-like QP -> [v, omega]
```

RGB cannot increase geometric clearance. When RGB fails, `r -> 0` and the system becomes the Stage-05 exact LiDAR planner. Complete world geometry remains offline-evaluation-only. The first version does not predict future dynamic-obstacle trajectories.

## Work performed

- Read and audited the required Stage 04/05 reports, metrics, model flow, and execution plan.
- Revised the execution plan's final architecture, paper contributions, Stage-04 role, Stage-06 result, and Stage-07/08 boundaries.
- Revised the learned clearance-field architecture note.
- Preserved all Stage-04 code, checkpoint, metrics, and figures unchanged.
- Created the Stage-06 decision artifacts in this directory.

No model integration, training, RGB implementation, PointPainting implementation, Stage-07 code, network access, or Git mutation was performed.

## Verification

- Documentation consistency search: passed.
- Protected-directory worktree check: no new changes.
- Modified paths are limited to `sgcf_nrmp_project/docs/` and this Stage-06 artifact directory.

Stage 07 was redefined but not started. Stop after this report pending human acceptance.
