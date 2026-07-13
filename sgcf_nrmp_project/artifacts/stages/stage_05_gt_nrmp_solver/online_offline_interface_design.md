# Stage 05 Online/Offline Interface Design

The online planner receives only the robot state, reference, current LiDAR scan, previous control, and an `ExactObservableChecker`. The checker owns only cached CPU tensors for observed points, a validity mask, rectangle half-extents, and truncation. It exposes batched distance, distance-plus-autograd-gradient, and observable trajectory recheck operations.

`OfflineWorldEvaluator` is constructed by the simulator, never the planner. It owns complete procedural world geometry and evaluates an already selected/executed trajectory. Its `OfflineEvaluationResult` contains world clearance, collision, hidden-risk classification, collision step, and evaluation latency. These values cannot alter planner status, fallback, control, QP parameters, or warm start.

> 在线规划器只依赖当前 LiDAR 可观测障碍信息；完整世界几何仅由离线评估器使用，不参与控制求解、状态判断、回退决策或 warm start。

`scene.label()` and Shapely finite differences remain unchanged as legacy label/reference interfaces. They are excluded from the normal online planning cycle.
