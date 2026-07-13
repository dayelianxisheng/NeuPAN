# Installation Validation

Validated on 2026-07-13.

```text
image: sgcf-gazebo-harmonic:local
image id: add3df817107
image size: 1.32 GB
container: sgcf_gz_harmonic
Gazebo Sim: 8.14.0 (Harmonic)
SDFormat: 14.9.0
```

Registered Gazebo commands include `sim`, `topic`, `service`, `model`, `sdf`,
`log`, `msg`, `param`, and `gui`. The environment is configured for server-only
offscreen operation; the GUI command is installed as a transitive runtime
component but was not started.

The Stage 11A `empty_world.sdf` completed a 20-iteration server-only run:

```bash
gz sim -s -r --iterations 20 \
  /workspace/sgcf_nrmp_project/gazebo/worlds/empty_world.sdf
```

The command exited with code 0 and no SDF, physics-plugin, or server error.
There was no residual `gz` process after completion.

This is an installation smoke test only. It does not claim completion of Stage
11B world-matrix, sensor, frame, clearance, diff-drive, or timing validation.

## Stage 11B-B repair definition

The original container contained the ABI-compatible OGRE2 plugin and all of
its `ldd` dependencies, but did not set Gazebo Sim 8's documented
`GZ_SIM_RENDER_ENGINE_PATH`. The reproducible repair adds only:

```text
GZ_SIM_RENDER_ENGINE_PATH=/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins
```

No additional package, host library, source build, or OGRE symlink is used.
Runtime validation belongs to the Stage 11B-B artifact report and is not
claimed by this installation note.

## Local ABI-8 compatibility shim

Stage 11B-E explicitly authorizes one Docker-owned packaging shim because the
Jammy runtime package lacks the logical alias expected by the gz-rendering8
loader. It is not described as Debian-owned:

```text
/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering-ogre2.so
  -> /usr/lib/x86_64-linux-gnu/libgz-rendering8-ogre2.so.8
```

The image uses `GZ_RENDERING_PLUGIN_PATH`, installs no additional package, and
records the shim contract under `/usr/local/share/sgcf/compat/`.

## Stage 11B-F exact HLMS package

The Stage 11B-F image installs only the audited exact archive and dependencies:

```text
libgz-rendering8-ogre2-dev 8.2.3-1~jammy amd64
SHA256 f7963e5c70dc933d5c3e402de6491a28b22e7229ce918bec69f0fc7a69f1df6b
```

It is built from the alias-free `runtime-base`; the official package owns both
`libgz-rendering-ogre2.so` and the OGRE2 media tree. The runtime resource root
is `/usr/share/gz/gz-rendering8`. Stage 11B-F runtime results are recorded only
in its artifact report, not inferred from successful image construction.
