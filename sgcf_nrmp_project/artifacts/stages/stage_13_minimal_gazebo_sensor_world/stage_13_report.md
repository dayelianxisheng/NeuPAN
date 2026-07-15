# Stage 13 Minimal Gazebo Sensor World Report

## Outcome

Stage 13 passed. The existing Stage 11 `single_static_obstacle` world, robot SDF, self-visibility contract, and Stage 11C six-topic bridge were sufficient, so no Gazebo asset or Docker image was created or modified.

Runtime images were bound by local full IDs:

- Gazebo Harmonic: `sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3`
- ROS 2 Humble bridge: `sha256:69ec4a1e2134de8e05532386c4220e8ea4a91107b8bf1947dab4f07948af275f`

## Zero-motion sensor test

The zero-command run observed 5 simulated seconds after sensor readiness. It collected 7,005 clock messages, 70 LaserScans, 70 RGB images, 70 CameraInfo messages, and 350 Odometry messages. All timestamps were monotonic and used Gazebo simulation time. Camera frames were `320×240`, `rgb8`, and matched the frozen intrinsics. Odometry displacement was `7.50e-20 m`; nonzero command count, nonfinite values, and robot self-return count were all zero.

The ROS TF tree was constructed from frozen contracts: dynamic `odom → base_link` from bridged Odometry, and static `base_link → lidar` / `base_link → camera` transforms. Camera-to-LiDAR TF lookup succeeded on 100% of attempts in both runs.

## Controlled command test

The second independent run published only `linear.x=0.10 m/s`, `angular.z=0` for approximately one simulated second, followed by zero for at least two simulated seconds. ROS and Gazebo unique command sets were identical and the maximum component error was zero.

- Positive x displacement: `0.101900 m`
- Absolute y drift: `3.35e-16 m`
- Final linear/angular speed: `0 / 0`
- Minimum final runtime LiDAR range: greater than the footprint front extent
- Observable collision: false

Clock, LiDAR, RGB, CameraInfo, Odometry, and TF remained active throughout motion.

## LiDAR–RGB projection

Projection used only runtime LaserScan points, frozen `T_camera_lidar`, and bridged CameraInfo. The known cylinder return supplied 13 observable target points; 4 projected inside the camera image because the low LiDAR plane places central returns below the lower image boundary. All 4 valid projections landed on the cylinder's visible `[75,75,75]` pixels.

- Valid projection count: `4`
- In-image ratio: `30.77%`
- Correct-object hit ratio among valid projections: `100%`
- Mean/max projection residual: `0.402 / 0.528 px`

No world geometry replaced LaserScan input, and no extrinsic adjustment, pixel offset, or Stage 10 prediction was used.

## Boundaries and cleanup

Planner, Core planning, Stage 10, and semantic navigation were not started. Both rounds used independent Gazebo and Bridge containers. Final residual container and process counts were zero.
