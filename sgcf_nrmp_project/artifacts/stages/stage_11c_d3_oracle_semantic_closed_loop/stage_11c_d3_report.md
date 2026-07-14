# Stage 11C-D3 Report

## Result

Stage 11C-D3 stopped at `BLOCKED_ORACLE_SEMANTIC_CLOSED_LOOP_FEASIBILITY`.

The three `human_path_center` modes were run independently from fresh Gazebo/ROS processes:

- P0: 20 evaluations, 14 eligible, 68 nonzero forwarded messages, `0.171102 m` goal progress, P95 `53.68 ms`.
- P1: 20/20 `SEMANTICALLY_INFEASIBLE`, no eligible candidate, no nonzero actuation, P95 `175.42 ms`.
- P2: 20/20 `SEMANTICALLY_INFEASIBLE`, no eligible candidate, no nonzero actuation, P95 `181.46 ms`.

P1/P2 were correctly marked `ORACLE_GROUND_TRUTH`, `SIMULATION_ONLY`, and not Stage 10. Their semantic margin was exactly `0.35`, within the frozen `[0, 0.35]` contract. ROS/Core replay errors were zero. There was no collision, self-return, stale input, backlog, nonzero ineligible execution, or zero-stop failure. Residual containers and processes were zero.

The separate P0/P1/P2 launches received slightly different initial runtime scans, so cross-run `d_geo` values are not used as synchronized geometry-invariance evidence. Within each run, ROS wrapper and direct Core replay geometry were identical.

One initialization evaluation in each semantic run exceeded 200 ms and was isolated by the watchdog. Steady-state P95 remained below 200 ms and no late result was actuated.

The specified hard stop applies because P1 and P2 produced no legal nonzero closed-loop command. The remaining authorized worlds were not run.
