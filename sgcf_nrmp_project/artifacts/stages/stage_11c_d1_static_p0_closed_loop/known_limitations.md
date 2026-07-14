# Known limitations

- The formal empty-world P0 first command is approximately 0.240 m/s, above the Stage 11C-D1 additional 0.15 m/s hard limit. The Safe Gate rejects rather than clamps it.
- The formal single-static-obstacle P0 result is `REJECTED_BY_GEOMETRY_CHECK` and ineligible.
- The Gazebo runtime is functionally equivalent rather than binary-identical to the historical Stage 11B-N image.
