# ROS 2 Humble / Gazebo Harmonic bridge

Stage 11C-A bridge-only image. It is pinned to the immutable local image behind
`ros2_dev` and installs the official `ros-humble-ros-gzharmonic` apt package.
BuildKit cannot use a bare local image ID in `FROM`, so the build gate creates
the private alias `sgcf-ros2-humble-base:4cbeac7831833` only after asserting
that it resolves to the full ID in `package_lock_manifest.json`.
It must not host the Gazebo server or a planner.

Build with `./container.sh build`; the runtime is created by the Stage 11C-A
gate using the resulting immutable image ID, host networking,
`ROS_DOMAIN_ID=42`, and `GZ_PARTITION=sgcf_stage11ca`.
