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
#   -d  : kinematics type (acker, diff, omni)
#   -m N: set max steps (default 1000)

# Training DUNE for a new robot geometry
cd example/dune_train
python train_dune.py

# Training LON model
cd example/LON
python train_lon.py
```

Available scenarios for `-e`: `corridor`, `convex_obs`, `dyna_non_obs`, `dyna_obs`, `non_obs`, `pf` (path following), `pf_obs`, `polygon_robot`, `reverse`.
Available kinematics for `-d`: `diff`, `acker`, `omni`.

**Note:** The `reverse` scenario with `-d diff` has special handling in `run_exp.py` — it flips gear direction and rotates orientation by π on the initial path. For Ackermann reverse, use `ipath.curve_style: 'reeds'` in the YAML config (Reeds-Shepp paths support forward+backward).

## Architecture

NeuPAN is an end-to-end MPC-based robot motion planner that directly maps raw obstacle points to control actions. It avoids explicit object detection, mapping, or trajectory engineering by solving a differentiable optimization at each timestep.

### Package Structure

```
neupan/                         # Python package (import as neupan, not NeuPAN)
├── neupan.py                   # Main neupan class (torch.nn.Module)
├── robot/robot.py              # Robot kinematics model (diff/acker/omni)
├── blocks/
│   ├── pan.py                  # PAN — Proximal Alternating-minimization Network
│   ├── dune.py                 # DUNE — Deep Unfolded Neural Encoder
│   ├── nrmp.py                 # NRMP — Neural Regularized Motion Planner (cvxpylayers)
│   ├── dune_train.py           # DUNE training pipeline with synthetic data
│   ├── initial_path.py         # Waypoint → reference trajectory (via gctl)
│   └── obs_point_net.py        # ObsPointNet: MLP mapping points → latent distance
├── configuration/__init__.py   # Global mutable state (device, dtype, conversions)
└── util/__init__.py            # Helpers: file_check(), WrapToPi, decimation, G/h generators
```

Import shorthand: The repo is named `NeuPAN`, but the package installs and imports as `neupan` (lowercase, singular). E.g., `from neupan import neupan` or `from neupan import configuration`.

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

Planner parameters are set via YAML files (see `example/corridor/diff/planner.yaml`). Sections: `robot` (kinematics, shape, limits), `ipath` (waypoints, curve style), `pan` (DUNE checkpoint, iteration settings), `adjust` (cost weights, safety distances), `train` (data generation and training parameters for DUNE). The `adjust` section can be updated at runtime via `update_adjust_parameters()`.

**`q_s` dimension alignment:** When using vector `q_s` (e.g., `[1.0, 1.0, 0.5]` for x, y, theta weights), the type (scalar vs 3-element vector) must be consistent between YAML initialization and runtime updates. You cannot switch from scalar to vector at runtime — re-initialize the planner to switch types.

### Key Public API

These methods on the `neupan` class are the primary integration points:

- **`scan_to_point(state, scan)`** — Convert raw lidar scan to world-frame obstacle points (2×N matrix). Handles sensor offset, rotation, downsampling. Returns `None` if no points.
- **`scan_to_point_velocity(state, scan)`** — Same as above but also returns per-point velocity for dynamic obstacle handling.
- **`set_initial_path(path)`** — Replace the reference path at runtime (e.g., from A* or other global planner). Path format: list of `[x, y, theta, gear]` 4×1 vectors (gear = -1 or 1).
- **`set_reference_speed(speed)`** — Change reference speed dynamically.
- **`update_initial_path_from_waypoints(waypoints)`** — Regenerate the reference path from a new list of waypoints.
- **`update_initial_path_from_goal(start, goal)`** — Generate a direct path from start to goal pose.
- **`update_adjust_parameters(**kwargs)`** — Tune cost weights at runtime: `q_s`, `p_u`, `eta`, `d_max`, `d_min`.
- **`reset()`** — Reset planner state (path index, stop/arrive flags) for a new run.
- **`train_dune()`** — Trigger DUNE training from the initialized config.
- **Properties:** `min_distance`, `dune_points`, `nrmp_points`, `initial_path`, `adjust_parameters`, `waypoints`, `opt_trajectory`, `ref_trajectory`.

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

## ROS Integration & Real Robot Deployment

- **[neupan_ros](https://github.com/hanruihua/neupan_ros)** — ROS1 wrapper for NeuPAN (git submodule at `neupan_ros/`).
- **`neupan_ros2/`** — ROS2 wrapper for NeuPAN (separate directory in repo root).
- **`example/mowen/`** — Custom real robot deployment example for the "Mowen" platform. Contains simulation environments, scaling configs, and real robot launch files (`.launch` + `planner.yaml` + `move.py`).
- **`docs/`** — Deployment reference:
  - `docs/BUGS.md` — Known issues and workarounds.
  - `docs/real_robot_deployment.md` — Instructions for deploying on physical robots.
  - `docs/MOWEN_SIM_TO_REAL.md` — Sim-to-real transfer notes for the Mowen platform.

To update the initial path from an external global planner (A*, etc.) at runtime, use `set_initial_path()` or publish to the `/initial_path` ROS topic with `refresh_initial_path=True` in the ROS wrapper.

## 实车代码参考

**小车 ROS 工作空间参考路径 (本地副本):**
```
/home/zq/resource/code/emb_ai/mobile_robot/clone/newznzc_ws/
```

**重要说明:**
- 该目录是 **小车 Ubuntu 系统内代码的副本 (copy)**，并非真实小车上的代码
- 真实小车 ROS 工作空间运行在小车自带的 Ubuntu 系统中
- 所有对小车代码的修改，必须先 **scp** 到小车后才能生效
  ```bash
  # 将文件复制到小车
  scp /本地路径/文件 小车用户名@小车IP:~/newznzc_ws/src/...
  
  # 或从小车复制回本地
  scp -r 小车用户名@小车IP:~/newznzc_ws/... /本地路径/
  ```
- **核心原则**: 任何场景测试都**不得修改小车内部已有代码**。如需改动，只能复制可复用的代码文件到新路径，再在此基础上新增功能代码。
- 小车已有的自定义功能包（不可修改）: `car_bringup`, `mbot_bringup`, `nav_demo`, `grab`, `wit`
- 小车已有的第三方包（通常不修改）: `leishen`, `ydlidar_ros_driver`, `mycobot_ros`, `OrbbecSDK_ROS`, `imu_tools`, `rf2o_laser_odometry`, `open_karto`, `slam_karto`, `robot_pose_ekf`
