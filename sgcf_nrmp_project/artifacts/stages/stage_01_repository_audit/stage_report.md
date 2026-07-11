# Stage 01 report

## Status

COMPLETED

## Goal

Freeze official NeuPAN commit `579e7af` as the read-only algorithm baseline,
isolate acknowledged erroneous DeepSeek changes, revise the technical plan and
create the independent SGCF-NRMP package skeleton without starting stage 02.

## Completed

- Verified the full baseline commit and tree hashes.
- Audited current protected paths and recorded known contamination without repair.
- Updated the plan for observable/world clearance, distance-only first version,
  autograd gradients, delayed gradient head, SCP trust region, geometry recheck,
  false-safe rate and no first-version motion-prediction claim.
- Fixed the stage-start document path.
- Created an importable independent package, audit tools, documentation index,
  copying notice and reproducibility lock.

## Tests

- Standard-library import test: 1 passed.
- Direct package import/version output: `0.1.0.dev0`.
- Python compileall: passed.
- Git whitespace/error check: passed.
- Baseline object and geometry-only ObsPointNet check: passed.

`pytest` is not installed, so no network installation was attempted; the same
test was run with `unittest`. This is recorded as an environment fact, not hidden.

## Visible results

- `sgcf_nrmp_project/docs/repo_audit.md`
- `sgcf_nrmp_project/docs/environment_report.md`
- `sgcf_nrmp_project/docs/project_tree.txt`
- `sgcf_nrmp_project/docs/version_lock.json`
- this stage report and logs

## Performance metrics

Not applicable to the stage 01 skeleton. No model, dataset or planner exists yet.

## Remaining issues

- The current protected working tree remains intentionally contaminated relative
  to `579e7af`; later work must read baseline sources from the fixed Git object.
- `neupan_ros` has pre-existing local changes.
- `neupan_ros2` nested Git ownership prevents a nested status query.
- pytest is absent; install only when explicitly authorized or already available.

## Upstream protection

No stage 01 action modified `neupan/`, `neupan_ros/`, `neupan_ros2/`, `example/`
or `docker/`. Pre- and post-stage protected status both report only the same
pre-existing `neupan_ros` nested change.

## Next stage

Stage 02: procedural 2D scenes, LiDAR simulation and clearance-label
visualization. Stage 02 has not been started.

## Post-stage layout migration

After stage 02 acceptance, the user authorized consolidation under the single
`sgcf_nrmp_project/` root. Paths above reflect the migrated locations; the stage
01 implementation and test results were not otherwise changed.
