# Stage 09C Report

## Outcome

Stage 09C completed. The defect was an unsafe SCP linearization nominal, not a nonlinear recheck defect. In `single_static_obstacle`, the initial future nominal reached zero clearance while the current state remained safe at approximately `0.750956 m`. Collision slots consequently had unusable zero gradients.

The Planner now retains the safe nominal prefix, replaces the unsafe suffix with zero velocity / zero angular velocity terminal hold, and repeats this repair before every sequential relinearization. Recovery QPs additionally require zero geometry slack; this is scoped only to a detected future-unsafe nominal. No threshold, speed bound, geometry API, semantic margin, R1 rule, or final nonlinear recheck was changed.

## Offline evidence

- `empty_world`: `SOLVED_SAFE`; historical candidate maximum error `1.31e-20`.
- `single_static_obstacle`: `SOLVED_SAFE`; candidate `[0.0275245, 0.6000005]`; full-horizon minimum clearance `0.253705 m`; zero violations.
- `initial_collision`: `EMERGENCY_STOP`; zero candidate; recovery not entered.
- failure fixture: `GEOMETRICALLY_INFEASIBLE`; zero candidate.
- CPU performance over 100 cold Planner instances: P95 `151.30 ms`, below `200 ms`.
- Geometry, Planner, semantic, and evaluation suites: 88/88 passed (19 + 51 + 16 + 2).

The full Core discovery passed 182/186 tests. The remaining four are Stage 10 lifecycle tests whose checkpoint files are intentionally absent from this Planner runtime and are outside Stage 09C; no Stage 10 dependency was loaded or repaired.

## Runtime evidence

Only `single_static_obstacle` was run. The active window ended after `2.5 simulated seconds`, once sufficient progress had been obtained.

- Goal-distance reduction: `0.125501 m`.
- Safe nonzero ROS forwarding messages: `36`.
- Candidate → ROS maximum error: `0`.
- ROS → Gazebo maximum error: `0`.
- Minimum runtime `d_geo`: `0.250389 m` (`d_safe = 0.25 m`).
- Collision: false.
- Robot self-return count: `0`.
- Deadline misses / stale inputs / backlog: `0 / 0 / 0`.
- Runtime Planner P95: `57.47 ms`.
- Final linear/angular speed: `0 / 0`.
- Last 0.5 simulated-second translation/yaw: `0 / 0`.
- Residual stage containers/processes: `0 / 0`.

No other world was run and Stage 11C-D2 was not started.
