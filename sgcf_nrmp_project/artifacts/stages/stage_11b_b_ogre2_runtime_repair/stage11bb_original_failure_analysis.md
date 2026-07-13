# Original OGRE2 Failure Analysis

The Stage 11B-A stderr is preserved verbatim at
`logs/original_empty_world_stderr.txt`. No OGRE log was created before the
crash, so `logs/original_ogre2.log` contains the required
`LOG_NOT_CREATED_BEFORE_CRASH` marker.

The original image contained the ABI-compatible OGRE2 engine plugin and all
`ldd` dependencies. However, its environment omitted the Gazebo Sim 8 variable
`GZ_SIM_RENDER_ENGINE_PATH`, whose name and purpose are printed by
`gz sim --help`. The Sensors thread requested engine `ogre2`, failed to load
logical plugin `gz-rendering-ogre2`, and segfaulted in
`gz::sim::systems::SensorsPrivate::RenderThread` during `RenderUtil::Init`.

No missing EGL/OpenGL dependency was reported and no OGRE log existed, so the
initial failure was classified as plugin discovery rather than backend
initialization.
