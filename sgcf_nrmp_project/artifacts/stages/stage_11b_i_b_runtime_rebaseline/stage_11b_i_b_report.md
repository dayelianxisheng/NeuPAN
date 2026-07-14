# Stage 11B-I-B Immutable Runtime Re-baseline Report

## Decision

```text
STAGE_11B_I_B_COMPLETE
NEW_IMMUTABLE_RUNTIME_BASELINE_ESTABLISHED
SELF_RETURN_REPRODUCED_ON_REBUILT_IMAGE
VISIBILITY_MASK_FIX_REVALIDATED
READY_FOR_STAGE_11B_I_FORMAL_VISIBILITY_FIX
```

The mutable tag was resolved once to `sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3`. A new container was created directly from that full image ID; its recorded image ID matches exactly. The historical `4585ea…` image remains unavailable and its old container was used only as read-only historical evidence.

Gazebo Sim 8.14.0, SDFormat 14.9.0, gz-rendering ABI 8, OGRE Next 2.3.1, the official OGRE2 alias, dependency closure, HLMS Unlit/PBS resources, GpuRays compositor, and headless rendering all passed.

The first and only formal-asset run reproduced the I-A physical signature exactly: every one of 20 scans contained ten footprint-internal points at beams `43–47` and `133–137`; the nearest point was `[1.2247214544127935e-17, -0.2000121921300888]` m, only `0.00001219` m from the wheel inner surface. Camera delivered 5 nonempty 320×240 frames, and Odometry and simulation clock each delivered 20 monotonic messages.

The second and final run used the I-A visibility values verbatim in `/tmp`: bit `2`, robot flags `2`, LiDAR mask `4294967293`. All 20 scans contained zero finite returns, while Camera, Odometry, and simulation clock remained normal. Both runs cleaned up without residual Gazebo processes, and the stage-specific container was stopped.

Formal Gazebo assets, Docker files, and core algorithms were not modified. This is not `STAGE_11B_I_COMPLETE`, `STAGE_11B_COMPLETE`, or authorization for Stage 11C.
