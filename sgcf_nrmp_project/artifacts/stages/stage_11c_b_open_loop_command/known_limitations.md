# Known Limitations

- The Gazebo image is the Stage 11C-A functionally equivalent baseline, not the
  unavailable historical Stage 11B-N binary image.
- Each nonzero command type was exercised once. Latency values are descriptive;
  no P95 is claimed.
- Gazebo Twist messages do not carry a simulation timestamp. The bridge value and
  sign were captured directly, but ROS-to-Gazebo transport latency cannot be
  separated precisely from this capture.
- Known nonfatal headless X11 / DRM warnings remain inherited from Stage 11B-F.
- The run used only `empty_world` and open-loop commands. It did not exercise a
  planner, Stage 10, PointPainting, Semantic Margin, Nav2, TF publication, or an
  obstacle scenario.
- A preflight node-construction attempt failed before commands were published due
  to duplicate `use_sim_time` declaration. The test node was corrected before the
  one completed formal sequence.
- The frozen bridge image does not contain `colcon`, and package installation was
  prohibited. The `ament_python` source package passed an in-container setuptools
  build in `/tmp`; no dependency or image change was made.
