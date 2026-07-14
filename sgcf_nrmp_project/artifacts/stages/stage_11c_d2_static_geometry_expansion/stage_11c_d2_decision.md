# Stage 11C-D2 Decision

```text
BLOCKED_UNRESOLVED_RUNTIME_FAILURE
```

`single_static_obstacle`, `static_corridor`, and `narrow_passage` passed P0 closed-loop validation. `robot_obstacle` did not produce a legal nonzero actuation: all 20 candidates were rejected by the existing full-horizon Exact Geometry recheck, while the current state remained collision-free. It therefore correctly remained at zero, but the required progress and nonzero-actuation gate was not met.

The observed recheck minimum was approximately `0.2228–0.2475 m` during rejected candidates. Passing this scene would require another Core SCP/recovery algorithm change or a safety-contract relaxation, both prohibited in D2. No such change was made.
