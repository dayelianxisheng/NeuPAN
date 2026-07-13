# Stage 11B-E ABI-locked OGRE2 Compatibility Alias Report

## Decision

```text
BLOCKED_HEADLESS_RENDERING_BACKEND
```

## Target and compatibility shim

The audited target is owned by `libgz-rendering8-ogre2:amd64`, version
`8.2.3-1~jammy`, with SONAME `libgz-rendering8-ogre2.so.8`, x86-64 ELF,
SHA256 `c82cba3f...34b24ef`, and zero unresolved `ldd` dependencies. Exactly one
authorized local alias was created in the unique engine-plugin directory and
resolves to that target. It is explicitly disclosed as
`LOCAL_PACKAGING_COMPATIBILITY_SHIM`, `NOT_OWNED_BY_DEBIAN_PACKAGE`, and
`ABI_LOCKED_TO_GZ_RENDERING_8`.

No package was installed, upgraded, downgraded, or removed. No library was
copied or modified. `GZ_RENDERING_PLUGIN_PATH` replaces the previous incorrect
loader variable.

## Single runtime re-gate

The alias fixes the packaging discovery failure. The stderr no longer reports
“couldn't find shared library”; OGRE logs show plugin installation, EGL device
enumeration, and creation of an OpenGL 4.5 context. Initialization then stops at
`Ogre2RenderEngine` because this image lacks:

```text
/usr/share/gz/gz-rendering8/ogre2/src/media/Hlms/Unlit/GLSL
```

The missing shader templates cause render-engine initialization failure and a
subsequent Sensors-thread segmentation fault. This is classified at the first
new failing layer as `BLOCKED_HEADLESS_RENDERING_BACKEND`, proving that the
compatibility alias itself works.

No sensor messages or DiffDrive commands were collected because the server did
not pass the rendering gate. The attempt was not repeated.

## Preservation and cleanup

Only `empty_world` was attempted. Gazebo assets, footprint, sensor contracts,
Planner, Stage 10 and protected algorithms are unchanged. The diagnostic
container was stopped and no Gazebo process remains. Full Stage 11B and Stage
11C remain unauthorized.
