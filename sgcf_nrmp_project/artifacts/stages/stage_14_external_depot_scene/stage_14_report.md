# Stage 14 External Depot Scene Integration

## Decision

`STAGE_14_COMPLETE_WITH_LOCAL_VENDOR_RESTRICTIONS`

The local Depot model was mounted read-only and integrated through an SDF 1.9 overlay. Zero-motion sensors, TF, the low-speed command chain, zero-stop, and LiDAR-to-RGB projection passed. No Planner, Stage 10, or semantic navigation component ran.

## Vendor boundary

No license file was present, so the asset is `LICENSE_UNKNOWN_LOCAL_TEST_ONLY`. Neither the ZIP nor extracted vendor files are tracked or redistributable. The requested `/home/qcqc/Depot.zip` was absent on this host; the byte source was resolved to `/home/zq/Downloads/Depot.zip` and pinned by SHA-256.

## Compatibility

Gazebo Harmonic accepted deprecated Ignition joint-controller aliases at runtime. Ogre material scripts are unsupported, while the included PBR materials rendered. The vendor building mesh has no collision geometry beyond a 100 x 100 ground plane; the overlay target supplies the audited physical/projection obstacle.

## Runtime

Both bounded runs used simulation time, preserved the Stage 11 sensor and frame contracts, produced zero self-return, and cleaned all containers and processes. The motion run displaced the robot in +x and then returned to zero velocity.
