# Stage 05 Latency Definition

`online_equivalent_planner_latency` includes LiDAR observation preparation, reference/control logic, batched observable distance and gradient, QP parameter update, OSQP solve, batched observable trajectory recheck, and fallback/control selection. Its acceptance gate is P95 below 100 ms.

`offline_world_evaluation_latency` includes complete-world clearance/collision and hidden-risk classification after online control selection. `visualization_latency` includes plotting and image writing. Neither offline category contributes to the online gate, but both are reported independently.

The simulator uses world geometry to synthesize LiDAR data, as a physical sensor surrogate. Only the resulting scan crosses the planner boundary; the planner does not receive the scene or obstacle polygons.
