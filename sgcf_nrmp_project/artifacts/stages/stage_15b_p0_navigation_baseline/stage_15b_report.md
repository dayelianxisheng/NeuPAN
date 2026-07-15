# Stage 15B Geometry-only P0 Navigation Baseline

Decision: `STAGE_15B_COMPLETE`.

The fixed static-scene thresholds were met and every safety gate passed. The single-obstacle floor effect was traced to the original avoid path's early curvature and corrected with a Stage 15B-only explicit reference path. No Core, geometry, d_safe, footprint, solver, or Gazebo asset changed. The mixed diagnostic scene remained safely rejected and is retained as a planner-completeness limitation.

## Results

- `empty_world`: 3/3 goal reached, collisions=0, max eligible P95=17.538 ms
- `single_static_obstacle`: 3/3 goal reached, collisions=0, max eligible P95=23.601 ms
- `static_corridor`: 3/3 goal reached, collisions=0, max eligible P95=22.286 ms
- `narrow_passage`: 3/3 goal reached, collisions=0, max eligible P95=23.156 ms
- `mixed`: 0/3 goal reached, collisions=0, max eligible P95=0.000 ms
