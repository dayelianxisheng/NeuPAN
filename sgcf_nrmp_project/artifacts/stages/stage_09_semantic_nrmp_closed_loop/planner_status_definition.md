# Planner Status Definition

The existing Stage 05 statuses remained active during the stopped run. The proposed semantic-specific statuses were not activated because the first evaluation triggered mandatory stop conditions before the semantic infeasibility classifier was completed.

Observed terminal statuses include `SOLVED_SAFE`, `SOLVED_WITH_SLACK`, `REJECTED_BY_GEOMETRY_CHECK`, `SOLVER_TIMEOUT`, and `EMERGENCY_STOP`. A subsequent authorized repair should add `SEMANTICALLY_INFEASIBLE`, `SEMANTIC_DEGRADED_TO_GEOMETRY`, and `EXPLICIT_FAILURE_GEOMETRY_FALLBACK` without conflating them with offline world risk.

