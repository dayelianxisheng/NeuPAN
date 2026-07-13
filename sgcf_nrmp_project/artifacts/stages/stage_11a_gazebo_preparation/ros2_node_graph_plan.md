# Future ROS 2 Node Graph Plan

The intended headless graph is:

`gz sim sensors/state -> bridge -> contract adapter -> frozen planner -> command safety monitor -> cmd_vel`

The contract adapter owns timestamp, transform, validity, and point-order
checks. The frozen planner owns exact observable geometry and status. The
command safety monitor owns freshness/nonfinite/status-to-zero mappings.

A simulation-only Oracle semantic sidecar may feed Stage 07 Hard
PointPainting for P1/P2 interface checks. It is physically and logically
separate from scan geometry. Stage 10 RGB inference is absent because its
authoritative state is `BLOCKED_OPTIMIZATION_CONVERGENCE`.

Stage 11B must validate bridge message types, QoS, transform availability,
sensor timestamps, and headless startup on a host with Modern Gazebo. It must
not infer runtime readiness from this static graph.
