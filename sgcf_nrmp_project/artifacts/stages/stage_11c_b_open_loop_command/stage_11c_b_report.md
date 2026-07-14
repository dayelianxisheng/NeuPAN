# Stage 11C-B ROS 2 Open-loop Command Integration Report

## Executive Summary

Stage 11C-B validated the nonzero command path

```text
ROS 2 /cmd_vel publisher
→ ros_gz_bridge
→ Gazebo /cmd_vel
→ DiffDrive
→ Gazebo odometry
→ ROS /odom
```

using one deterministic `empty_world` sequence. The bridge preserved all Twist
components exactly, positive linear velocity produced initial `base_link +x`
motion, positive angular velocity produced positive yaw, and both zero-command
phases stopped the robot. LiDAR, RGB camera, CameraInfo, clock, and odometry data
continued during motion.

Final decision:

```text
STAGE_11C_B_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS
```

## Runtime Binding

- Gazebo immutable image: `sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac`
- Bridge immutable image: `sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862`
- Runtime baseline: `FUNCTIONALLY_EQUIVALENT_RUNTIME_BASELINE`
- Historical Stage 11B-N image: unavailable and not binary-identical
- ROS: Humble; bridge: `ros_gz_bridge`
- Gazebo Sim: 8.14.0; SDFormat: 14.9.0; gz-rendering ABI: 8
- Network: host; `ROS_DOMAIN_ID=42`; `GZ_PARTITION=sgcf_stage11ca`

Both formal containers were started from full immutable image IDs. No image was
rebuilt or modified.

## Command Profile and Sequence

Stage 11B-F preserved motion results but not exact command amplitudes and
durations, so the explicitly authorized conservative fallback was used:

| Phase | Command | Simulation duration |
|---|---:|---:|
| zero baseline | zero Twist | 1.0 s |
| positive linear | `linear.x=0.10 m/s` | 1.0 s |
| zero after linear | zero Twist | 1.0 s |
| positive angular | `angular.z=0.30 rad/s` | 1.0 s |
| zero after angular | zero Twist | 1.0 s |
| final stationary | zero Twist | 2.0 s |

All phase changes used subscribed ROS `/clock` simulation timestamps. Wall time
was used only for the 60-second process safety timeout.

## Command Bridge Consistency

The ROS and Gazebo captures each contained 452 Twist samples. Their unique values
were exactly:

```text
(linear.x, angular.z) = (0,0), (0.1,0), (0,0.3)
```

- Maximum component error: 0
- Sign agreement: 100%
- Unauthorized nonzero component count: 0
- Authorized ROS `/cmd_vel` publisher count: 1
- `cmd_vel` bidirectional loop: absent

## Stationary Baseline

Before the first nonzero command, 96 odometry messages, 30 scans, and 30 images
were observed. Position range was `2.19e-20 m`, yaw range was `1.24e-20 rad`, and
there was no sustained uncommanded motion.

## Positive Linear Motion

- Command: `+0.10 m/s` for 1.0 simulated second
- Expected ideal displacement: 0.1000 m
- Measured displacement along initial `base_link +x`: 0.0969 m
- Lateral displacement: `3.29e-16 m`
- Yaw change: `-5.38e-15 rad`

The measured forward distance was 96.9% of the ideal value and was inside the
authorized 50–150% interval.

## Linear Stop Response

After the linear command, the final linear and angular velocities were zero. In
the last 0.5 simulated second, both additional displacement and yaw were zero.
The first stopped odometry response was observed approximately 0.02 s after the
zero phase began.

## Positive Angular Motion

- Command: `+0.30 rad/s` for 1.0 simulated second
- Expected ideal yaw: 0.3000 rad
- Measured unwrapped yaw: 0.2907 rad
- Translation during rotation: `5.83e-17 m`

The measured yaw was positive and 96.9% of the ideal value.

## Angular Stop and Final Stationary Gates

After the angular command, final linear and angular velocity were zero. The last
0.5-second stop window had zero translation and yaw. The two-second final window
contained 100 odometry messages, 20 scans, and 20 images, with exactly zero pose
drift and no delayed stale nonzero command.

## Sensor Data-plane Regression

The completed motion run recorded:

| Stream | Messages |
|---|---:|
| `/clock` | 8,980 |
| `/scan` | 90 |
| `/camera/image_raw` | 90 |
| `/camera/camera_info` | 90 |
| `/odom` | 448 |

Timestamps were monotonic without negative jumps. Camera data remained
`320×240 RGB8`; odometry values remained finite. LiDAR self-return count across
wheel-sensitive beams 43–47 and 133–137 was zero, and no point filtering was
introduced.

## Frame Contract

- Odometry: `odom → base_link`
- LiDAR: `sgcf_robot/lidar_link/lidar`
- Image and CameraInfo: `sgcf_robot/camera_link/rgb_camera`

Linear direction was evaluated by projection onto the initial `base_link`
orientation, not by assuming world +x.

## Latency Scope

Command-to-first-odometry response was approximately 0.01 s for both linear and
angular commands; zero-to-stopped-odometry response was approximately 0.02 s.
These are single-sequence descriptive samples. Gazebo Twist carries no timestamp,
so a separate ROS-to-Gazebo transport delay and P95 are not claimed.

## Safety, Boundaries, and Cleanup

No Planner, Stage 10, PointPainting, Semantic Margin, Nav2, robot state publisher,
TF publisher, GUI, RViz, obstacle scenario, or negative command was used. Gazebo
assets, core algorithms, Docker images, footprint, wheel geometry, sensor
contracts, and bridge directions were unchanged. Residual stage containers and
host processes were both zero.

The frozen bridge image lacks `colcon`, so that command could not be used without
violating the no-install rule. The same image successfully built the
`ament_python` package with setuptools into container `/tmp`. Standard-library
unit tests, `compileall`, JSON parsing, and `git diff --check` also passed.

## Preflight Incident

An initial launch attempt stopped before node construction because ROS 2 Humble
had already declared `use_sim_time` and the test node attempted to declare it
again. No nonzero command or Phase 0–5 sequence occurred. The diagnostics are
retained under `logs/preflight_node_constructor_failure/`. The test-only node was
corrected, then the single completed formal sequence above was executed.

## Decision

All command value, direction, stop-response, sensor, self-visibility, frame, and
cleanup Gates passed. The known limitations are the functionally equivalent
Gazebo image, single-sequence latency evidence, and inherited nonfatal headless
rendering warnings. Therefore the selected state is:

```text
STAGE_11C_B_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS
ROS_TO_GAZEBO_NONZERO_COMMAND_PATH_VALIDATED
POSITIVE_LINEAR_DIRECTION_VALIDATED
POSITIVE_ANGULAR_DIRECTION_VALIDATED
ZERO_STOP_RESPONSE_VALIDATED
SENSOR_DATA_PLANE_PRESERVED_DURING_MOTION
READY_FOR_STAGE_11C_C_WITH_RESTRICTIONS
```

This result does not mark Stage 11C complete and does not authorize planner
closed-loop operation.
