# Known Limitations

1. Stage 10 predicted RGB semantics remain blocked and were not loaded.
2. Semantic input in this stage is Oracle ground truth for simulation/offline interface testing only.
3. The sensor stream is deterministic synthetic ROS publication derived from Stage 11C snapshots, not a new Gazebo run or real robot recording.
4. The self-contained SQLite CDR recorder is compatible with the Stage 12 replayer but is not a standard `rosbag2` directory; the immutable runtime images lack the `ros2 bag` CLI and could not be modified.
5. Existing Planner completeness and semantic navigation limitations from Stage 11C remain unchanged.
6. The first Planner evaluation can exceed the 200 ms deadline; Stage 12 is offline and exposes candidates only, never `/cmd_vel`.
7. This work does not constitute a formal safety guarantee or dynamic-target prediction validation.
