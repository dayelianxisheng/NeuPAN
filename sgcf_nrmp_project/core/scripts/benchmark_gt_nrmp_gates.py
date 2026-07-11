#!/usr/bin/env python3
"""Run the two mandatory persistent-QP latency and safety gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import polyline_path
from sgcf_nrmp.types.lidar import LidarConfig


def serializable(result):
    timing = result["timing_samples_ms"]
    metrics = result["metrics"]
    breakdown = {}
    for key, values in timing.items():
        breakdown[key] = {
            "mean": float(np.mean(values)) if values else 0.0,
            "p95": float(np.percentile(values, 95)) if values else 0.0,
            "max": float(max(values, default=0.0)),
            "count": len(values),
        }
    return {"metrics": metrics, "timing_breakdown_per_scp_ms": breakdown}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml")
    parser.add_argument("--output", default="sgcf_nrmp_project/artifacts/stages/stage_05_gt_nrmp_solver/persistent_qp_gate_results.json")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    lidar = LidarConfig(num_beams=181, range_max=8.0)
    cases = {
        "no_obstacle_straight": (
            ProceduralScene([], (-2, -2, 5, 2)), polyline_path([(0, 0), (4, 0)]), 60
        ),
        "single_circle_detour": (
            ProceduralScene([circle_obstacle((1.5, 0), .35)], (-2, -2, 5, 2)),
            polyline_path([(0, 0), (.7, .7), (1.5, 1.), (2.3, .7), (4, 0)]), 80
        ),
    }
    report = {
        "backend": "persistent_cvxpy_parameter_osqp",
        "dt_s": config["planner"]["dt_s"],
        "problem_is_dpp": True,
        "cases": {},
    }
    for name, (scene, path, max_steps) in cases.items():
        planner = GTNRMPPlanner(config)
        report["problem_is_dpp"] &= planner.qp.problem.is_dpp()
        report["cases"][name] = serializable(run_closed_loop(planner, scene, path, config, lidar, max_steps, seed=0))
    report["gate_pass"] = all(
        case["metrics"]["success"]
        and not case["metrics"]["observable_collision"]
        and not case["metrics"]["world_collision"]
        and case["metrics"]["p95_end_to_end_ms"] < 200.0
        and case["metrics"]["average_end_to_end_ms"] < 200.0
        for case in report["cases"].values()
    )
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
