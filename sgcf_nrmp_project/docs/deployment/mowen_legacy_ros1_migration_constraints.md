# Mowen Legacy ROS 1 Migration Constraints

`example/mowen` is read-only legacy NeuPAN real-robot reference material. It
targets Ubuntu 18.04 and ROS 1 Melodic.

The recorded robot uses omni kinematics with a `0.42 × 0.26 m` footprint. Its
LiDAR is identified as a Leishen N10, but the recorded channel count is
inconsistent. The exact IMU model and the LiDAR-to-IMU extrinsic calibration
are not confirmed.

The MCU retains the last velocity command. Stopping therefore requires a zero
Twist to be published continuously at 50 Hz for at least three seconds.

The legacy deployment loads DUNE weights and is not the current Geometry-only
P0 system. It does not satisfy the conditions for direct Stage 17 execution.
Future deployment requires migration to ROS 2, support for omni kinematics,
validation of the real footprint, and integration with the current safe
actuation chain.

```text
MOWEN_LEGACY_ROS1_DEPLOYMENT_DATA_FOUND
STAGE17_HARDWARE_INFORMATION_PARTIALLY_AVAILABLE
DIRECT_STAGE17_DEPLOYMENT_NOT_READY
ROS2_AND_ROBOT_CONTRACT_MIGRATION_REQUIRED
```
