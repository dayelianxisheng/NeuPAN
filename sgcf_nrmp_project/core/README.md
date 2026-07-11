# SGCF-NRMP

Independent research implementation based on the design in
`sgcf_nrmp_project/docs/codex/SGCF_NRMP_Codex_Execution_Plan_V2.md`.

The official read-only NeuPAN algorithm baseline is `579e7af`. No code from the
current modified `neupan/` tree is imported by this package.

Stage 02 adds deterministic static 2D procedural geometry, footprint-aware
clearance labels, finite-difference reference gradients and nearest-hit LiDAR
ray casting. It contains no neural network, planner, ROS, RGB or Gazebo code.

Coordinate convention:

- robot-local x points forward;
- robot-local y points left;
- positive yaw is counter-clockwise;
- positions use metres and angles use radians;
- transforms are named `T_target_source`.

`observable_clearance` is the footprint distance to valid points returned by the
current simulated LiDAR scan. Occluded, out-of-FOV, out-of-range and dropped
surfaces are absent. If no valid hit exists, it returns the configured truncation
distance with `observable_available=false`. `observable_collision` only means a
visible scan point intersects the footprint and can therefore miss a real
collision.

`world_clearance` and `world_collision` use all static obstacle polygons. They
are evaluation/oracle labels and must not become default supervision for a model
whose only input is one LiDAR frame.

Stage 03 smoke dataset commands:

```bash
PYTHONPATH=sgcf_nrmp_project/core/src python sgcf_nrmp_project/core/scripts/generate_geometry_dataset.py
PYTHONPATH=sgcf_nrmp_project/core/src python sgcf_nrmp_project/core/scripts/validate_geometry_dataset.py sgcf_nrmp_project/artifacts/datasets/geometry_v1
```

The dataset uses scene-level splits, checksummed atomic NPZ shards and a lazy
PyTorch loader. See `sgcf_nrmp_project/docs/dataset/geometry_v1.md`.

Import without installation:

```bash
PYTHONPATH=sgcf_nrmp_project/core/src python -c "import sgcf_nrmp; print(sgcf_nrmp.__version__)"
```
