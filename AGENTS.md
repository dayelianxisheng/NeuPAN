# Repository Guidelines

## Project Structure & Module Organization

`neupan/` is the primary Python package. Its planner entry point is `neupan/neupan.py`; optimization and learning components live in `neupan/blocks/`, robot models in `neupan/robot/`, and shared helpers in `neupan/util/`. Runnable IR-SIM scenarios and their YAML configuration are under `example/`. Deployment notes and known issues belong in `docs/`, while Docker support is in `docker/` and the root `Dockerfile`.

`sgcf_nrmp_project/core/` is a separate research package using a `src/sgcf_nrmp/` layout. Keep its implementation, configs, scripts, and `tests/` isolated from the upstream NeuPAN package. Generated datasets, checkpoints, and logs belong under `sgcf_nrmp_project/artifacts/`, not in source directories.

## Build, Test, and Development Commands

- `python -m pip install -e .` installs NeuPAN for local development.
- `python -m pip install -e ".[irsim]"` also installs the simulator dependency.
- `cd example && python run_exp.py -e corridor -d diff` runs a representative differential-drive scenario.
- `python -m pip install -e "sgcf_nrmp_project/core[dev]"` installs the research package and pytest.
- `python -m pytest sgcf_nrmp_project/core/tests` runs its full test suite from the repository root.
- `PYTHONPATH=sgcf_nrmp_project/core/src python sgcf_nrmp_project/core/scripts/validate_geometry_dataset.py sgcf_nrmp_project/artifacts/datasets/geometry_v1` validates a generated dataset.

Use Python 3.10 for the research package. Preserve dependency pins in `pyproject.toml`, especially NumPy, SciPy, CVXPY-related solvers, and Torch.

## Coding Style & Naming Conventions

Follow existing Python conventions: four-space indentation, `snake_case` functions and modules, `PascalCase` classes, and uppercase constants. Add type hints to new public APIs and concise docstrings where behavior or array shapes are not obvious. Keep imports package-relative within a package. YAML files use lowercase keys and two-space indentation. No formatter is currently enforced, so match neighboring code and keep changes focused.

## Testing Guidelines

Tests use pytest and follow `test_*.py` naming. Mirror source areas in test subdirectories (for example, `tests/geometry/`). Add deterministic tests for geometry, planner constraints, dataset schemas, and bug fixes; seed randomized fixtures. Do not require ROS, a display, or GPU for the default suite.

## Commit & Pull Request Guidelines

Recent history favors short imperative subjects with Conventional Commit prefixes such as `fix:`, `feat:`, and `docs:`. Keep each commit scoped to one concern. Pull requests should explain the motivation, list validation commands, link relevant issues, and call out config or dependency changes. Include plots, screenshots, or short recordings when navigation behavior or visualization output changes.
