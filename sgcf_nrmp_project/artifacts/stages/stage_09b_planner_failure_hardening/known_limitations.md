# Stage 09B Known Limitations

1. `human_path_side` remains unsuccessful: P0 is exactly rejected at `0.24652 m`
   versus `0.25 m`; P1/P2 hit `OSQP_MAX_ITER_REACHED`.
2. The fixed random smoke success rates remain P0 70% and P1/P2 85%; safe
   rejection is not goal-reaching success.
3. Random smoke retains ten geometry-recheck terminations and two solver
   user-limit terminations, now explicitly classified.
4. The frozen Stage 09 configuration does not silently activate
   semantic-to-geometry control fallback after valid-semantic infeasibility.
   The explicit policy path is implemented and tested but requires deliberate
   configuration authorization.
5. The deterministic fixture named `semantic_infeasible` is not semantically
   infeasible under the strict definition because P0 also fails exact recheck.
6. Some exact-recheck events include small solver-level trust-bound violations;
   safety is preserved by rejecting rather than executing them.
7. First-cycle setup-inclusive P95 is `279.26 ms`; deployment requires prewarm.
   Steady-state online-equivalent P95 is `37.72 ms`.
8. `trajectory_collision` includes unexecuted rejected candidates and the three
   intentional initial-collision trajectories; planner-induced executed
   observable collision remains zero.
9. Stage 10 RGB perception remains independently blocked/frozen and is not used.
10. No dynamic-agent prediction, formal safety proof, ROS, Gazebo, or real-robot
    validation is claimed.
