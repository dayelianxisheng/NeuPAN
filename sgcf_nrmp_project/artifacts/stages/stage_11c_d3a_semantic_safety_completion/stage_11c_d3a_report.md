# Stage 11C-D3A Report

## Outcome

Stage 11C-D3A completed on the synchronized local runtime with known Planner limitations. No Core, Planner configuration, Gazebo asset, safety threshold, Stage 10 component, or perception checkpoint was modified or loaded. Planner execution was CPU-only and Oracle ground truth was the only semantic source.

## Local runtime binding and smoke

- Gazebo image: `sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3`
- Bridge image: `sha256:69ec4a1e2134de8e05532386c4220e8ea4a91107b8bf1947dab4f07948af275f`
- Planner image: `sha256:450a603029c87e18550c64d19672ccb72b66395f74c254d0b098fbf8f7deb7cc`

The zero-motion smoke received 1781 clock, 20 scan, 22 image, 22 CameraInfo, and 106 odometry messages. All six bridge mappings were present, robot self-return was zero, ROS/Gazebo nonzero command count was zero, and translation/yaw drift remained below `2.3e-20`. All smoke processes and containers were cleaned.

## Safety and R1 contracts

- `human_path_center` remains `EXPECTED_SEMANTIC_SAFE_REJECTION`; it was not treated as a new hard blocker.
- `semantic_infeasible`: P1/P2 remained `SEMANTICALLY_INFEASIBLE`. Late results were diagnostic-only; nonzero actuation, stale execution, backlog, and ROS/Core replay error were all zero. Safe Actuation Gate supplied zero fallback.
- `rgb_dropout_contract`: `semantic_valid=false`, `fallback_reason=RGB_DROPOUT`, semantic margin zero. Paired P2/P0 candidate, `d_geo`, and `g_geo` maximum differences were zero.
- `outdated_rgb_contract`: simulation time produced `semantic_valid=false`, `fallback_reason=OUTDATED_IMAGE`, and semantic margin zero. Paired P2/P0 candidate, `d_geo`, and `g_geo` maximum differences were zero.

## Feasible-scene probe and closed loop

- `human_path_side`: P2 was 20/20 `SEMANTICALLY_INFEASIBLE`; no command was actuated in Shadow Mode.
- `vehicle_path`: P2 was 20/20 eligible with positive Oracle VEHICLE margin `0.2`, exact same-query geometry, and Shadow P95 `35.91 ms`; it was the first feasible probe.
- `vehicle_path` P0: 184 safe nonzero actuation messages; goal-distance reduction `0.03239 m`.
- `vehicle_path` P2: 196 safe nonzero actuation messages; P95 `41.37 ms`; zero collision, deadline miss, stale input, backlog, self-return, or zero-stop failure. Candidate-to-ROS maximum absolute error was zero.

P2 goal-distance reduction was `-0.31891 m`, below the required `0.05 m`. The safe positive-margin commands were dominated by turning and did not demonstrate semantic navigation progress. This is recorded as `KNOWN_PLANNER_SEMANTIC_FEASIBILITY_LIMITATION`, not as a runtime-safety failure.

At identical nominal queries, P0/P2 observable-point counts, `d_geo`, and `g_geo` matched exactly. R1 paired replays also matched exactly. Semantic data therefore did not alter Exact Geometry.

## Validation and boundaries

The D3A contract suite passed 19/19 tests, the direct Stage 11C-C2 dependency suite passed 6/6, Stage 09 lifecycle/recovery tests passed 22/22, and semantic fallback tests passed 16/16. Compileall passed using an isolated temporary pycache. No Stage 11C final evaluation was started, and all stage processes and containers were cleaned.
