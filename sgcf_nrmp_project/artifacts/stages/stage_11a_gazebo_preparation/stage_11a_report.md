# Stage 11A Gazebo Simulation Preparation Report

## 1. Executive summary

Stage 11A completed the static Gazebo assets and integration contracts without
starting Gazebo, ROS 2, or a planner closed loop. The authoritative decision is:

```text
STAGE_11A_COMPLETE_WITH_RUNTIME_UNAVAILABLE
STATIC_GAZEBO_PREPARATION_COMPLETE
RUNTIME_VALIDATION_REQUIRED_ON_GAZEBO_HOST
```

This host has Python 3.10 but no `gz`, `gazebo`, `ign`, `ros2`, `colcon`, or
`xacro` executable. SDF 1.9 and Modern Gazebo / `gz sim` were selected as the
single static target. No runtime result or Gazebo screenshot is claimed.

## 2. Inherited boundaries

Stage 09B remains
`STAGE_09B_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS` and
`READY_FOR_GAZEBO_PREPARATION_WITH_RESTRICTIONS`. Stage 10 remains
`BLOCKED_OPTIMIZATION_CONVERGENCE` with no further tuning authorized for its
current configuration.

P0 geometry-only is therefore the formal future integration baseline. P1/P2
can use only the clearly marked `GAZEBO_ORACLE_SEMANTIC_SIDECAR` for simulator
interface checks. The sidecar is ground truth, is not an RGB model, and cannot
enter or modify exact observable geometry.

No Stage 05 geometry, Stage 07 projection/margin, Stage 08 gate, Stage 09/09B
planner, safety distance, horizon, trust region, or solver setting was changed.

## 3. Environment and selected simulator

- Selected simulator contract: Modern Gazebo / `gz sim`.
- Asset format: SDF 1.9.
- Gazebo runtime available: no.
- ROS 2 tooling available: no.
- Runtime actions executed: none.
- Required future resource path: `sgcf_nrmp_project/gazebo/models`.

The missing runtime is handled by the explicitly permitted static-preparation
outcome. Installation, network access, sudo, and bridge setup were not used.

## 4. Assets and scenarios

Six primitive-only models and twelve deterministic worlds were generated. The
robot uses a `0.8 x 0.5 x 0.2 m` collision body; placeholder objects use boxes
or cylinders with no external meshes, textures, plugins, or downloads.

The scenario manifest includes `empty_world`, static obstacle/corridor/narrow
passage scenes, HUMAN center/side scenes, vehicle and robot obstacles,
semantic infeasibility, intentional initial collision, and RGB dropout/outdated
contracts. Scene IDs, start/goal/reference, obstacles, classes, sensor configs,
and seed 909 are fixed.

Static comparison caught and corrected one asset-generation defect before
acceptance: the first generated `single_static_obstacle` SDF used a box while
the frozen manifest required a cylinder. An independent `static_cylinder`
model now represents that scene; corridor walls continue to use boxes.

## 5. Coordinate, sensor, and time contracts

The contract uses a right-handed frame tree:

```text
world -> odom -> base_footprint -> base_link
                                  |-> lidar_link
                                  `-> camera_link -> camera_optical_frame
```

`base_link` uses x-forward, y-left, z-up. The optical frame uses x-right,
y-down, z-forward. All transforms are documented as `T_target_source`.

The LiDAR contract has 181 ordered samples over `[-pi, pi]`, range
`[0.05, 8.0) m`, and 10 Hz rate. Invalid/nonfinite/maximum-range returns retain
their ordered slot, receive a false valid mask, and do not delete geometry
array entries.

The camera contract is exactly the Stage 07 configuration: `320 x 240`,
`fx=fy=180`, `cx=160`, `cy=120`, near clip `0.05 m`, and

```text
T_camera_optical_frame_lidar_link =
[[0, -1,  0, 0.0],
 [0,  0, -1, 0.8],
 [1,  0,  0, 0.0],
 [0,  0,  0, 1.0]]
```

RGB age is limited to 0.10 s, LiDAR age to 0.20 s, and RGB/LiDAR skew to
0.05 s. Dropout, stale RGB, invalid projection/transform, or UNKNOWN disables
semantic contribution under the frozen R1 rules.

## 6. Robot geometry and static consistency

The SDF collision and Stage 05 footprint are both a centered
`0.8 x 0.5 m` rectangle. Neither is reduced to make a scene easier.

Static validation parsed the actual world includes, model collision geometry,
poses, and scales and compared them with the frozen scenario/Stage 02/05
definitions:

| Metric | Result |
|---|---:|
| XML/model files parsed | 24 |
| Scenarios | 12 |
| Obstacles compared | 13 |
| Maximum pose error | 0 |
| Maximum size error | `2.78e-17 m` |
| Observable boundary-point error | `1.11e-16 m` |
| Maximum clearance error | `1.03343e-4 m` |
| Declared clearance tolerance | `5e-4 m` |
| Collision classification agreement | 100% |

The nonzero clearance difference is explicitly retained: SDF cylinders are
analytic while frozen Stage 02 circles use Shapely `resolution=32`. It is not a
runtime measurement and is not hidden as zero.

## 7. Pure-Python adapter boundary

Typed immutable frames cover scan, image, camera info, robot state, transform,
Oracle semantics, and planner input/output. The adapters:

- transform ordered scan ranges to base-frame observable points;
- validate the Stage 07 camera convention without performing segmentation;
- convert pose/quaternion/twist to planner state;
- attach simulation-only semantic IDs without changing point coordinates,
  range slots, validity masks, or point order;
- implement R1 time/validity decisions;
- map stale, invalid, nonfinite, or unsafe-status outputs to zero velocity.

World geometry is absent from the online adapter data structures and cannot
affect status, warm start, fallback, or control.

## 8. Oracle semantic sidecar

The sidecar maps simulator model labels to the frozen classes:

```text
UNKNOWN=0, STATIC_OBSTACLE=1, HUMAN=2, VEHICLE=3, ROBOT=4
```

Margins remain exactly `0.00, 0.00, 0.35, 0.20, 0.15 m`. UNKNOWN and invalid
projection yield zero semantic contribution. The sidecar may support future
P1/P2 integration checks but cannot be presented as real-camera validation.

## 9. `human_path_side` known limitation

The Gazebo asset preserves the Stage 09B start, reference, HUMAN pose
`[1.5, 0.35, 0]`, radius `0.35 m`, footprint, and margins. Stage 11A does not
claim resolution of the known behavior:

- P0: exact clearance `0.2465197271 m < 0.25 m`, rejected by exact recheck;
- P1/P2: `OSQP_MAX_ITER_REACHED`, 10000 iterations.

The scene remains in the manifest as a required regression case.

## 10. Future ROS 2 and command contracts

The topic and node-graph documents specify future scan, image, camera info,
odometry, transform, command, status, and diagnostic interfaces. The Oracle
topic is marked simulation-only, ground-truth-only, and forbidden for real
deployment. No ROS 2 package, node, launch file, or bridge was created.

The future command boundary accepts only valid, finite, fresh outputs with a
motion-permitting status. Emergency, infeasible, solver-failure, recheck,
stale, invalid, nonfinite, or unknown outputs map to `v=0, omega=0`.

## 11. Latency preparation

The Stage 09B references are retained without remeasurement:

- steady-state online P95: `37.72 ms`;
- first-cycle setup-inclusive P95: `279.26 ms`.

The future steady-state interface budget totals `100 ms`, reserving explicit
time for sensing/queueing, transform lookup, adapter conversion, planner,
publication, safety monitoring, and contingency. Runtime must warm sensors,
transforms, and the persistent solver before enabling commands.

## 12. Static verification

Stage 11A contract tests cover XML/reference/name validity, unique scenarios,
class IDs, acyclic frames, LiDAR conversion/order/invalid handling, camera
consistency, footprint equality, semantic geometry preservation, R1 shutdown,
safe zero-command mapping, frozen `human_path_side`, and JSON parsing.

Gazebo runtime load/spawn/headless/sensor checks are explicitly not executed.
The generated figures are parameter/asset diagrams, not simulator screenshots.

## 13. Decision and Stage 11B boundary

Static assets, contracts, adapters, geometric comparisons, ROS 2 preparation,
and safety mappings are complete. Runtime readiness is not established because
the simulator is unavailable. Stage 11B may perform only headless runtime smoke
validation on a host with the selected Modern Gazebo version, beginning with
P0 and preserving all frozen modules and restrictions.
