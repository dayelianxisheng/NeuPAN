# SGCF-NRMP project

This is the only project root for all SGCF-NRMP code, documentation, tools and
generated results. The NeuPAN directories beside it are read-only upstream code.

- `core/`: standalone Python geometry, learning and planning core
- `ros2_ws/`: future ROS 2 workspace
- `gazebo/`: future simulation assets
- `deploy/`: future CPU deployment code and exports
- `docs/`: project documentation and stage records
- `tools/`: project-level audit and reporting utilities
- `artifacts/`: generated stage results, datasets, logs and figures

The Python package remains named `sgcf_nrmp` and lives in
`core/src/sgcf_nrmp/`.

Current completion state: stages 01 and 02 only. No stage 03 dataset generator,
neural model, planner, ROS, Gazebo or deployment implementation has started.
