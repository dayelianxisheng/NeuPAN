# SGCF-NRMP Simulation Final Summary

## Final status

```text
SIMULATION_PIPELINE_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
GEOMETRY_ONLY_P0_NAVIGATION_BASELINE_VALIDATED
GAZEBO_ROS2_CLOSED_LOOP_VALIDATED
ORACLE_SEMANTIC_NEGATIVE_RESULT_RECORDED
RGB_PREDICTION_STAGE_SKIPPED
REAL_ROBOT_DEPLOYMENT_DEFERRED
```

This document closes the current Gazebo simulation mainline. It does not
authorize Stage 16, Stage 17, predicted RGB semantic closed-loop operation, or
real-robot deployment.

## Stage 11C through Stage 15C

- Stage 11C validated the Gazebo–ROS 2–Planner runtime, Safe Actuation Gate,
  200 ms deadline watchdog, full-horizon Exact Geometry recheck, R1 fallback,
  initial-collision emergency stop, and collision-aware nominal recovery. It
  completed with recorded Planner limitations.
- Stage 12 validated deterministic offline ROS 2 nodes, TF and sensor
  synchronization, Planner diagnostics and visualization, ROS/Core replay,
  and self-contained rosbag record/replay without publishing `/cmd_vel`.
- Stage 13 validated the minimal Gazebo sensor and DiffDrive chain, frozen
  LiDAR–RGB projection, simulation time, TF, controlled motion, and zero-stop.
- Stage 14 integrated the local Depot scene through a non-vendor overlay. Its
  license remains `LICENSE_UNKNOWN_LOCAL_TEST_ONLY`; the vendor mesh is
  visual-only and the scored geometry conclusions do not depend on it.
- Stage 15 and Stage 15A found a navigation floor effect and separated safe
  semantic rejection from the missing full P0 goal-reaching baseline.
- Stage 15B established the missing Geometry-only P0 baseline with the frozen
  differential-drive robot and safety contract.
- Stage 15C repeated the Oracle comparison on three P0-feasible semantic
  overlays and recorded a negative result.

## Geometry-only P0 navigation baseline

Stage 15B reached the formal goal tolerance in:

- `empty_world`: 3/3;
- `single_static_obstacle`: 3/3;
- `static_corridor`: 3/3;
- `narrow_passage`: 3/3.

Across the selected baseline runs, Planner-induced collisions, stale/late or
ineligible command execution, ROS/Core replay error, command-chain numerical
error, and robot self-return were zero. All runs passed zero-stop, and the
maximum command-eligible P95 latency was 23.60 ms. The original mixed P0 scene
remains a safe-rejection Planner-completeness case and is not counted as a
successful navigation baseline.

## Exact Geometry and safety execution chain

Exact Observable Geometry remains the physical safety basis. Semantic input
does not replace observable LiDAR points, `d_geo`, `g_geo`, the 0.8 × 0.5 m
footprint, `d_safe`, or the full-horizon nonlinear recheck. Runtime evidence
validated:

- the Safe Actuation Gate as the only authorized command publisher;
- rejection of stale, late, nonfinite, ineligible, or expired candidates;
- the 200 ms deadline watchdog and diagnostic-only treatment of late results;
- candidate-to-ROS-to-Gazebo numerical preservation;
- zero fallback and final zero-stop;
- `initial_collision` as `EMERGENCY_STOP`;
- no LiDAR self-return after the Gazebo visibility isolation fix.

These empirical checks do not constitute a formal safety proof or guarantee.

## Stage 09C nominal recovery

Stage 09C collision-aware safe nominal recovery remains enabled. It repairs
the nominal lifecycle used for safe planning without weakening Exact Geometry,
the full-horizon recheck, `d_safe`, the footprint, the deadline gate, or command
eligibility. Its CPU and runtime regressions remained part of the Stage 11C and
Stage 15B/15C validation chain.

## Oracle semantic result

Stage 15C used only `ORACLE_GROUND_TRUTH`, `SIMULATION_ONLY` semantics. It did
not run Stage 10 or load a predicted RGB checkpoint. Thirty deterministic
P0/P2 pairs produced:

- P0 success: 30/30;
- P2 success: 10/30;
- P2 relative change: -66.67 percentage points;
- VEHICLE P2 success: 10/10;
- HUMAN and mixed P2: rejected by the frozen formal semantic safety
  constraints;
- collision and erroneous command execution: zero.

Although rejected or stationary P2 runs sometimes had larger offline measured
clearance, that increase came primarily from safe stopping and is not a
successful-navigation safety benefit. The project therefore does not claim
that Oracle semantics improve navigation safety or success rate.

## Stage 16 disposition

Stage 16 is recorded as:

```text
STAGE_16_SKIPPED_DUE_TO_UNESTABLISHED_ORACLE_BENEFIT
```

The Oracle experiment did not establish the prerequisite benefit needed to
justify predicted RGB semantic closed-loop integration. No evidence supports a
claim that RGB prediction is ready for closed-loop navigation.

## Known Planner limitations

- The original mixed P0 scene remains safely rejected.
- `robot_obstacle` retains a Planner-completeness limitation.
- HUMAN center/side constraints can reject otherwise Geometry-feasible motion.
- Semantic-infeasible failure paths can exceed the deadline, but the watchdog
  keeps diagnostic-only results out of actuation.
- Static or instantaneous obstacle validation does not cover future human or
  vehicle trajectory prediction.
- The current results do not provide a formal safety guarantee.

## Stage 17 and real-robot migration

Stage 17 real-robot deployment is deferred. The available `example/mowen`
material is a read-only ROS 1 Melodic / Ubuntu 18.04 legacy reference for an
omnidirectional chassis, not the validated differential-drive Gazebo robot.
Its footprint, kinematics, DUNE weights, MCU command-retention behavior, and
incomplete sensor/extrinsic records cannot be substituted into the current
contract.

Before any real-robot deployment, a separately authorized migration must
establish ROS 1 to ROS 2 interfaces, omnidirectional motion and control
kinematics, the measured real footprint, verified LiDAR/IMU identities and
extrinsics, and a hardware-safe execution chain. The MCU stop contract must
continuously publish zero Twist at 50 Hz for at least three seconds. None of
that migration is performed by this simulation closure.
