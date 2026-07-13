# Stage 05 — Exact-Oracle trust-region NRMP-like/SCP planner

## Result

**PASS for the Stage-05 exact-Oracle optimizer scope, including the repaired complex-geometry online latency gate.**

The Exact Observable Oracle performance repair strictly separates online planning from complete-world evaluation. The online planner now receives only the current LiDAR observation and uses a batched analytic rectangle-to-point Oracle with Torch autograd. Complete-world geometry is owned only by `OfflineWorldEvaluator`, called after control selection by the simulator.

> 在线规划器只依赖当前 LiDAR 可观测障碍信息；完整世界几何仅由离线评估器使用，不参与控制求解、状态判断、回退决策或 warm start。

The two mandatory real-time gates pass at `dt_s=0.2`. The planner uses exact
`observable_clearance` and finite-difference observable gradients for its normal
constraints. `world_clearance` and `world_collision` are used only by simulation
evaluation/recheck and never to generate normal controls. No Stage-04 learned
field, RGB, ROS, Gazebo, or upstream NeuPAN source is used.

## Persistent parameterized QP

- One `cvxpy.Problem` is built in `GTNRMPPlanner.__init__`; its object identity is
  unchanged across SCP iterations and control cycles.
- Initial state, reference, nominal states/controls, previous control, dynamics
  `A/B/c`, clearance gradients/biases/valid masks, trust radii, safe distance,
  control bounds, and acceleration bounds are `cvxpy.Parameter` values.
- State/control/slack dimensions, constraints, and sparsity remain fixed.
  Invalid clearance slots use zero gradient, a safe bias, a validity mask, and a
  fixed big-M relaxation; constraints are not dynamically added or removed.
- Clearance bias `d - g*q_nominal` is computed in NumPy. This removes the
  parameter-by-parameter expression that would violate DPP.
- `problem.is_dcp()`, `problem.is_qp()`, and `problem.is_dpp()` all return true.
- OSQP uses `warm_start=True` and the previous primal state/control/slack values.
  CVXPY does not expose a stable public dual-value initialization path, so dual
  warm-start state is left to the retained OSQP/CVXPY solver cache.
- The first solve includes one-time CVXPY-to-OSQP setup; subsequent calls update
  the retained parameterized problem.

## Mandatory gate results

| Metric | Empty straight | Single-circle detour |
|---|---:|---:|
| Success | yes | yes |
| End-to-end mean | 24.17 ms | 70.13 ms |
| End-to-end P95 | 25.88 ms | 89.96 ms |
| End-to-end maximum | 124.34 ms | 147.92 ms |
| Cycles over 200 ms | 0/25 | 0/29 |
| Per-QP solve mean | 3.89 ms | 3.53 ms |
| Per-QP solve P95 | 2.90 ms | 2.92 ms |
| Per-QP solve maximum | 103.27 ms | 81.98 ms |
| Mean SCP iterations | 2.68 | 2.72 |
| Minimum observable clearance | 8.000 m | 0.33343 m |
| Minimum world clearance | 8.000 m | 0.33338 m |
| Fallback / emergency stop | 0 / 0 | 0 / 0 |

The maximum QP values are first-solve setup outliers. They occur once per fresh
planner instance (1/67 and 1/79 SCP solves respectively), remain below the
200-ms control period at end-to-end level, and OSQP's internal solve mean is only
about 0.30–0.33 ms. Full samples and component timing are in
`persistent_qp_gate_results.json` and `solver_benchmark.json`.

## Timing decomposition

For the empty/single-circle gates, mean per-SCP component costs were:

| Component | Empty | Circle |
|---|---:|---:|
| Observable query + finite-difference linearization | 3.20 ms | 16.73 ms |
| Parameter update | 1.16 ms | 1.49 ms |
| CVXPY/OSQP wall solve | 3.89 ms | 3.53 ms |
| OSQP internal solve | 0.30 ms | 0.33 ms |
| Observable/world recheck | 0.34 ms | 1.67 ms |

The simulator's end-to-end timing encloses scan generation, checker/reference
construction, all SCP work, geometry recheck, and first-control selection.

## Optimizer and safety behavior

- Differential-drive rollout and analytical linearization are implemented and
  checked against numerical finite differences.
- Objective terms: tracking, terminal, control, smoothness, proximal, and
  quadratic slack penalties. All weights are in `planner_config.yaml`.
- Bounds cover velocity, angular velocity, and both acceleration channels.
- Explicit state/control trust regions are applied at every horizon step.
- Every candidate is rolled out through nonlinear dynamics and rechecked using
  exact observable and complete-world geometry.
- Observable violations shrink the trust region and retry; exhausted retries
  stop rather than emit the rejected trajectory.
- Timeout, infeasible, numerical, emergency, and geometry-rejection statuses map
  to explicit fallbacks. The infeasible passage stops with zero path advance and
  no collision.
- Hidden complete-world collision is classified separately as
  `partial_observation_world_risk`; it is not treated as an optimizer error.

## Scenario results

- Empty straight and turning: successful, collision-free.
- Single circle and rotated rectangle detours: successful, collision-free.
- Corridor: successful; minimum observable/world clearance 0.375/0.375 m.
- Narrow passage: successful; minimum observable/world clearance 0.260/0.260 m.
- U-shape local case: did not reach the goal; three geometry-check rejections
  caused a safe fallback, with no observable or world collision.
- Infeasible 0.65-m channel: stopped after one cycle with no motion and no
  collision; three rejected candidates were not executed.
- Trust regions small/medium/large all completed the single-circle gate without
  collision. Large trust produced the largest slack, while geometry recheck
  remained active.

Detailed values are in `scenario_metrics.json`, `trust_region_analysis.json`,
and `fallback_test_report.json`.

## Linearization validity

| Perturbation | MAE | P95 |
|---|---:|---:|
| xy 0.01 m, yaw 1 deg | 0.000070 m | 0.000218 m |
| xy 0.03 m, yaw 3 deg | 0.000531 m | 0.001294 m |
| xy 0.05 m, yaw 5 deg | 0.001197 m | 0.003367 m |
| xy 0.10 m, yaw 10 deg | 0.004540 m | 0.014515 m |

Error increases with radius as expected. The configured medium trust region is
retained because nonlinear rollout and exact recheck protect acceptance; the
analysis supports shrinking it on rejection.

## Resolved limitation: dense exact-geometry latency

The earlier implementation mixed complete-world `scene.label()` work into the online checker and performed six Shapely queries per state for finite differences. Its recorded results were:

- Corridor mean/P95: 310.87/364.44 ms.
- Narrow passage mean/P95: 320.72/374.64 ms.

The repaired analytic Oracle preserves the exact rectangle-to-LiDAR-point definition and batches the full horizon. New online P95 is 23.18 ms for corridor and 21.97 ms for narrow passage; single obstacle is 17.03 ms. Observable distance-plus-gradient P95 per SCP is below 0.55 ms in all three cases. Offline world evaluation and visualization are measured separately. Safety checks, `dt_s`, horizon, LiDAR points, and SCP limits were not reduced.

## Verification

- Full standard-library suite: **77 tests passed** in 10.687 s.
- Stage-05 planner/interface/Oracle suite: **25 tests passed** in 1.331 s.
- `python -m compileall`: passed.
- `git diff --check`: passed.
- Deterministic fixed-seed gate/scenario runs: passed.
- No NaN/Inf observed in continuous closed-loop runs.
- DPP/Problem identity regression test: passed.

Commands:

```text
PYTHONPATH=sgcf_nrmp_project/core/src python -m unittest discover -s sgcf_nrmp_project/core/tests -v
PYTHONPATH=sgcf_nrmp_project/core/src python -m unittest discover -s sgcf_nrmp_project/core/tests/planner -v
python -m compileall -q sgcf_nrmp_project/core/src sgcf_nrmp_project/core/scripts sgcf_nrmp_project/core/tests
git diff --check
```

## Artifacts

Required JSON/text outputs are present: planner configuration, scenario metrics,
solver benchmark, trust analysis, linearization analysis, fallback report, test
output, and changed-file list. Required figures are present, including tracking,
obstacle avoidance, corridor, narrow passage, U-shape, infeasible, hidden-world
risk, SCP progress, trust comparison, linearization error, and solver latency.
`gt_nrmp_closed_loop.gif` shows footprint, observed points, reference, optimized
trajectory, executed trajectory, control, and solver status.

## Upstream and scope check

All Stage-05 additions and edits are under `sgcf_nrmp_project/`. Protected paths
show no Stage-05 increment. The repository still reports the pre-existing
` m neupan_ros` state and pre-existing root/docs migration changes; none were
modified, restored, deleted, or formatted by this stage. No new root-level
`sgcf_nrmp_*` directory was created.

Stage 06 was not started.
