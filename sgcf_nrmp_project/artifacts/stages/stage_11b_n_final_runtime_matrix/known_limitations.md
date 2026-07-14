# Known limitations

- The intentional initial-collision contact response moves the dynamic robot approximately 2.41 mm before pose capture; the external obstacle pose and collision classification remain correct.
- Headless X11 / DRM warnings remain nonfatal when OGRE2 falls back to a working EGL device.
- Startup latency has only three samples per selected scene.
- Stage 09B `human_path_side` Planner limitations remain unresolved.
- Oracle semantics are simulation-only ground truth.
