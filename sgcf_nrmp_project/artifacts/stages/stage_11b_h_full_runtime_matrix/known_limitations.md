# Known limitations

- Stage 11B-H is blocked because the runtime GPU LiDAR observes the robot's own body / wheel geometry at approximately 0.20 m. These returns lie inside the 0.8 × 0.5 m planning footprint and force zero observable clearance in safe scenes.
- No asset correction or self-filter was authorized, so this stage did not attempt a fix.
- Startup-latency repeat runs were not executed after the immediate-stop condition.
- Gazebo sensor frame headers use scoped sensor names and require an explicit adapter mapping to the frozen `lidar_link` and `camera_optical_frame` contracts.
- The nonfatal X11 and one-device DRM warnings match Stage 11B-F; another EGL device successfully initializes OpenGL 4.5.
- `human_path_side` retains its Stage 09B Planner limitation; no Planner was run here.
