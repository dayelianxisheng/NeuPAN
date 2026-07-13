# Collision Metric Definition

`initial_collision` is evaluated at the initial pose before the first planner output, using observable and offline world checks. `planner_induced_collision` is true only when that initial pose was safe and an executed control enters observable collision. `trajectory_collision` records collision on a candidate or executed trajectory. `world_collision` remains an offline complete-world metric.

The navigation safety acceptance rate excludes intentionally colliding initial fixtures from its denominator, but those fixtures remain visible through `initial_collision_count`, `correct_emergency_stop_count`, and `initial_collision_response_accuracy`. This changes metric classification only; no collision threshold or geometry definition changed.

