# Known Limitations

- No `gz`, Gazebo Classic, Ignition, ROS 2, colcon, or xacro executable is
  installed on this host. No world was loaded and no sensor was run.
- SDF 1.9 assets target Modern Gazebo / `gz sim`; runtime compatibility and
  bridge behavior require a Gazebo host.
- P0 geometry-only is the integration baseline. P1/P2 may use only the clearly
  labelled Gazebo Oracle semantic sidecar. Stage 10 RGB remains blocked and is
  not loaded.
- Oracle semantics are simulator ground truth, not real RGB perception.
- `human_path_side` remains a deliberate known-limit regression: P0 exact
  clearance `0.24652 m < 0.25 m`; P1/P2 previously reached
  `OSQP_MAX_ITER_REACHED` at 10000 iterations. Stage 11A does not resolve it.
- Only static or instantaneous semantic obstacles are represented. No future
  HUMAN/VEHICLE motion, social navigation, or formal safety guarantee exists.
- The camera, LiDAR, time, QoS, and command contracts are statically tested;
  actual simulator timestamps, noise, rendering, and bridge QoS are untested.
- World geometry remains offline-only and cannot alter planner input, status,
  warm start, fallback, or command.
