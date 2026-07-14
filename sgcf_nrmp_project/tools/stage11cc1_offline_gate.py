#!/usr/bin/env python3
"""Deterministic offline validation for the Stage 11C-C1 Planner image."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

import numpy as np
import yaml


ROOT = Path(os.environ.get("SGCF_REPO_ROOT", Path.cwd()))
CFG = yaml.safe_load(
    (ROOT / "sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml").read_text()
)


def install_cpu_execution_trace(torch):
    counts = {
        "tensor_cuda_calls": 0, "module_cuda_calls": 0,
        "explicit_cuda_to_requests": 0, "cuda_init_calls": 0,
        "cuda_set_device_calls": 0,
    }

    def wrap(owner, name, counter, inspect_device=False):
        original = getattr(owner, name)
        def traced(*args, **kwargs):
            if inspect_device:
                requested = args[1] if len(args) > 1 else kwargs.get("device")
                if requested is not None and str(requested).startswith("cuda"):
                    counts[counter] += 1
            else:
                counts[counter] += 1
            return original(*args, **kwargs)
        setattr(owner, name, traced)

    wrap(torch.Tensor, "cuda", "tensor_cuda_calls")
    wrap(torch.nn.Module, "cuda", "module_cuda_calls")
    wrap(torch.Tensor, "to", "explicit_cuda_to_requests", True)
    wrap(torch.nn.Module, "to", "explicit_cuda_to_requests", True)
    wrap(torch.cuda, "init", "cuda_init_calls")
    wrap(torch.cuda, "set_device", "cuda_set_device_calls")
    return counts


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q))


def result_record(result) -> dict[str, object]:
    diagnostics = result.diagnostics
    distances = diagnostics.get("exact_distance_samples", [])
    gradients = diagnostics.get("exact_gradient_samples", [])
    margins = diagnostics.get("semantic_margin_samples", [])
    return {
        "status": result.status.value,
        "first_control": np.asarray(result.first_control, dtype=float).tolist(),
        "command_eligible": result.status.value in {
            "SOLVED_SAFE", "SOLVED_WITH_SLACK", "EXPLICIT_FAILURE_GEOMETRY_FALLBACK",
            "SEMANTIC_DEGRADED_TO_GEOMETRY",
        },
        "min_observable_clearance": float(result.min_observable_clearance),
        "solver_iterations": int(result.scp_iterations),
        "d_geo": distances[-1] if distances else [],
        "g_geo": gradients[-1] if gradients else [],
        "semantic_margin": margins[-1] if margins else [],
        "fallback_reason": diagnostics.get("explicit_failure_fallback", {}).get(
            "fallback_reason",
            diagnostics.get("semantic_failure_comparison", {}).get("fallback_reason"),
        ),
    }


def planner_fixture(kind: str):
    from sgcf_nrmp.data.procedural.scene import ProceduralScene
    from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
    from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
    from sgcf_nrmp.planner.reference import local_reference, polyline_path
    from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
    from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
    from sgcf_nrmp.types.geometry import Pose2D
    from sgcf_nrmp.types.lidar import LidarConfig, LidarScan

    state = np.zeros(3, dtype=float)
    path = polyline_path([(0, 0), (0.7, 0.7), (1.5, 1.0), (2.3, 0.7), (4, 0)])
    reference = local_reference(
        state,
        path,
        CFG["planner"]["horizon"],
        CFG["planner"]["reference_speed_mps"] * CFG["planner"]["dt_s"],
    )
    if kind == "p0":
        scan = LidarScan(np.empty(0), np.empty(0, bool), np.empty((0, 2)), np.empty((0, 2)), np.empty(0))
        return state, reference, ExactObservableChecker(scan, 0.8, 0.5, 8.0)
    if kind == "collision":
        points = np.asarray([[0.0, 0.0]])
        scan = LidarScan(np.asarray([0.0]), np.ones(1, bool), points, points, np.asarray([0.0]))
        return state, reference, ExactObservableChecker(scan, 0.8, 0.5, 8.0)
    if kind == "r1":
        scan = LidarScan(np.empty(0), np.empty(0, bool), np.empty((0, 2)), np.empty((0, 2)), np.empty(0))
        exact = ExactObservableChecker(scan, 0.8, 0.5, 8.0)
        provider = SemanticMarginProvider(
            scan.points_world, np.empty((0, 5)), np.empty(0, bool), np.empty(0, bool),
            False, 0.0, True,
        )
        return state, reference, SemanticObservableChecker(exact, provider)
    scene = ProceduralScene([circle_obstacle((1.5, 0), 0.35)], (-2, -2, 5, 2))
    scan = scene.scan(Pose2D(*state), LidarConfig(num_beams=181, range_max=8.0), np.random.default_rng(1))
    exact = ExactObservableChecker(scan, 0.8, 0.5, 8.0)
    probabilities = np.zeros((len(scan.points_world), 5))
    probabilities[:, 2] = 1.0
    valid = np.ones(len(probabilities), bool)
    if kind == "semantic":
        provider = SemanticMarginProvider(scan.points_world, probabilities, valid, valid, True, 0.0, True)
    else:
        raise ValueError(kind)
    return state, reference, SemanticObservableChecker(exact, provider)


def geometry_gate() -> dict[str, object]:
    import torch
    from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle

    fixtures = {
        "empty": (np.empty((0, 2)), np.empty(0, bool), np.asarray([[0.0, 0.0, 0.0]])),
        "single": (np.asarray([[1.2, 0.1]]), np.ones(1, bool), np.asarray([[0.0, 0.0, 0.0], [0.2, -0.1, 0.2]])),
        "corridor": (np.asarray([[x, y] for x in np.linspace(-1, 2, 9) for y in (-0.8, 0.8)]), np.ones(18, bool), np.asarray([[0.1, 0.0, 0.0], [0.4, 0.1, 0.3]])),
        "boundary": (np.asarray([[0.650001, 0.0], [0.0, 0.500001]]), np.ones(2, bool), np.asarray([[0.0, 0.0, 0.0]])),
        "collision": (np.asarray([[0.0, 0.0]]), np.ones(1, bool), np.asarray([[0.0, 0.0, 0.0]])),
        "yaw": (np.asarray([[0.9, 0.45], [1.2, -0.3]]), np.ones(2, bool), np.asarray([[0.1, -0.1, 0.63]])),
    }
    records = {}
    repeated_max = 0.0
    observed_devices = set()
    for name, (points, mask, queries) in fixtures.items():
        oracle = BatchedRectangleObservableOracle(points, mask, 0.8, 0.5, 8.0)
        observed_devices.update((str(oracle.points.device), str(oracle.mask.device), str(oracle.half_extents.device)))
        runs = [oracle.distance_and_gradient(queries) for _ in range(20)]
        base_d, base_g, base_valid, nearest = runs[0]
        for d, g, valid, _ in runs[1:]:
            repeated_max = max(repeated_max, float(np.max(np.abs(d - base_d))), float(np.max(np.abs(g - base_g))))
            assert np.array_equal(valid, base_valid)
        assert np.isfinite(base_d).all() and np.isfinite(base_g).all()
        records[name] = {
            "d_geo": base_d.tolist(), "g_geo": base_g.tolist(),
            "gradient_valid": base_valid.tolist(), "nearest": nearest.tolist(),
            "collision": bool(np.any(base_d <= 0.0)),
        }
    assert repeated_max <= 1e-9
    assert observed_devices == {"cpu"}
    return {
        "fixtures": records, "repeated_max_difference": repeated_max,
        "tensor_devices": sorted(observed_devices), "autograd_enabled": torch.is_grad_enabled(),
    }


def osqp_gate() -> dict[str, object]:
    import osqp
    from scipy import sparse

    solver = osqp.OSQP()
    solver.setup(
        P=sparse.csc_matrix([[4.0, 1.0], [1.0, 2.0]]), q=np.asarray([1.0, 1.0]),
        A=sparse.csc_matrix([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]]),
        l=np.asarray([1.0, 0.0, 0.0]), u=np.asarray([1.0, 0.7, 0.7]),
        warm_starting=True, verbose=False, polishing=True,
    )
    solutions, statuses, iterations = [], [], []
    for _ in range(20):
        result = solver.solve()
        statuses.append(result.info.status)
        iterations.append(int(result.info.iter))
        solutions.append(np.asarray(result.x, dtype=float))
    delta = max(float(np.max(np.abs(value - solutions[0]))) for value in solutions)
    assert all("solved" in status.lower() for status in statuses)
    assert all(np.isfinite(value).all() for value in solutions)
    assert delta <= 1e-9
    return {"success_count": 20, "statuses": statuses, "iterations": iterations,
            "solution": solutions[0].tolist(), "maximum_repeated_solution_difference": delta}


def planner_and_performance() -> tuple[dict[str, object], dict[str, object]]:
    from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner

    replay = {}
    for kind in ("p0", "semantic", "r1", "collision"):
        state, reference, checker = planner_fixture(kind)
        result = GTNRMPPlanner(CFG).plan(state, reference, checker)
        replay[kind] = result_record(result)
    assert replay["collision"]["status"] == "EMERGENCY_STOP"
    assert replay["collision"]["command_eligible"] is False
    assert replay["r1"]["status"] == "EXPLICIT_FAILURE_GEOMETRY_FALLBACK"
    assert "RGB_DROPOUT" in (replay["r1"]["fallback_reason"] or [])

    state, reference, checker = planner_fixture("p0")
    planner = GTNRMPPlanner(CFG)
    for _ in range(8):
        planner.plan(state, reference, checker)
    samples = []
    for _ in range(100):
        started = time.perf_counter()
        planner.plan(state, reference, checker)
        samples.append((time.perf_counter() - started) * 1000.0)
    performance = {
        "sample_count": 100, "mean_ms": statistics.fmean(samples),
        "p50_ms": percentile(samples, 50), "p95_ms": percentile(samples, 95),
        "maximum_ms": max(samples), "threshold_ms": 200.0,
    }
    performance["passed"] = performance["p95_ms"] <= 200.0
    assert performance["passed"]
    return replay, performance


def ros_gate() -> dict[str, object]:
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import CameraInfo, Image, LaserScan

    rclpy.init(args=None)
    node = rclpy.create_node("stage11cc1_offline_coexistence")
    if node.has_parameter("use_sim_time"):
        from rclpy.parameter import Parameter
        node.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
    else:
        node.declare_parameter("use_sim_time", True)
    publisher = node.create_publisher(Twist, "/sgcf/planner_candidate_cmd_vel", 1)
    subscriptions = [
        node.create_subscription(LaserScan, "/scan", lambda _: None, 1),
        node.create_subscription(Image, "/camera/image_raw", lambda _: None, 1),
        node.create_subscription(CameraInfo, "/camera/camera_info", lambda _: None, 1),
        node.create_subscription(Odometry, "/odom", lambda _: None, 1),
    ]
    result = {"node_created": True, "use_sim_time": node.get_parameter("use_sim_time").value,
              "candidate_publisher_created": publisher is not None, "subscription_count": len(subscriptions),
              "cmd_vel_published": False}
    node.destroy_node()
    rclpy.shutdown()
    result["node_destroyed"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--with-ros", action="store_true")
    args = parser.parse_args()

    import cvxpy
    import osqp
    import scipy
    import torch
    from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle
    from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner

    before_initialized = torch.cuda.is_initialized()
    cpu_trace = install_cpu_execution_trace(torch)
    data = {
        "environment": {
            "python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
            "torch": torch.__version__, "torch_compiled_cuda": torch.version.cuda,
            "osqp": osqp.__version__, "cvxpy": cvxpy.__version__,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "nvidia_visible_devices": os.environ.get("NVIDIA_VISIBLE_DEVICES"),
            "torch_cuda_available": torch.cuda.is_available(),
            "torch_cuda_device_count": torch.cuda.device_count(),
            "torch_cuda_initialized_before": before_initialized,
            "planner_class": f"{GTNRMPPlanner.__module__}.{GTNRMPPlanner.__name__}",
            "geometry_class": f"{BatchedRectangleObservableOracle.__module__}.{BatchedRectangleObservableOracle.__name__}",
        },
        "geometry": geometry_gate(),
        "osqp": osqp_gate(),
    }
    data["replay"], data["performance"] = planner_and_performance()
    data["ros"] = ros_gate() if args.with_ros else {"status": "REFERENCE_ENVIRONMENT_NOT_REQUESTED"}
    data["environment"]["torch_cuda_initialized_after"] = torch.cuda.is_initialized()
    data["cpu_execution_trace"] = {
        **cpu_trace,
        "cuda_tensor_count": 0,
        "cuda_context_count": int(data["environment"]["torch_cuda_initialized_after"]),
        "cuda_allocation_count": 0,
        "cuda_kernel_count": 0,
        "observed_tensor_devices": data["geometry"]["tensor_devices"],
        "planner_device": "cpu",
        "geometry_checker_device": "cpu",
    }
    data["environment"]["stage10_modules_loaded"] = sorted(
        name for name in sys.modules
        if "rgb_semantic_predictor" in name or "tiny_semantic_segmentation" in name or ".training" in name
    )
    assert not data["environment"]["torch_cuda_available"]
    assert data["environment"]["torch_cuda_device_count"] == 0
    assert not data["environment"]["torch_cuda_initialized_after"]
    assert not data["environment"]["stage10_modules_loaded"]
    assert all(value == 0 for key, value in cpu_trace.items())
    Path(args.output).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
