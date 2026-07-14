# Known limitations

- Only the four authorized targeted worlds were run; the full 12-world Stage 11B matrix remains to be rerun.
- `human_path_side` retains the Stage 09B Planner limitations: P0 geometry recheck rejection and P1/P2 OSQP maximum-iteration termination.
- Stage 10 remains blocked and was not loaded.
- Visibility isolation is renderer-based; exact geometry continues to consume all runtime LiDAR points without data-layer self-cropping.
