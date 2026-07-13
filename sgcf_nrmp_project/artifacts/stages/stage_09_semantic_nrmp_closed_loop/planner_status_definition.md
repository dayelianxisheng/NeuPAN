# Stage 09 Planner Status Definition and Implemented Scope

## Implemented terminal statuses

The revalidated implementation emits the inherited planner statuses
`SOLVED_SAFE`, `SOLVED_WITH_SLACK`, `REJECTED_BY_GEOMETRY_CHECK`,
`SOLVER_TIMEOUT`, and `EMERGENCY_STOP`. In these artifacts,
`OSQP_OR_SOLVER_USER_LIMIT` is the lifecycle termination reason associated with
the solver `USER_LIMIT` path and may be represented by `SOLVER_TIMEOUT` as the
planner status.

## Planned but not fully implemented semantic statuses

The following belong to the planned semantic status system and are not yet fully
activated end-to-end:

```text
SEMANTICALLY_INFEASIBLE
SEMANTIC_DEGRADED_TO_GEOMETRY
EXPLICIT_FAILURE_GEOMETRY_FALLBACK
```

Consequently:

- semantic infeasibility can currently surface as
  `REJECTED_BY_GEOMETRY_CHECK` or solver timeout/user limit;
- RGB dropout and outdated-image behavior correctly recovers P0-equivalent
  controls, but the current status enum does not fully express the degradation
  cause;
- offline world risk remains separate and must not be conflated with a semantic
  or online planner status.

Completing this taxonomy, diagnosing geometry recheck rejection and solver user
limit, and adding the `human_path_side` regression belong to a future Stage 09B
before ROS/Gazebo. Stage 09B is not implemented by this revision.
