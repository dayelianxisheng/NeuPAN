#!/usr/bin/env python3
"""Write a deterministic stage-01 environment and baseline lock."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

BASELINE = "579e7afa239cd7ff61f7f63fbd4aaaecbb136d3b"
PACKAGES = ("torch", "numpy", "scipy", "cvxpy", "cvxpylayers", "osqp", "shapely", "PyYAML")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sgcf_nrmp_project/docs/version_lock.json")
    payload = {
        "baseline_commit": git("rev-parse", BASELINE),
        "baseline_tree": git("rev-parse", f"{BASELINE}^{{tree}}"),
        "working_head": git("rev-parse", "HEAD"),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "packages": {},
    }
    for name in PACKAGES:
        try:
            payload["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            payload["packages"][name] = None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
