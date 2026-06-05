# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

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

# Training DUNE for a new robot geometry
cd example/dune_train
python train_dune.py
```

Available scenarios for `-e`: `corridor`, `convex_obs`, `dyna_non_obs`, `dyna_obs`, `non_obs`, `pf`, `pf_obs`, `polygon_robot`, `reverse`.
Available kinematics for `-d`: `diff`, `acker`, `omni`.

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

### YAML Configuration

Planner parameters are set via YAML files (see `example/corridor/diff/planner.yaml`). Sections: `robot` (kinematics, shape, limits), `ipath` (waypoints, curve style), `pan` (DUNE checkpoint, iteration settings), `adjust` (cost weights, safety distances). The `adjust` section can be updated at runtime via `update_adjust_parameters()`.

### Key design decisions

- The NRMP optimization runs on CPU only (`cvxpy`/`cvxpylayers` don't support GPU). DUNE can run on GPU during training but typically runs on CPU during inference for data locality.
- DUNE is trained once per robot geometry, not per environment. The training data is purely synthetic (random points within `data_range`).
- The collision avoidance uses a slack-variable reformulation with L1 regularization (parameter `eta`) to handle infeasible configurations gracefully.
- The `adjust` parameters directly control the trade-off between path-following, speed-tracking, and obstacle avoidance. Tuning them is the primary way to adapt behavior to different scenarios.
