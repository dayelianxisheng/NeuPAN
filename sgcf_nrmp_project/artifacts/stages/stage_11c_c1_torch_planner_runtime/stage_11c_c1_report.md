# Stage 11C-C1 Torch Planner Runtime Image Report

## Outcome

```text
STAGE_11C_C1_COMPLETE
CUDA_CAPABLE_TORCH_RUNTIME_IMAGE_FROZEN
CPU_ONLY_PLANNER_EXECUTION_VALIDATED
DUAL_NUMERICAL_STACK_ISOLATION_VALIDATED
TORCH_BACKED_EXACT_GEOMETRY_VALIDATED
CORE_PLANNER_CPU_REPLAY_EQUIVALENCE_VALIDATED
ROS2_PLANNER_RUNTIME_COEXISTENCE_VALIDATED
READY_TO_RESTART_STAGE_11C_C_SHADOW_MODE
```

The derived immutable image is `sha256:03f77926ea1b97cc460ca2d5893abb1b26d3b68984d53f9e98e707994841cff5`. It is built from the verified local Bridge image `sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862` and preserves that image's RootFS layers as an exact prefix.

The system ROS environment remains NumPy 1.21.5 / SciPy 1.8.0. The isolated Planner venv contains NumPy 1.26.4, SciPy 1.13.0, OSQP 1.1.1, and CUDA-capable Torch 2.8.0+cu128. Formal execution used no GPU and observed no CUDA device, tensor, context, allocation, or kernel.

Six deterministic Exact Geometry fixtures matched the live verified working environment with zero d_geo and g_geo error. P0, semantic, R1, and collision replays matched status, eligibility, fallback reason, geometry, semantic margin, and candidate control with zero maximum error. OSQP solved 20/20 deterministic problems. Planner steady-state CPU P95 was 17.434 ms against the 200 ms limit.

The Planner venv imported rclpy and created/destroyed a ROS Node with the required message subscriptions without publishing `/cmd_vel`. All six ros_gz_bridge registrations remained present. The existing Planner unittest suite passed 47/47 tests. Core, Gazebo assets, the original Bridge Docker directory, and the original Bridge image remained unchanged. Gazebo and Stage 11C-C were not started.
