# Stage 11C-D1A Speed-contract Alignment and Geometry Diagnosis

## Outcome

Stage 11C-D1A completed its two scoped objectives. The effective formal limits are 1.0 m/s and 1.5 rad/s in both Planner and DiffDrive. The wrapper-local 0.15/0.50 limits were removed; candidates are forwarded unchanged or rejected, never clamped.

`empty_world` forwarded 160 nonzero commands, reduced goal distance by 1.920158 m, had zero collision/self-return/deadline/stale-execution events, and passed final zero-stop. Candidate-to-ROS and ROS-to-Gazebo maximum errors were 0 and 0.

`single_static_obstacle` remained hard-zero and produced 20/20 `REJECTED_BY_GEOMETRY_CHECK`. Inputs and replay are correct. Each QP solve reports `SOLVED_SAFE`, but the formal exact recheck predicts minimum clearance 0.0 and reports `RECHECK_TRUST_REGION_VIOLATION` through three reduced trust regions. This is classified `CORE_GEOMETRY_RECHECK_LIMITATION`; modifying Core is outside scope.

Stage 11C-D2 was not started.
