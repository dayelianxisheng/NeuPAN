# Stage 02 report

## Status

COMPLETED

## 1. Completed work

- Implemented deterministic static 2D scenes with discretized circles,
  axis-aligned/rotated rectangles, convex polygons, walls and corridors.
- Implemented convex polygon robot footprints, default YAML rectangle geometry
  and explicit `T_target_source` SE(2) transforms.
- Implemented nearest-visible-surface LiDAR ray casting with FOV, beam count,
  min/max range, Gaussian range noise, dropout and explicit RNG.
- Implemented footprint-aware observable/world clearance, collision labels and
  finite-difference x/y/yaw gradient references with discontinuity validity.
- Generated three required scene, scan, comparison and gradient visual sets.

No model training, dataset generation, RGB, planner, ROS or Gazebo work exists.

## 2. Label definitions

`observable_clearance` is the distance from the complete query footprint to the
valid hit points in the current simulated scan. Occluded, out-of-FOV,
out-of-range and dropped surfaces do not enter it. With no hit, it returns the
configured truncation and `observable_available=false`.

`world_clearance` is the distance from the complete query footprint to the union
of all world obstacle polygons. Intersection gives `world_clearance=0` and
`world_collision=true`. It is an evaluation/oracle value, not the default future
single-frame LiDAR supervision target.

`observable_collision` only detects footprint intersection with an observed hit
point, so it can be false while an unseen obstacle causes `world_collision`.

## 3. Files

The complete list is in `files_changed.txt`. Source is confined to
`sgcf_nrmp_project/core/`; reports are confined to
`sgcf_nrmp_project/artifacts/stages/stage_02_procedural_geometry/` and project
documentation to `sgcf_nrmp_project/docs/`.

## 4. Test commands and results

The main command was:

```text
PYTHONPATH=sgcf_nrmp_project/core/src python -m unittest discover -s sgcf_nrmp_project/core/tests -v
```

Result: 16 passed, 0 failed, 0 skipped. Compileall and `git diff --check` passed.
All 12 PNG hashes were identical after a deterministic rerun.

Known circle clearance error was 0.0 m at the reported precision. The wall
translation gradient was `[-1.0, 0.0]` within floating-point tolerance.

## 5. Visible results

- `scene_01_*`: single-circle analytical case
- `scene_02_*`: front-wall occlusion plus rear out-of-FOV obstacle
- `scene_03_*`: narrow corridor with an internal obstacle
- `known_case_validation.json`
- `random_scene_statistics.json`

Each comparison image shows observable clearance, world clearance and absolute
difference. Gradient plots show the observable heatmap, valid arrows, invalid
regions when sampled, and a rotated footprint example.

## 6. Validation and performance

- 1000 random scenes and 3000 query labels completed with 0 NaN/Inf.
- Mean observable/world absolute difference: 0.4615455 m.
- Maximum observed difference: 6.6188048 m.
- Validation run: 2.72 s, maximum RSS 38656 KiB.
- Three-scene visualization run: 7.41 s, maximum RSS 125980 KiB.

These are development-script measurements, not deployment benchmarks.

## 7. Observable/world difference

Scene 02 visibly demonstrates the intended partial-observation gap: the front
wall hides the farther rectangle and the rear circle is outside the forward FOV.
Its grid maximum absolute difference is 3.825 m. The implementation never uses
the hidden world geometry to fill an observable label.

## 8. Known limitations

- Observable geometry is represented by discrete beam hit points, not continuous
  reconstructed visible surface segments; resolution therefore affects labels.
- Circles are polygonal approximations.
- The world is static; there is no obstacle velocity or trajectory prediction.
- A single `gradient_valid` flag covers all three components. It is false if any
  central pair crosses collision state or shows a strong one-sided slope jump.
- Empty-world `world_clearance` uses the same configured truncation because an
  infinite numeric label is unsuitable for grids and later storage.

## 9. Upstream increment check

Protected status was ` m neupan_ros` before and after this stage. This is the
same pre-existing nested change. Stage 02 introduced no protected-path change.

## 10. Next-stage suggestion

Stage 03 would convert these APIs into a versioned, sharded geometry dataset with
scene-level splits and quality reports. It has not been started.

## Post-stage layout migration

After acceptance, all stage 01/02 files were migrated without algorithm changes
into the single `sgcf_nrmp_project/` root. Tests and visual reproducibility were
rerun from the new paths. No legacy root-level `sgcf_nrmp*` directory remains.
