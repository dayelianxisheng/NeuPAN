# Stage 11C-C1R Report

Stage 11C-C1R stopped at the local-base probe hard gate.

## Decision

`BLOCKED_LOCAL_BASE_IMAGE_RESOLUTION`

The authoritative local base object `sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862` exists, is `linux/amd64`, and its eight RootFS layers matched the bootstrap alias and probe image exactly. The authorized alias is `sgcf-local/ros2-bridge-base:sha256-c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862` and is only a `NON_AUTHORITATIVE_BOOTSTRAP_ALIAS`.

The probe build itself exited successfully and did not pull base layers or return HTTP 403. However, its log records both a Dockerfile frontend access to `docker.io/docker/dockerfile:1` and a canonical `docker.io/sgcf-local/...` metadata lookup. This violates the explicit zero-network / no `docker.io/sgcf-local` lookup gate. Therefore the derived Planner image was not built and no downstream Planner, Torch, OSQP, ROS coexistence, Gazebo, bridge, world, or `/cmd_vel` gate was run.

The parent Stage 11C-C1 `BLOCKED_IMAGE_BUILD` report remains unchanged.
