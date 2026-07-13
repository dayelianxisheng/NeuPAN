# Stage 07 Redefinition

Stage 07 is now:

```text
RGB–LiDAR Projection, Semantic Ground Truth and PointPainting Baseline
```

Its scope is limited to:

1. camera model and RGB–LiDAR projection;
2. timestamp and extrinsic interfaces;
3. semantic class data structures;
4. Oracle semantic labels;
5. PointPainting baseline;
6. nonnegative semantic-margin label definition;
7. projection and painted-point visualization;
8. no main-planner closed-loop integration.

Sparse Local Soft Fusion is deferred to Stage 08. Stage 07 must not implement the main fusion method, RGB planner integration, ROS, Gazebo, or dynamic-obstacle prediction.
