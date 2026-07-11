#!/usr/bin/env python3
"""Validate a geometry_v1 dataset and optionally write the report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sgcf_nrmp.data.datasets.validation import validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--report")
    args = parser.parse_args()
    report = validate_dataset(args.dataset)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        Path(args.report).write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
