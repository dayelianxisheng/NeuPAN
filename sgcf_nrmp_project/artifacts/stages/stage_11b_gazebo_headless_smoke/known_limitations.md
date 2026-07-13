# Known Limitations

- Stage 11A sensor elements have no active Harmonic Sensors system at runtime.
- The robot asset has no DiffDrive system or wheel joints; odometry and command topics are absent.
- Only `empty_world` was started before the mandatory stop.
- Runtime LiDAR, camera, frames, clearance, rates, motion, and sidecar contracts remain unvalidated.
- `human_path_side` retains the frozen Stage 09B limitation and was not run.
