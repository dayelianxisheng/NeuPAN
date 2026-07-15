# Stage 15 Oracle Semantic Closed-loop Report

## Outcome

`STAGE_15_COMPLETE_WITH_NEGATIVE_OR_INCONCLUSIVE_RESULT`

Seventy fresh Gazebo runs formed 35 deterministic P0/P2 pairs: 15 fixed
pairs (five scenes, three seeds) and 20 randomized mixed-scene pairs. P0 and
P2 navigation success were both 0.0%. The
required HUMAN or VEHICLE benefit was not reached: median HUMAN clearance
changed by 0.002549 m and median VEHICLE
clearance by 0.000079 m; both near-miss
rates were already zero. The result is therefore negative/inconclusive, not a
semantic-navigation validation.

## Experiment contract

- Fixed scenes: `human_path_center`, `human_path_side`, `vehicle_path`,
  `semantic_infeasible`, and the independent `stage15_oracle_mixed` overlay.
- Fixed seeds: 101, 202, 303. Random mixed-scene seeds: 1000 through 1019.
- Each seed was run once in P0 and once in P2 with the same scene parameters.
- P2 source was `ORACLE_GROUND_TRUTH`, `SIMULATION_ONLY`, and
  `NOT_STAGE10_PREDICTION`; Stage 10 was neither started nor loaded.
- Depot was not scored because its local vendor license is unknown and its
  mesh is visual-only.

## Safety and geometry

- Planner-induced collisions: 0 in P0 and 0 in P2.
- Stale, late, or ineligible candidates executed: 0.
- Candidate-to-ROS-to-Gazebo maximum numerical error: 0.
- ROS/Core replay maximum error: 0.
- Same-query Exact Geometry `d_geo` and `g_geo` differences: 0.
- Robot self-return and sustained backlog: 0; all runs passed zero-stop.
- Full-horizon nonlinear recheck and the Safe Actuation Gate remained active.
- The historical Stage 11C initial-collision gate remains the authoritative
  `EMERGENCY_STOP` evidence; Stage 15 did not rerun that additional scene.

Semantic labels were supplied only to the margin wrapper. The exact checker
and observable points remained shared. Cross-trajectory arrays from separately
evolving P0/P2 closed loops were deliberately not compared as if they were the
same query; invariance is established by same-query checker delegation and
direct-Core replay.

## Performance

The maximum P95 among command-eligible paths was
92.411 ms, below the 200 ms gate. The
maximum P95 over all paths was 517.427 ms. Deadline
misses on ineligible/diagnostic paths totaled 438;
the watchdog kept those results out of actuation and no continuous backlog was
observed.

## Interpretation

P2 did not increase collision rate or reduce aggregate success relative to P0,
and static median clearance did not degrade. However, no run reached the goal,
and neither required semantic safety-effect threshold was met. Consequently
Stage 16 must not proceed without analysis of planner feasibility and scenario
discrimination. This stage validates Oracle runtime safety and Exact Geometry
invariance only.
