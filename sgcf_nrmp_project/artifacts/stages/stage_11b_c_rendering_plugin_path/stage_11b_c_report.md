# Stage 11B-C Official Plugin-path Correction Report

## Decision

```text
BLOCKED_GZ_RENDERING_PLUGIN_PATH
```

## Loader audit

The user-supplied official gz-rendering8 source audit confirms that
`RenderEngineManager` reads `GZ_RENDERING_PLUGIN_PATH`, requests logical library
`gz-rendering-ogre2`, and retains SDF engine identifier `ogre2`.
`GZ_SIM_RENDER_ENGINE_PATH` was not accepted as the Stage 11B-C loader basis.

## Blocking package evidence

A reliable search over files and symlinks under `/usr`, `/lib`, and `/opt`
found no `libgz-rendering-ogre2.so`. The installed Debian package
`libgz-rendering8-ogre2 8.2.3-1~jammy` provides only:

```text
/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering8-ogre2.so.8
/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering8-ogre2.so.8.2.3
```

Those versioned files identify a likely engine-plugin directory, but it is not
a directory containing the exact logical filename required by this stage.
Consequently the mandated Docker build assertions cannot pass.

## Stop boundary

No Dockerfile was changed, no new image was built, and no `empty_world` runtime
re-gate occurred. No package, library copy, rename, or symlink was used. The
audit container was stopped and no Gazebo process remains. Gazebo assets,
robot footprint, sensors, Planner, Stage 10 and all remaining worlds were
untouched.

Human direction is required on how the official Harmonic Debian package is
expected to supply the unversioned logical plugin filename without violating
the explicit no-install/no-symlink constraints. Stage 11B cannot resume and
Stage 11C must not begin.
