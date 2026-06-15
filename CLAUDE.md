# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

**Requirements:** Python >= 3.9 (pyproject.toml). README says >= 3.10 for safety.
**Critical pins:** `numpy==1.26.4`, `scipy==1.13.0` (newer versions break cvxpylayers), `gctl==1.2` (exact pin), `torch>=2.1.0`. All pinned in `pyproject.toml`.

```bash
# Editable install (base package)
pip install -e .

# Install with IR-SIM for running examples
pip install -e ".[irsim]"

# Run example scenarios (from example/ directory)
cd example
python run_exp.py -e corridor -d diff       # corridor, differential drive
python run_exp.py -e non_obs -d acker       # nonconvex obstacles, ackermann
python run_exp.py -e dyna_obs -d omni       # dynamic obstacles, omnidirectional

# Additional flags for run_exp.py:
#   -v  : use point velocity from lidar scan (dynamic obstacle avoidance)
#   -a  : save animation to file
#   -n  : enable display (default: no display)
#   -m N: set max steps (default 1000)

# Training DUNE for a new robot geometry
cd example/dune_train
python train_dune.py
```

Available scenarios for `-e`: `corridor`, `convex_obs`, `dyna_non_obs`, `dyna_obs`, `non_obs`, `pf`, `pf_obs`, `polygon_robot`, `reverse`.
Available kinematics for `-d`: `diff`, `acker`, `omni`.

**Note:** The `reverse` scenario with `-d diff` has special handling in `run_exp.py` — it flips gear direction and rotates orientation by π on the initial path. For Ackermann reverse, use `ipath.curve_style: 'reeds'` in the YAML config (Reeds-Shepp paths support forward+backward).

**Import naming:** The repository is `NeuPAN`, but the Python package installs and imports as `neupan` (singular). E.g., `from neupan import neupan`.

## Architecture

NeuPAN is an end-to-end MPC-based robot motion planner that directly maps raw obstacle points to control actions. It avoids explicit object detection, mapping, or trajectory engineering by solving a differentiable optimization at each timestep.

### Core pipeline (top to bottom)

```
YAML config → neupan.init_from_yaml()
                                   │
                                   ├── robot (kinematics + constraints)
                                   ├── InitialPath (waypoint → reference trajectory)
                                   └── PAN (iterative optimization)
                                          ├── DUNE (point encoder → latent distance)
                                          └── NRMP (differentiable optimization via cvxpylayers)
```

**`neupan/neupan.py`** — Main `neupan` class (`torch.nn.Module`). Entry point: `init_from_yaml()` reads a YAML config and constructs the full pipeline. The `forward(state, points)` method runs one MPC step: update reference path → PAN solve → return control action.

**`neupan/blocks/pan.py`** — PAN (Proximal Alternating-minimization Network). The core solver that alternates between DUNE (encode point→distance) and NRMP (constraint optimization) iterations. Each iteration: DUNE maps obstacle points to latent distance space (mu, lambda, fa, fb), then NRMP solves the differentiable optimization problem with collision avoidance constraints derived from those distances.

**`neupan/blocks/dune.py`** — DUNE (Deep Unfolded Neural Encoder). A learned module that maps raw 2D obstacle points to a latent signed-distance representation. Uses `ObsPointNet` for point feature extraction. The pretrained model checkpoint is loaded via `dune_checkpoint` in the YAML config.

**`neupan/blocks/nrmp.py`** — NRMP (Neural Regularized Motion Planner). Formulates and solves the differentiable optimization problem using `cvxpylayers` (which wraps `cvxpy` problems as differentiable `torch` layers). Solves for optimal control sequence subject to kinematics, collision avoidance, and state/speed costs. Uses the ECOS solver.

**`neupan/blocks/initial_path.py`** — Generates a naive reference trajectory from waypoints using `gctl` (curve generation). Supports straight lines, Dubins paths (forward ackermann), and Reeds-Shepp paths (forward+backward).

**`neupan/robot/robot.py`** — Robot kinematics model. Encodes the motion model (linearized discrete-time), generates constraint matrices (A, B, C), and provides the robot's convex hull as halfplane inequalities (G, h). Supports diff, acker, and omni kinematics.

**`neupan/configuration/`** — Global mutable state: `device` (cpu/cuda), `time_print` flag, `tensor_dtype`, and conversion helpers (`np_to_tensor`, `tensor_to_np`). Imported and mutated by other modules (e.g., `neupan.py` sets `configuration.device`).

**`neupan/blocks/dune_train.py`** — Training pipeline for DUNE. Generates synthetic training data (random points within a range + robot geometry). Trains the DUNE autoencoder to predict latent distance from obstacle points. Only needs retraining when robot shape/size changes.

### Data flow per timestep

1. `env.get_robot_state()` + `env.get_lidar_scan()` → raw state and scan
2. `neupan.scan_to_point(state, scan)` → transformed obstacle points in world frame
3. `neupan.forward(state, points)`:
   - `ipath.update(state)` → reference trajectory over receding horizon
   - `pan.forward(ref_traj, points)`:
     - DUNE: points → latent distances (mu, lambda) + dual features (fa, fb)
     - NRMP: solve differentiable optimization with those distances → control sequence
   - Return first control action + info dict
4. `env.step(action)` → simulate robot motion

**Important `forward()` behavior:**
- Returns `(action, info)` where `action` is a `(2, 1)` numpy array.
- When the robot arrives at the goal, returns `np.zeros((2, 1))` with `info["arrive"] == True`.
- When collision is detected (min distance < `collision_threshold`), returns `np.zeros((2, 1))` with `info["stop"] == True`.
- **Always check `info["arrive"]` and `info["stop"]` before using the action.**

**Omni kinematics special case:** For `omni`, the NRMP internally optimizes `(v_linear, theta)` but `forward()` converts to `(vx, vy)` output using `cos`/`sin`. The info dict stores both forms (`omni_linear_speed`, `omni_orientation`). The cost function for omni only penalizes `x, y` position errors (not theta).

### YAML Configuration

Planner parameters are set via YAML files (see `example/corridor/diff/planner.yaml`). Sections: `robot` (kinematics, shape, limits), `ipath` (waypoints, curve style), `pan` (DUNE checkpoint, iteration settings), `adjust` (cost weights, safety distances). The `adjust` section can be updated at runtime via `update_adjust_parameters()`.

### Key design decisions

- The NRMP optimization runs on CPU only (`cvxpy`/`cvxpylayers` don't support GPU). DUNE can run on GPU during training but typically runs on CPU during inference for data locality.
- DUNE is trained once per robot geometry, not per environment. The training data is purely synthetic (random points within `data_range`).
- The collision avoidance uses a slack-variable reformulation with L1 regularization (parameter `eta`) to handle infeasible configurations gracefully.
- The `adjust` parameters directly control the trade-off between path-following, speed-tracking, and obstacle avoidance. Tuning them is the primary way to adapt behavior to different scenarios.
- When `nrmp_max_num` or `dune_max_num` is set to `0`, collision avoidance is disabled entirely (pure path following). Useful for debugging path-tracking behavior separately from obstacle handling.

### DUNE checkpoint file resolution

The `file_check()` utility in `neupan/util/__init__.py` searches for checkpoint files in this order:
1. Exact path as given
2. `<script_directory>/<file_name>` (i.e., `sys.path[0]`)
3. `<current_working_directory>/<file_name>` (i.e., `os.getcwd()`)
4. `<neupan_package_root>/<file_name>`

This means relative paths like `'example/model/diff_robot_default/model_5000.pth'` resolve relative to wherever `run_exp.py` is invoked. Run from the `example/` directory for correct resolution.

## Docker

项目自带 Docker 镜像，已内置清华加速源（apt/pip/rosdep），国内构建无需代理。

**构建:** `./docker/build.sh ros2` (或 `ros1`)，加 `--proxy` 使用代理（git clone 场景）。

**运行:**
```bash
xhost +local:docker
# ROS2
docker run -it --gpus all --net=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix neupan:ros2
# ROS1
docker run -it --gpus all --net=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix neupan:noetic
```

**开发（挂载代码）:**
```bash
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $(pwd):/root/neupan_ros2_ws/src/NeuPAN neupan:ros2
# 容器内重新安装
pip install -e /root/neupan_ros2_ws/src/NeuPAN
```

**Dockerfile 位置:** `docker/ros1/Dockerfile`, `docker/ros2/Dockerfile`
**关键依赖:** 已内置 `torch==2.8.0+cu128`、`numpy==1.26.4`、`scipy==1.13.0`，与 `pyproject.toml` 版本锁定一致。
