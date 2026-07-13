# Method Definition (Partial)

P0 uses exact observable distance and gradient with zero semantic margin. P1 uses Hard PointPainting class probabilities without explicit-failure shutdown. P2 applies the deterministic R1 gate: unavailable or stale RGB disables all semantic contribution; invalid projections and UNKNOWN points contribute zero.

For each nominal query, the provider computes point-to-rectangle distances over the same observable LiDAR points as exact geometry, then applies `max(0, d_geo - min_i(d_i-s_i))`. The result is fixed on the QP right-hand side for that SCP iteration. Exact geometry linearization and final recheck are unchanged.

