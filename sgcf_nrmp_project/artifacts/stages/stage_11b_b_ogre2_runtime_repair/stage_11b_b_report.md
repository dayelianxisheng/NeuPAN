# Stage 11B-B OGRE2 Runtime Diagnosis and Repair Report

## Decision

```text
BLOCKED_OGRE2_PLUGIN_DISCOVERY
```

## Diagnosis

The original image contains `libgz-rendering8-ogre2 8.2.3`, OGRE-Next 2.3.1,
Mesa/EGL/OpenGL runtime libraries, and a valid x86-64 engine-plugin symlink.
`ldd` reports no missing dependency, and Gazebo Sim 8 matches gz-rendering 8.
The original container lacked `GZ_SIM_RENDER_ENGINE_PATH`; `gz sim --help`
documents that variable and the accepted engine identifier `ogre2`.

No original or repaired OGRE log was created before either crash. Marker files
preserve that fact instead of fabricating logs.

## Reproducible repair

An independent image, `sgcf-gazebo-harmonic:ogre2-fix`, was built from the
authorized Dockerfile. It adds only:

```text
GZ_SIM_RENDER_ENGINE_PATH=/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins
```

No package was added, no host library was copied, no source was compiled, and
no OGRE ABI-bypass symlink was created. The original `:local` image remains.

## Single runtime re-gate

The only repaired-image run used server-only headless rendering and explicitly
selected `ogre2`. Static plugin validation passed, but runtime still requested
logical library `gz-rendering-ogre2`, reported it could not find that shared
library, and segfaulted in the Sensors render thread. Only `/odom`, `/tf`,
resource paths and world stats appeared before the crash; simulation clock,
LiDAR and camera publication never became ready.

Because the server failed the sensor gate, no sensor samples or DiffDrive
commands were collected. No second image repair, symlink experiment, SDF edit,
or runtime retry was performed.

## Preservation and cleanup

The Gazebo asset tree hash remains unchanged from the Stage 11B-B entry value.
Planner, Exact Geometry, Semantic Margin, Stage 10 and protected upstream
directories were not modified. The diagnostic container was stopped and the
residual Gazebo process count is zero.

## Required next action

Before another build, a human must approve a specific Harmonic Debian
plugin-name solution backed by package metadata. In particular, review whether
an ABI-compatible logical-name link or loader configuration is officially
required for the runtime-only package. Stage 11B cannot resume and Stage 11C
must not begin.
