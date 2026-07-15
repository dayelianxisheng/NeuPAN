# Stage 12 ROS 2 Offline Nodes and Replay Report

## Outcome

Stage 12 passed with the upstream limitations listed below. Six isolated ROS 2 Python packages now provide the offline message contracts, fusion, Planner wrapper, visualization, evaluation diagnostics, deterministic synthetic publisher, and launch description. The runtime used the local immutable Planner/ROS image `sha256:450a603029c87e18550c64d19672ccb72b66395f74c254d0b098fbf8f7deb7cc` on CPU.

No Gazebo process, Stage 10 inference, predicted semantic checkpoint, Planner actuation path, or `/cmd_vel` publisher was used. Candidate commands were published only on `/sgcf/planner_candidate_cmd_vel` for offline inspection.

## Data and scenarios

The deterministic publisher consumed saved Stage 11C snapshots for:

- `single_static_obstacle` in P0;
- `vehicle_path` in paired P0/P2 with Oracle ground-truth semantics;
- `rgb_dropout_contract` in paired P0/P2;
- `outdated_rgb_contract` in paired P0/P2.

Message timestamps came from deterministic simulation time. The maximum ordinary scan/image or scan/odom skew was 0.05 s, matching the Stage 11A synchronization contract. The outdated-image skew was deliberately 0.100001 s. All timestamp streams had zero negative jumps. TF provided dynamic `odom → base_link` and static sensor transforms without duplicate parents.

## Planner, geometry, and fallback evidence

Each scene completed 20 Planner evaluations. Direct ROS/Core replay maximum error was `0`, and the Stage 11C current-state Exact Geometry query maximum error was `0` (threshold `1e-6`). Robot self-return count was zero in every scene, there was no sustained queue growth, and all values were finite.

For both explicit RGB failures, P2 and synchronized P0 had zero maximum error for `d_geo`, `g_geo`, and candidate control. Reliability and semantic margin were zero. The explicit Planner status remains distinct from P0 by design so the failure cause is observable.

Steady-state P95 evaluation latency was 57.01 ms (single static), 33.04 ms (vehicle), 59.82 ms (dropout), and 58.96 ms (outdated). One initialization-path deadline miss occurred in vehicle and dropout respectively; results remained offline-only and no actuation topic existed.

## Self-contained replay

The Stage 12 bag is an SQLite3 container of ROS 2 CDR messages because the immutable local runtime images do not include the `ros2 bag` CLI and Docker modification was prohibited. It contains 663 messages, including clock, scan, image, CameraInfo, odometry, TF, fusion, Planner candidate/status/diagnostics, local plan, markers, and diagnostic arrays.

Two independent ROS publications of that bag produced identical message counts and identical canonical logical-message hashes on every topic. Canonical hashes intentionally exclude non-field CDR alignment padding.

## Validation

- Stage 12 contract unittest: 5 passed.
- Geometry, Planner, evaluation, Stage 11C-C2, and Stage 11C-D3A regression: 97 passed.
- Six package `setup.py build` checks passed in isolated temporary directories.
- JSON parse, `compileall`, and `git diff --check` passed.
- All Stage 12 containers and processes were removed.

The existing immutable images do not provide the `colcon` CLI, so package build validation used setuptools plus actual sustained ROS runtime execution. No package installation or image rebuild was performed.
