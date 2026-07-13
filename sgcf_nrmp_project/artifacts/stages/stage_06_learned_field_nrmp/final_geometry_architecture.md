# Final Geometry Architecture

```text
2D LiDAR
    ↓
Batched Exact Observable Geometry
    ├── exact distance d_geo
    └── exact gradient g_geo

RGB + LiDAR
    ↓
Sparse RGB–LiDAR Semantic Fusion
    ↓
Semantic Margin Head
    ├── nonnegative margin m_sem
    └── reliability r

d_geo + g_geoᵀ(q-q_nom) + slack
    >= d_safe + r · m_sem
    ↓
Trust-Region NRMP-like QP
    ↓
control [v, omega]
```

Invariants:

1. Exact geometry alone defines physical observable clearance.
2. Semantic margin adds category-sensitive distance; it never changes geometry.
3. RGB cannot increase `d_geo` or remove a LiDAR obstacle.
4. `m_sem >= 0` by construction.
5. Missing, stale, or unreliable RGB drives `r -> 0`.
6. At `r = 0`, behavior reduces to the Stage-05 exact LiDAR planner.
7. Complete world geometry is unavailable online and remains offline-evaluation-only.
8. The first version is reactive and does not predict dynamic-obstacle trajectories.
