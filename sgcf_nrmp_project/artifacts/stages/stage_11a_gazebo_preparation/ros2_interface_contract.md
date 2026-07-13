# Future ROS 2 Interface Contract

This is a preparation specification, not an implemented ROS 2 node graph.
Every runtime component will use simulation time and timestamped frame IDs.

Inputs are `/scan`, `/camera/image_raw`, `/camera/camera_info`, `/odom`, `/tf`,
and `/tf_static`. Outputs are `/cmd_vel`, `/sgcf_nrmp/planner_status`, and
`/sgcf_nrmp/diagnostics`. `/sgcf_nrmp/oracle_semantics` is simulation-only,
ground-truth-only, and forbidden in real deployment.

The future adapter shall construct the frozen pure-Python contracts before the
planner is called. The online exact-geometry input is derived only from the
current scan and transforms. Oracle semantic data can annotate those same
ordered points for P1/P2 interface validation, but cannot add, delete, or move
points and cannot reach exact geometry. P0 is the formal integration baseline.

No ROS 2 package, node, launch file, bridge, or message filter is implemented
or run in Stage 11A.
