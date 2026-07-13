# Modern Gazebo Harmonic Headless Environment

This isolated image provides the Gazebo Harmonic headless CLI, transport,
system plugins, DART physics engine, Ogre2 sensor runtime, and SDFormat utility
required by Stage 11B. It intentionally omits the Harmonic development and GUI
metapackages. It does not install or launch the SGCF-NRMP Planner, Stage 10
model, ROS bridge, or Gazebo GUI.

Build and validate:

```bash
./docker/gazebo_harmonic/container.sh build
./docker/gazebo_harmonic/container.sh create
./docker/gazebo_harmonic/container.sh check
```

Expected core versions for the current image are Gazebo Sim `8.x` (Harmonic)
and SDFormat `14.x`. The base `gz --versions` command may return 255 after
printing generic help in Gazebo Tools 2; the check therefore validates the
registered subcommands and their component-specific versions.

Open a diagnostic shell when required:

```bash
./docker/gazebo_harmonic/container.sh shell
```

The repository is mounted at `/workspace`. Gazebo resources are resolved from
`/workspace/sgcf_nrmp_project/gazebo/models` and
`/workspace/sgcf_nrmp_project/gazebo`. The container uses host networking for
Gazebo Transport and runs with offscreen rendering defaults. If `/dev/dri`
exists, it is passed through for headless rendering.

The packaged Harmonic DART engine is resolved through
`GZ_SIM_PHYSICS_ENGINE_PATH=/usr/lib/x86_64-linux-gnu/gz-physics-7/engine-plugins`.
The image adds the unversioned discovery symlink omitted by the runtime-only
Ubuntu package, including the logical engine name requested by Gazebo Sim; both
point to the packaged ABI-compatible `.so.7` library.

Stage 11B must still begin with its environment, version, SDF, plugin, and
resource audits. Creating this container does not itself validate any runtime
contract.

## OGRE2 diagnostic image

The runtime package installs its engine plugin under
`/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins`. Gazebo Sim 8 exposes
`GZ_SIM_RENDER_ENGINE_PATH` as the supported discovery variable, so the image
sets that exact packaged path. No shared library is copied and no ABI-bypass
symlink is created for OGRE2.

Keep the original baseline image and build an independent diagnostic image:

```bash
./docker/gazebo_harmonic/container.sh build-ogre2
./docker/gazebo_harmonic/container.sh create-ogre2
./docker/gazebo_harmonic/container.sh check-ogre2
./docker/gazebo_harmonic/container.sh stop-ogre2
```

The diagnostic image is tagged `sgcf-gazebo-harmonic:ogre2-fix` and uses the
container name `sgcf_gz_harmonic_ogre2_fix`.

The earlier Stage 11B-B assumption that `GZ_SIM_RENDER_ENGINE_PATH` controls
gz-rendering8 plugin discovery was disproved by the loader audit. Current
images use `GZ_RENDERING_PLUGIN_PATH`; the old image is retained only as
historical evidence.

## ABI-locked packaging compatibility image

Jammy's `libgz-rendering8-ogre2 8.2.3-1~jammy` package omits the unversioned
logical loader alias. The explicitly authorized compatibility image creates
exactly one local shim in the packaged engine-plugin directory:

```text
libgz-rendering-ogre2.so -> /usr/lib/x86_64-linux-gnu/libgz-rendering8-ogre2.so.8
```

The target version and SHA256 are asserted during the build. The shim is marked
`LOCAL_PACKAGING_COMPATIBILITY_SHIM`, is not Debian-owned, and is locked to
gz-rendering ABI 8. Build and inspect it independently:

```bash
./docker/gazebo_harmonic/container.sh build-abi8-alias
./docker/gazebo_harmonic/container.sh create-abi8-alias
./docker/gazebo_harmonic/container.sh check-abi8-alias
./docker/gazebo_harmonic/container.sh stop-abi8-alias
```

## Exact-version HLMS media image

Stage 11B-F uses the exact OSRF archive
`libgz-rendering8-ogre2-dev_8.2.3-1~jammy_amd64.deb`. The archive supplies the
Debian-owned logical plugin alias plus the Unlit, PBS, Terra, Gazebo custom,
GPU-rays and camera rendering resources missing from the runtime-only image.
The package URL, identity and SHA256 are asserted during the build.

The fixed directory `2.0/scripts/Compositors` is not used as a package gate:
gz-rendering8 does not contain that exact reference, while the package provides
the actual GPU-rays, camera, lens-flare, VCT and Terra compositor files in their
versioned runtime locations.

```bash
./docker/gazebo_harmonic/container.sh build-hlms-media
./docker/gazebo_harmonic/container.sh create-hlms-media
./docker/gazebo_harmonic/container.sh check-hlms-media
./docker/gazebo_harmonic/container.sh stop-hlms-media
```

The image is tagged `sgcf-gazebo-harmonic:hlms-media-fix` and uses container
name `sgcf_gz_harmonic_hlms_media_fix`. This image does not by itself complete
Stage 11B; its only authorized runtime gate is `empty_world`.
