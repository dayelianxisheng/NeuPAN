# Known limitations

- Only the authorized `empty_world` runtime re-gate was executed; the remaining 11-world Stage 11B matrix is still pending.
- Raw empty-world LiDAR no-return samples are encoded as positive infinity by Gazebo. They contain no NaNs and must be filtered by the frozen adapter before observable-point construction.
- OGRE2 logs expected headless probing warnings for unavailable X11 and one DRM device; it successfully created a GL 4.5 EGL context on another device.
- The official development package pulls a large development dependency closure; no Gazebo, gz-rendering runtime, or OGRE runtime was upgraded or replaced.
- This result does not validate Planner, Stage 10, ROS bridge, runtime clearance, rates, startup latency, or the remaining worlds.
