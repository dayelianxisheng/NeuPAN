# Stage 08A Candidate Search Definition

All deployable candidate generators consume only projected UV, projection validity, the oracle semantic probability map, image age/dropout state, and image bounds. Their APIs do not accept GT point class, GT instance, true calibration perturbation, reliability GT, margin GT, world geometry, or hidden instances. GT class/instance is used only by the offline coverage evaluator.

Compared patterns:

- C0: center pixel, 1 candidate.
- C1: dense local 3×3, 9 candidates.
- C2: dense local 5×5, 25 candidates.
- C3: radius-8 sparse 5×5 grid at offsets `{-8,-4,0,4,8}`, 25 candidates.
- C4: radius-16 sparse 5×5 grid at offsets `{-16,-8,0,8,16}`, 25 candidates.
- C5: radius-24 sparse 7×7 grid at offsets `{-24,-16,-8,0,8,16,24}`, 49 candidates.
- C6: radius-24/stride-8 coarse search, top-4 selected from online semantic confidence, then four 3×3 refinements, 36 candidates.
- C7: unique 3×3 grids at radii 2/8/16/24, at most 33 sparse candidates.

Cross, ring, and fixed-seed random offset constructors are available for later audit but were not promoted after the mandatory 3 cm + 3° gate failed. Oracle depth was not used by any deployable method.
