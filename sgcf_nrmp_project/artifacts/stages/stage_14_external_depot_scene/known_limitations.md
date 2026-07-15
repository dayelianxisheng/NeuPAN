# Known Limitations

- `LICENSE_UNKNOWN_LOCAL_TEST_ONLY`: the vendor archive and extracted files must not be committed or redistributed.
- The vendor Depot package is a model, not a complete world.
- Its building mesh is visual-only; collision is limited to a ground plane.
- Legacy Ignition joint-controller names rely on Gazebo Harmonic compatibility aliases.
- Ogre material scripts are ignored; PBR material paths are used.
- The static projection target belongs to the overlay, not the vendor asset.
- No Planner, Stage 10 perception, or semantic navigation was evaluated.
