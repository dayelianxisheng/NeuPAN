# Stage 11C-C1 Planner Runtime Image

For cross-machine setup and verification, see:

- [Stage 11C-C1 跨机器交接说明](../../sgcf_nrmp_project/docs/stage_11c_c1_cross_machine_handoff.md)

This image derives from the immutable Stage 11C-A/B Bridge image. It keeps the
system ROS Python environment unchanged and installs the formal Planner numerical
stack into `/opt/sgcf_planner_venv`.

The Torch build is CUDA-capable (`2.8.0+cu128`), while the deployment contract is
strictly CPU execution. Formal runs must not use `--gpus` or NVIDIA device mounts
and must set `CUDA_VISIBLE_DEVICES=""` and `NVIDIA_VISIBLE_DEVICES=void`.

Build:

```bash
docker build --progress=plain \
  -t sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1 \
  docker/ros2_humble_gzharmonic_torch_planner
```

No Stage 10 model, TorchVision, Torchaudio, checkpoint, or training dependency is
installed by this image definition.
