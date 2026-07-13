# Known Limitations

- OGRE2 render-engine discovery fails in the current Harmonic container, so
  runtime LiDAR and camera publication are not validated.
- The short DiffDrive command sequence was not sent because the sensor-system
  crash triggered the immediate stop rule; motion direction and physical
  stability remain runtime-unvalidated.
- Only `empty_world` was attempted. The other eleven worlds remain unrun.
- Stage 11B remains `BLOCKED_GAZEBO_PLUGIN`; Stage 11C is not authorized.
