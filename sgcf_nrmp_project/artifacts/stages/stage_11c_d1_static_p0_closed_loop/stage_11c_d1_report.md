# Stage 11C-D1 Static P0 Closed-loop Report

## Decision

`BLOCKED_NO_LEGAL_NONZERO_CLOSED_LOOP_COMMAND`

The Safe Actuation Gate was the sole `/cmd_vel` publisher and correctly enforced deadline, freshness, frame, solver, collision, finite-value, and velocity-bound checks without modifying candidates.

- `empty_world`: Core returned 20/20 `SOLVED_SAFE` candidates near 0.240 m/s. The stage hard limit is 0.15 m/s, so every otherwise relevant candidate was rejected with `linear_bound`; clamping is prohibited.
- `single_static_obstacle`: Core returned 20/20 `REJECTED_BY_GEOMETRY_CHECK`, `command_eligible=false`, candidate zero. The Gate correctly retained zero output.

No nonzero command reached ROS `/cmd_vel` or Gazebo, no robot motion or collision occurred, self-return remained zero, ROS/Core replay differences were zero, and final zero-stop passed. Because both worlds produced zero legal nonzero actuation commands, the explicit closed-loop capability hard blocker applies. Core, Planner configuration, Gazebo assets, and images were not modified.

Stage 11C-D2 was not started.
