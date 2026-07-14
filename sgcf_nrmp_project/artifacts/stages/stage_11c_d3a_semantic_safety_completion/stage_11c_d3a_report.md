# Stage 11C-D3A Report

## Outcome

Stage 11C-D3A completed with known Planner limitations. No Core, Planner configuration, Gazebo asset, safety threshold, Stage 10 component, or checkpoint was modified.

## Safety and R1 contracts

- `human_path_center`: reclassified as expected semantic safe rejection at margin `0.35`.
- `semantic_infeasible`: P1/P2 remained `SEMANTICALLY_INFEASIBLE`, zero nonzero actuation, zero stale/backlog, exact ROS/Core replay.
- `rgb_dropout_contract`: `semantic_valid=false`, `RGB_DROPOUT`, margin zero; P2/P0 candidate and geometry differences zero.
- `outdated_rgb_contract`: `semantic_valid=false`, `OUTDATED_IMAGE` using the simulation-time contract, margin zero; P2/P0 candidate and geometry differences zero.

## Feasible-scene probe

- `human_path_side`: P2 20/20 `SEMANTICALLY_INFEASIBLE`; no actuation during Shadow probe.
- `vehicle_path`: P2 20/20 `SOLVED_SAFE`, semantic margin `0.2`, P95 `28.62 ms`; selected for closed-loop trial.
- `vehicle_path` P2 closed loop: 80 safe nonzero actuation messages, no collision, self-return, deadline miss, stale input, backlog, or zero-stop failure. The candidate remained nearly pure angular velocity, so goal-distance reduction was approximately zero. This is recorded as `KNOWN_PLANNER_SEMANTIC_FEASIBILITY_LIMITATION`.

At identical nominal queries, P0/P2 observable-point counts, `d_geo`, and `g_geo` match exactly. Later trajectory-indexed geometry arrays differ because P0 and P2 optimize different trajectories; this is not a mutation of Exact Geometry.

All stage containers and processes were cleaned. Stage 11C final evaluation was not started.
