# Gazebo Command Safety Contract

Stage 11A defines a future actuator boundary; it does not publish commands.
Commands are accepted only when the planner output is valid, finite, fresh
(`age <= 0.20 s`), and its status permits motion. Otherwise the mapping emits
`v=0, omega=0` with `ZERO_VELOCITY_FALLBACK`.

`EMERGENCY_STOP`, invalid input, geometric or semantic infeasibility, solver
limit/timeout, numerical failure, and geometry-recheck rejection all map to
zero velocity. `SUCCESS`, `GOAL_REACHED`, and the two explicitly identified
geometry fallback statuses may carry a finite, fresh command; `GOAL_REACHED`
normally supplies zero velocity from the planner.

The safety adapter is independent of the offline world evaluator. World
collision labels can never authorize, reject, or alter a command.
