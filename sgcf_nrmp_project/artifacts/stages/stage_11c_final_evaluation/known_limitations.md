# Stage 11C Known Limitations

1. Stage 10 predicted RGB semantics were not integrated, started, or evaluated.
2. Gazebo semantic validation used simulation-only Oracle Ground Truth.
3. `vehicle_path` safely executed P2 nonzero commands, but goal distance increased by `0.31891 m`; navigation progress was not demonstrated.
4. No current semantic scenario proves semantic navigation success.
5. `robot_obstacle` is safely rejected and retains a Planner feasible-trajectory search completeness limitation.
6. `human_path_center` and `human_path_side` are rejected under the frozen formal semantic safety constraints.
7. The historical `semantic_infeasible` failure-path P95 is approximately `216.923 ms` (the local D3A diagnostic run was `252.047 ms`). The 200 ms watchdog marks these results `DIAGNOSTIC_ONLY`; none entered `/cmd_vel` or Gazebo.
8. The local Bridge and Planner images are functionally equivalent rebuilds, not byte-identical copies of the historical images. The local Gazebo image is the byte-identical Stage 11B image.
9. These empirical tests do not provide a formal safety guarantee.
10. Validation primarily covers static or instantaneous environments and does not include future dynamic-target prediction.

Additional inherited nonfatal limitations include headless X11/DRM warnings and small-sample runtime timing variation. They did not invalidate the measured contracts.
