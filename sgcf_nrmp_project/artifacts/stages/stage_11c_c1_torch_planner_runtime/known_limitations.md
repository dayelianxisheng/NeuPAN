# Known limitations

- Torch is a CUDA-capable 2.8.0+cu128 build, so the image is large; this stage validates CPU execution only.
- Replay used deterministic frozen code fixtures and a live verified working-environment reference; Gazebo was intentionally not run.
- Stage 10 inference, checkpoints, training, and the seven-world Stage 11C-C shadow runtime remain outside this stage.
