# Stage 11B-I Formal LiDAR Self-visibility Isolation Report

## Attempt history and decision

```text
previous_attempt = BLOCKED_RUNTIME_IMAGE_ID_UNAVAILABLE
current_attempt = FORMAL_VISIBILITY_FIX

STAGE_11B_I_COMPLETE
LIDAR_SELF_VISIBILITY_ISOLATED
EXTERNAL_OBSTACLE_DETECTION_PRESERVED
CAMERA_AND_ODOMETRY_PRESERVED
READY_TO_RERUN_STAGE_11B_FULL_RUNTIME_MATRIX
```

The formal run used immutable image `sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3` directly. The robot asset now applies the twice-validated visibility contract: all three actual robot-owned visuals use flag `2`, and the LiDAR mask `4294967293` excludes that bit. No external visual was changed.

The robot model hash changed from `3e374265419ae09961d772b03c23813c8c433c456ab39ea234cc23527c2aaf1c` to `3fc0c6077a99591802370181c2f2e57196171b58a5622c6ccb7344d2702b7a52` solely through the four authorized XML paths. Collision, inertial-bearing link content, sensor poses, LiDAR non-visibility parameters, Camera, joints, DiffDrive, obstacle models, and all 12 world files remain unchanged. No Adapter or point filtering was added.

## Targeted runtime gates

- `empty_world`: all 20 scans had zero finite self-return and zero footprint-internal points.
- `single_static_obstacle`: runtime exact observable clearance `0.750956 m` versus authoritative `0.750000 m`; non-collision.
- `human_path_side`: runtime exact observable clearance `0.756248 m` versus same-query authoritative `0.754536 m`; non-collision. The Stage 09B Planner rejection / OSQP limitations remain unresolved because no Planner was run.
- `initial_collision`: the external obstacle remained visible, produced `57` footprint-internal points, and exact clearance remained zero / collision true.

Geometry classification agreement was 3/3. Camera and Odometry passed in 4/4 scenes; simulation clock advanced in every independent run. Each world used a separate Gazebo process and cleanup passed. The stage container was stopped with zero host or container Gazebo residuals.

This is not `STAGE_11B_COMPLETE` and does not authorize Stage 11C. The next authorized action is rerunning the Stage 11B full runtime matrix.
