# Robot Footprint Comparison

The SDF collision named `planner_footprint_collision` is a `0.8 × 0.5 × 0.2 m`
box centred on `base_link`. Its ground projection is exactly the Stage 05
rectangle (`length=0.8 m`, `width=0.5 m`) centred at `base_footprint` x/y.

No wheel collision geometry is added outside the body envelope.
No collision shrinkage, safety-distance change, or alternate footprint is used.
The static validator reports zero length and width error.

The future differential-drive kinematic contract records `0.5 m` wheel
separation, `0.1 m` nominal wheel radius, Stage 05 limits (`1.0 m/s`,
`1.5 rad/s`), and the frozen `0.2 s` control period. Stage 11A does not add or
run a drive plugin; those values require runtime validation in Stage 11B.
