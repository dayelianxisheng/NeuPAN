# Known Limitations

- The local ABI-8 alias is Docker-owned compatibility infrastructure, not an
  official Debian package file.
- The alias resolves and loads, but required OGRE2 HLMS shader media is absent.
- The Sensors thread segfaults after backend initialization fails.
- LiDAR, camera, odometry sampling and DiffDrive motion were not validated.
- Only `empty_world` was run; Stage 11B remains blocked.
