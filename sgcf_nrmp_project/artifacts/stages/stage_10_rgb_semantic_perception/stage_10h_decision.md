# Stage 10H Decision

```text
BLOCKED_HUMAN_RECALL
```

The repaired early-stopping policy succeeded operationally and the formal retry passed validation readiness. The frozen checkpoint and validation-selected `U0_argmax_always` policy were evaluated once on test.

Test HUMAN recall was `0.7134025339642802`, below the fixed `0.80` gate. HUMAN IoU was `0.5772603754940712`, also below the suggested `0.60` target. Therefore PointPainting, Semantic Margin, robustness, and CPU latency evaluation were not executed.

`best_rgb_semantic_model.pt` is retained as the validation-selected diagnostic/formal-retry checkpoint, but it is **not accepted as a final Stage 10 model** and is not authorized for Planner, ROS, Gazebo, or deployment use.
