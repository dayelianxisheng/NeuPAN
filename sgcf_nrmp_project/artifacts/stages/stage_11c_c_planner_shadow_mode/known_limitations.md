# Known limitations

- The Gazebo runtime is functionally equivalent to the historical Stage 11B-N image, not binary-identical to it.
- Oracle semantics are simulation ground truth and are not Stage 10 prediction.
- `semantic_infeasible` steady-state Planner P95 is 216.923 ms, above the 200 ms hard limit. The formal failure path synchronously constructs and evaluates a geometry-only comparison planner. No Core modification was authorized.
- Known nonfatal headless EGL / DRM warnings remain as documented in prior stages.
