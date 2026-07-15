# Stage 11C Final Evaluation Report

## Outcome

Stage 11C is complete with known Planner limitations. This evaluation assembled the authoritative Stage 11B-N, Stage 11C-A through D3A, Stage 09C, amended D2, and local environment evidence. It ran only fast regression tests—no Gazebo scenario, Planner closed loop, Stage 10 inference, image build, or subsequent stage was started.

## Validated integration and closed loops

The Gazebo–ROS 2 sensor plane, directional command bridge, zero command, nonzero open-loop direction, stop response, CPU Planner runtime, ROS/Core replay, deadline watchdog, Safe Actuation Gate, and cleanup contracts passed.

P0 closed-loop validation passed for:

- `empty_world`: goal progress `1.920158 m`.
- `single_static_obstacle`: Stage 09C safe nominal recovery produced `0.125501 m` progress with minimum exact clearance `0.250389 m`.
- `static_corridor`: goal progress `0.957437 m`.
- `narrow_passage`: goal progress `0.957437 m`.

The mandatory full-horizon nonlinear Exact Geometry recheck remained authoritative. Stage 09C repair changes unsafe nominal suffixes to dynamically valid terminal holds without weakening `d_safe`, semantic margins, speed bounds, or the final nonlinear check.

`initial_collision` remained an intentional pre-control collision fixture and returned `EMERGENCY_STOP`. It is not counted as a Planner-induced collision.

## Semantic and failure contracts

Only Gazebo Oracle Ground Truth semantics were used. Stage 10 was not started and no predicted checkpoint was loaded.

- `semantic_infeasible`: safely rejected; command-ineligible results remained diagnostic and zero-actuated.
- RGB dropout: `semantic_valid=false`, `RGB_DROPOUT`, semantic margin zero, and synchronized P0 fallback differences zero.
- Outdated RGB: simulation-time `OUTDATED_IMAGE`, semantic margin zero, and synchronized P0 fallback differences zero.
- `human_path_center`: expected safe semantic rejection at margin `0.35`.
- `human_path_side`: safe semantic rejection.
- `vehicle_path`: 196 eligible P2 nonzero actuation messages were transmitted with exact candidate→ROS→Gazebo values, no collision or runtime safety violation, and P95 `41.37 ms`. Goal distance increased by `0.31891 m`, so semantic navigation success is not claimed.
- `robot_obstacle`: safely rejected with no collision; feasible-trajectory search completeness remains a known Planner limitation.

Semantics did not modify Exact Geometry: identical-query P0/P2 point counts, `d_geo`, and `g_geo` matched exactly, and maximum ROS/Core replay error was zero.

## Aggregate safety result

- Planner-induced collision: `0`
- Robot self-return: `0`
- Stale, late, or ineligible candidate executed: `0 / 0 / 0`
- Candidate→ROS and ROS→Gazebo maximum error: `0 / 0`
- ROS/Core replay maximum error: `0`
- Zero Guard and Safe Actuation Gate: passed
- 200 ms deadline watchdog: passed
- Full-horizon Exact Geometry recheck: enabled and validated
- Stage 09C safe nominal recovery: enabled and validated
- Zero-stop: passed
- Residual containers/processes: `0 / 0`

## Performance

| Evidence | P95 |
|---|---:|
| Planner Runtime offline | `17.434 ms` |
| Stage 09C CPU offline | `151.30 ms` |
| Stage 09C runtime | `57.47 ms` |
| human_path_center P1 | `175.42 ms` |
| human_path_center P2 | `181.46 ms` |
| vehicle_path P2 closed loop | `41.37 ms` |
| semantic_infeasible historical failure path | `216.923 ms` |

The `semantic_infeasible` failure path is `KNOWN_FAILURE_PATH_LATENCY_LIMITATION`. Its results are command-ineligible, captured by the deadline watchdog, labelled `DIAGNOSTIC_ONLY`, and cannot enter `/cmd_vel` or Gazebo. Stale and backlog counts remained zero. The local D3A diagnostic rerun measured `252.047 ms`; containment remained unchanged.

## Runtime images

- Gazebo: local byte-identical Stage 11B image `sha256:99de6309…`.
- Bridge: local functionally equivalent rebuild `sha256:69ec4a1e…`.
- Planner: local functionally equivalent CPU-only rebuild `sha256:450a6030…`.

No GPU was used. No Docker image was modified during final evaluation.

## Minimal regression

Fast regression passed: geometry 19/19, Planner including Stage 09C 51/51, semantic 16/16, evaluation 2/2, C2 watchdog 6/6, D3A 19/19, and final-evaluation contracts 14/14. All 594 JSON files and 16,397 rows across 201 JSONL files parsed. Compileall and `git diff --check` passed.

## Scope and limitations

This stage validates integration and runtime safety behavior under the tested contracts. It does not validate robot-obstacle navigation, Oracle semantic navigation success, semantic nonzero goal progress, predicted RGB perception, future dynamic-target prediction, or formal safety. Full limitations are retained in `known_limitations.md`.
