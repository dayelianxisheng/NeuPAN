# Stage 11C-D1B Core Geometry Recheck Investigation

## Outcome

`BLOCKED_CORE_GEOMETRY_RECHECK_FIX_UNSAFE`

The D1A snapshot deterministically reproduces three `SOLVED_SAFE` QP results followed by `RECHECK_TRUST_REGION_VIOLATION` and minimum exact clearance 0.0. Independent rectangle-frame calculations prove the zero is correct: from horizon index 7 onward, multiple actual LiDAR cylinder-surface points lie inside the 0.8 × 0.5 m robot footprint.

The problem is not variable ordering, units, frame conversion, odometry, duplicate pose integration, dt multiplication, yaw wrapping, empty-point use, batch indexing, or result overwrite. The nominal trajectory itself crosses the obstacle; collision states have unsigned distance zero and invalid geometry gradients, so relaxed QP slots can solve while the nonlinear exact recheck correctly rejects the unsafe result.

Making the pre-fix QP candidate eligible would require weakening/truncating horizon recheck or changing Planner nominal/QP behavior. Both are safety-policy or Planner-main changes prohibited by this stage. Core was left unchanged, Gazebo was not started, and Stage 11C-D2 was not started.
