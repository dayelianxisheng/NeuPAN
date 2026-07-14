# Stage 11B-I-A LiDAR Self-return Diagnosis Report

## Decision

```text
SELF_RETURN_CAUSED_BY_ROBOT_VISUAL_VISIBILITY
VISIBILITY_MASK_FIX_FEASIBLE
READY_FOR_STAGE_11B_I_FORMAL_VISIBILITY_FIX
```

## Environment equivalence

The running container preserves Gazebo Sim 8.14.0, SDFormat 14.9.0, gz-rendering ABI 8, OGRE2, EGL headless rendering, and both installed HLMS media trees. Its rebuilt image is functionally equivalent but not byte-identical to the historical image. The container itself uses image ID `sha256:4585ea4a757bad1cecab7f2943b9f4e6b9d3b3ad18f76848a577f0464be9ea3c`. The local tag currently resolves to a newer rebuild, which did not alter the running diagnostic container.

## Source attribution

The LiDAR origin and scan plane are at base-frame `z=0.2 m`. This is coplanar with the body top and the top tangent of both wheel visuals. The formal run produced exactly ten finite returns in every one of 20 scans at beams `43–47` and `133–137`. The nearest return was beam 45 at `[0.0, -0.200012] m`; the historical beam-43 point `[-0.013986, -0.200011] m` lies on the right-wheel visual's inner AABB surface `y=-0.2 m`. The symmetric cluster lies on the left-wheel inner surface `y=+0.2 m`. The body side is at `|y|=0.25 m` and is a worse geometric match.

Attribution to rendering visuals rather than collision geometry is established by the temporary visibility-only probe: robot collisions were unchanged, while excluding the robot visual bit removed every finite self-return.

## Runtime probe

SDFormat's installed schema explicitly supports `visual/visibility_flags` and `lidar/visibility_mask` as 32-bit unsigned masks. In `/tmp/stage11bia_visibility_probe/`, the three robot visuals used bit `2` and the LiDAR used mask `4294967293`, excluding only that bit. The probe retained 20 LiDAR messages, 5 camera images, and 20 odometry messages. All 20 LiDAR frames had zero footprint-internal points; Camera and Odometry remained operational. Formal Gazebo assets were not modified.

## Why sensor height was not changed

Raising LiDAR changes its absolute pose, scan plane, observable-point distribution, Stage 11A sensor contract, and runtime-clearance relationship. Raising LiDAR and Camera together may preserve their relative transform but still changes `base_link -> lidar_link`, `base_link -> camera_link`, and both world-to-sensor poses. That requires a separately authorized installation-contract revision and frame, sensor, geometry, clearance, and projection regression. It was neither needed nor performed here.

No Planner, Stage 10 model, ROS bridge, other world, adapter filtering, minimum-range change, collision change, or formal visibility fix was executed.
