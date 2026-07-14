# Known Limitations

- The formal Planner exact-geometry module has an unconditional runtime Torch
  dependency.
- The Core package NumPy constraint (`>=1.26,<2`) conflicts with the frozen Bridge
  NumPy 1.21.5 requirement.
- OSQP, CVXPY, QDLDL, Shapely, and Torch wheels were not resolved or downloaded
  because the earlier dependency-coupling Gate failed.
- No derived image, solver smoke, Planner construction, replay, ROS coexistence,
  or Bridge capability result exists for Stage 11C-C0.
