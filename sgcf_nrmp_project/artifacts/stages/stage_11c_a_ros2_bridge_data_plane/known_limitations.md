# Known limitations

- The original Stage 11B-N local image object `99de6309...` was no longer available. The Gate used the retained Stage 11B-F HLMS image after matching Gazebo 8.14.0, SDFormat 14.9.0, gz-rendering 8.2.3, OGRE2 / HLMS resources, and the frozen `empty_world` hash. This is functional equivalence, not a byte-identical image claim.
- The bridge image is runtime-only and does not contain `colcon`; the custom wrapper package was not installed in the image. The authoritative tested path is `ros2 run ros_gz_bridge parameter_bridge` with explicit mappings.
- Only one-message data-plane samples and one zero-Twist command were used. No nonzero open-loop command or closed-loop planner was executed.
- No Stage 10 perception, PointPainting, Semantic Margin, Nav2, RViz, or Planner was started.
