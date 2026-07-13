# Existing Gazebo/ROS Asset Audit

Before Stage 11A, `sgcf_nrmp_project/gazebo/` contained only `.gitkeep` files in
`config/`, `launch/`, `models/`, and `worlds/`; `ros2_ws/src/` also contained
only `.gitkeep`. No SDF, URDF, Xacro, world, launch file, simulator plugin, or
ROS node existed. Protected upstream directories were not searched for reusable
assets because they are outside the writable Stage 11A project boundary.

The requested `stage_05_exact_geometry_nrmp/` artifact path is absent. The
existing authoritative Stage 05 source is `stage_05_gt_nrmp_solver/`, whose
report and frozen `0.8 × 0.5 m` footprint were used.

Stage 11A adds primitive-only SDF 1.9 assets with no mesh, texture, network URI,
or runtime plugin dependency. Runtime loading was not attempted because no
Gazebo executable is installed.
