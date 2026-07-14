# Stage 11C-D2 Report

## Parent closure

The prior D1 evidence is formally registered as complete in `stage11cd2_d1_parent_closure.json`; D1/D1A/D1B and Stage 09C reports were not overwritten.

## Scene results

- `single_static_obstacle`: 20 evaluations, 36 nonzero actuation messages, progress `0.125469 m`, minimum `d_geo=0.250389 m`, P95 `57.69 ms`.
- `static_corridor`: initial clearance `0.372866 m`, progress `0.957437 m`, minimum `d_geo=0.368378 m`, P95 `18.53 ms`.
- `narrow_passage`: initial clearance `0.258258 m`, progress `0.957437 m`, minimum `d_geo=0.254597 m`, P95 `17.81 ms`.
- `robot_obstacle`: initial clearance `0.798792 m`, but all 20 evaluations were rejected by full-horizon geometry recheck; no nonzero actuation and no progress. This is a real safety rejection, not a command or transport failure.

All scenes had zero deadline misses, stale inputs, backlog, self-return, collision, and residual processes. Candidate/ROS/Gazebo command errors were zero for executed commands. Full-horizon recheck remained enabled and `d_safe=0.25 m` was unchanged.

The stage stops here because `robot_obstacle` requires another Core recovery change to obtain a legal trajectory. Stage 11C-D3 was not started.
