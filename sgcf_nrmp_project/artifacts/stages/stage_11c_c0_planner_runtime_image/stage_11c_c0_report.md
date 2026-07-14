# Stage 11C-C0 Frozen Planner Runtime Image Report

## Executive Summary

Stage 11C-C0 stopped before dependency download and image construction:

```text
BLOCKED_RUNTIME_TRAINING_DEPENDENCY_COUPLING
```

The requested Torch-free Planner runtime is incompatible with the current formal
Planner implementation. This is established directly by the Core source and its
package metadata, not inferred from a missing optional test dependency.

## Immutable Base Binding

The authorized base remains:

```text
sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862
```

It is the Stage 11C-A/B ROS Humble Bridge image with Python 3.10, `rclpy`, NumPy
1.21.5, and SciPy 1.8.0. It was not modified, retagged, committed, or used for an
in-container installation. The Gazebo runtime image was also unchanged.

## Formal Planner Import Closure

The public import path is:

```text
sgcf_nrmp.planner
→ GTNRMPPlanner
→ ExactObservableChecker
→ BatchedRectangleObservableOracle
→ torch
```

`geometry_checker.py` contains an unconditional `import torch`. Its production
observable-geometry implementation uses:

- `torch.as_tensor` for points and query states;
- `torch.linalg.vector_norm` for rectangle-point clearance;
- `torch.autograd.grad` for exact gradients.

This code is invoked by `GTNRMPPlanner`; it is not confined to Stage 10, training,
tests, or an optional learned model.

The QP path independently requires CVXPY and its OSQP backend:

```text
GTNRMPPlanner
→ PersistentPlannerQP
→ cvxpy
→ OSQP solver backend
```

Thus installing only `osqp` would not provide the complete formal runtime.

## Package-contract Conflict

The repository metadata declares:

```text
numpy >=1.26,<2
torch ==2.8.0
```

The Stage 11C-C0 contract requires:

```text
numpy ==1.21.5
scipy ==1.8.0
Torch prohibited
```

Both the unconditional Torch import and the NumPy constraint conflict with the
authorized target. Installing the project dependencies would either install
Torch or change the frozen numerical stack, each an immediate stop condition.

## Working-environment Evidence

The host environment was inspected only for version evidence:

| Component | Host evidence |
|---|---:|
| Python | 3.10.0 / CPython 3.10 / x86-64 |
| NumPy | 1.26.4 |
| SciPy | 1.13.0 |
| OSQP | 1.1.1 |
| CVXPY | 1.7.5 |
| Torch | 2.8.0+cu128 |

Its Python ABI matches, but its numerical stack differs from the frozen Bridge
image. Nothing was copied from the host environment.

## Why No Lockfile or Image Was Produced

A hash-locked wheel manifest may only be produced after the full runtime closure
is compatible with the stage contract. Here it is not. Downloading only solver
wheels would create a misleading partial lock, while adding Torch or upgrading
NumPy is forbidden. Therefore:

- wheel download count: 0;
- network package access: not used;
- derived Docker directory: not created;
- derived image: not built;
- OSQP smoke, Planner construction, replay, ROS coexistence, and Bridge regression:
  explicitly `NOT_EXECUTED`.

No result was fabricated for these downstream Gates.

## Frozen-component Audit

Core, Stage 05/09B Planner source, Stage 10, Gazebo worlds/models, original Bridge
Docker files, original images, and bridge mappings were unchanged. Gazebo run
count and `/cmd_vel` publish count were both zero.

## Required Design Decision Before Resumption

One of the following requires a new explicit authorization and architectural
decision:

1. permit Torch 2.8.0 in the Planner Shadow image and reconcile the frozen NumPy
   requirement with the project metadata; or
2. first refactor Exact Observable Geometry to a validated Torch-free runtime
   implementation, which would modify frozen Core and require full Stage 05/09B
   equivalence revalidation.

Stage 11C-C0 authorizes neither option.

## Final Decision

```text
BLOCKED_RUNTIME_TRAINING_DEPENDENCY_COUPLING
```

No Planner runtime image was built. Stage 11C-C cannot restart, and Stage 11C-D
is not authorized.
