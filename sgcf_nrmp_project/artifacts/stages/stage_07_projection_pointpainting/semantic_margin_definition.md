# Semantic Margin Ground Truth

Stage 07 uses engineering defaults, not a final safety standard:

| Class | Extra margin |
|---|---:|
| UNKNOWN | 0.00 m |
| STATIC_OBSTACLE | 0.00 m |
| HUMAN | 0.35 m |
| VEHICLE | 0.20 m |
| ROBOT | 0.15 m |

For query pose `q`, every current observable LiDAR point supplies the same exact rectangle-to-point distance used by `d_geo`. The effective semantic clearance is `min_j[d_j(q)-margin(class_j)]`, and `m_sem_gt=max(0,d_geo-effective_clearance_gt)`. This allows a farther HUMAN point to dominate a nearer zero-margin wall point. Invalid/UNKNOWN semantic points remain in geometry with margin zero. The label is always nonnegative, bounded by the largest valid visible class margin, and never modifies `d_geo`, `g_geo`, observable collision, or exact recheck.

Reliability is zero for missing/stale RGB, invalid projection, or UNKNOWN labels; it is reduced near image borders, depth discontinuities, and calibration perturbations. At reliability zero, the future constraint reduces exactly to Stage 05.
