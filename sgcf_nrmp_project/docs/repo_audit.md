# Repository audit — stage 01

## Decision

- Official read-only algorithm baseline: `579e7afa239cd7ff61f7f63fbd4aaaecbb136d3b`
- Baseline tree: `e37d357483d2e4df7631fbf03decd928b9cb0e5c`
- Current working HEAD: `54a291c7f68c7fe5085ff1abac7536e903dfadb6`
- `54a291c` is an acknowledged erroneous DeepSeek change and is excluded from all
  implementation, compatibility and experimental comparisons.

The baseline object exists locally and is readable. `git show 579e7af:<path>`
confirms that the baseline `ObsPointNet` accepts only two-dimensional geometry
and has no class embedding.

## Contamination found in the current tree

The current `neupan/` tree contains `class_embed`, `point_class`, `num_classes`
and Semantic-DUNE propagation across `neupan.py`, `pan.py`, `dune.py`,
`obs_point_net.py` and `dune_train.py`. These files were recorded only; they were
not restored, modified, imported or used as a baseline.

The current repository also differs from `579e7af` in later examples, Docker
files, `neupan_ros` and `neupan_ros2`. These later additions are outside the new
independent package and are not treated as baseline code.

## Pre-existing working-tree state

- `neupan_ros` nested repository: `src/neupan_core.py` modified and
  `src/neupan_core.py.bak` untracked.
- `neupan_ros2` nested Git status cannot be queried because Git reports dubious
  ownership. No global safe-directory setting was changed.
- Two pre-existing documents are staged as deleted.

No recovery, reset, checkout, clean, commit or push was performed.

## Isolation rule

All new implementation is restricted to the single project root
`sgcf_nrmp_project/`: Python code under `core/`, future ROS 2 work under
`ros2_ws/`, Gazebo under `gazebo/`, deployment under `deploy/`, and supporting
documents/tools/artifacts in their named subdirectories. Protected directories
remain read-only. Later source references must resolve against `579e7af`, not
HEAD.
