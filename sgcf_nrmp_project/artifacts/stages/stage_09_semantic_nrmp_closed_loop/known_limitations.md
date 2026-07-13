# Stage 09 Known Limitations

Status:

```text
STAGE_09_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
SEMANTIC_NRMP_CORE_VALIDATED
READY_FOR_STAGE_10_PERCEPTION_ONLY
```

1. Semantics use an Oracle semantic map and Hard PointPainting, not a real RGB
   perception network.
2. The R1 Gate handles only explicit RGB dropout, image staleness, invalid
   projection, and `UNKNOWN` semantics.
3. A single online frame cannot identify silent extrinsic-calibration drift;
   the operating assumption is `CALIBRATION_ASSUMED_VALID`.
4. Stage 09 considers static or instantaneous semantics and does not predict
   future HUMAN or VEHICLE motion.
5. Random smoke goal-reaching rates are P0 70%, P1 85%, and P2 85% (48/60
   overall). Collision-free rejection or stopping is not navigation success.
6. Random smoke contains ten geometry-recheck rejections and two OSQP/solver
   user-limit terminations.
7. Deterministic evaluation contains five geometry-recheck rejections and two
   solver user-limit terminations across 60 mode-scenario results.
8. `human_path_side` does not reach the goal: P0 is rejected by geometry recheck;
   P1/P2 terminate at solver user limit. This indicates a lifecycle,
   linearization, or solver-stability limitation for some lateral-HUMAN/reference
   configurations, not proof that semantic margin itself is invalid.
9. Planned statuses `SEMANTICALLY_INFEASIBLE`,
   `SEMANTIC_DEGRADED_TO_GEOMETRY`, and
   `EXPLICIT_FAILURE_GEOMETRY_FALLBACK` are not fully implemented.
10. World geometry is offline-evaluation-only and unavailable to online control.
11. Semantic margin is an added behavioral margin and does not replace exact
    observable-geometry safety.
12. First-cycle canonicalization/setup latency is substantially higher than
    steady state; deployment requires persistence or prewarming.
13. The result is not a formal safety guarantee and does not validate real RGB,
    silent-calibration detection, dynamic-agent prediction, ROS, or Gazebo.

Before ROS/Gazebo, Stage 09B must complete planner status classification,
geometry-rejection and solver-user-limit diagnosis, and the `human_path_side`
regression. This file records that debt only; Stage 09B is not implemented here.
