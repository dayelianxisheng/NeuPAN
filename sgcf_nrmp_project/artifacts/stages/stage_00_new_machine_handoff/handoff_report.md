# New Machine Handoff Report

Status: `READY_WITH_NONBLOCKING_DIFFERENCES`

Checked on 2026-07-12 in `/home/qcqc/resource/code/eai/NeuPAN`. The current branch is `main` at `fffaf87` (`feat: add SGCF-NRMP stages 01-05`). Official baseline object `579e7af` exists as a commit. No reset, restore, clean, staging, commit, push, download, dataset generation, or training was performed.

All required source, configuration, script, test, dataset, and stage 01–04 directories exist. `geometry_v1` contains the expected 13 NPZ shards plus manifests and configuration. Dataset validation reports 3,200 finite samples across 100 scenes with no split leakage. Stage 04 contains the 240,935-byte best checkpoint, metrics JSON, PNG figures, training history, and training configuration.

Package import and compile checks passed. Because `pytest` is absent, the same unittest-based stage 02–04 test files were run with `unittest`: 52/52 passed. The checkpoint loaded at epoch 20; single-batch forward and query autograd passed; all 480 test predictions were finite. CPU smoke timings completed for 1, 10, 32, and 128 queries.

Host GPU verification was completed manually after the sandbox check. PyTorch 2.8.0+cu128 detected CUDA Runtime 12.8 and an NVIDIA GeForce RTX 5070 Ti with compute capability `(12, 0)`. The build arch list contains `sm_120`; a synchronized 2048×2048 CUDA matrix multiplication completed on `cuda:0` with finite output. The earlier sandbox result, `torch.cuda.is_available() == False`, reflects unmapped GPU device nodes only and is not a host environment fault. No PyTorch, CUDA Toolkit, or NVIDIA driver reinstall is needed.

Nonblocking differences: the worktree contains copied-but-uncommitted reproducibility artifacts and prior guide/ignore-rule changes; `pytest` is not installed; and Codex cannot access the otherwise healthy host GPU because of sandbox device isolation. Protected directories are clean in the current worktree. Historical differences from baseline, including `neupan_ros`, are recorded and were not touched. Stage 05 content already exists in HEAD; this check did not run or modify it.
