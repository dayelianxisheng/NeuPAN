"""Strictly separated online observable geometry and offline world evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np
import torch
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.geometry.footprint import transform_footprint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarScan


class BatchedRectangleObservableOracle:
    """Exact rectangle-to-observed-point clearance for a batch of poses."""

    def __init__(self, points: np.ndarray, mask: np.ndarray, length: float, width: float, truncation: float):
        points = np.asarray(points, dtype=np.float64).reshape((-1, 2))
        mask = np.asarray(mask, dtype=bool).reshape((-1,))
        if len(points) != len(mask):
            raise ValueError("points and mask lengths differ")
        if length <= 0 or width <= 0 or truncation <= 0:
            raise ValueError("rectangle dimensions and truncation must be positive")
        self.points = torch.as_tensor(points, dtype=torch.float64, device="cpu")
        self.mask = torch.as_tensor(mask, dtype=torch.bool, device="cpu")
        self.half_extents = torch.tensor([length / 2.0, width / 2.0], dtype=torch.float64)
        self.truncation = float(truncation)

    def _distance_tensor(self, queries: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if queries.ndim != 2 or queries.shape[1] != 3:
            raise ValueError("queries must have shape [Q, 3]")
        if not bool(self.mask.any()):
            count = queries.shape[0]
            return (
                torch.full((count,), self.truncation, dtype=queries.dtype, device=queries.device),
                torch.full((count,), -1, dtype=torch.int64, device=queries.device),
                torch.zeros((count,), dtype=torch.bool, device=queries.device),
            )
        delta = self.points.unsqueeze(0) - queries[:, None, :2]
        cosine = torch.cos(queries[:, 2]).unsqueeze(1)
        sine = torch.sin(queries[:, 2]).unsqueeze(1)
        local_x = cosine * delta[..., 0] + sine * delta[..., 1]
        local_y = -sine * delta[..., 0] + cosine * delta[..., 1]
        local = torch.stack((local_x, local_y), dim=-1)
        outside = torch.clamp(torch.abs(local) - self.half_extents, min=0.0)
        point_distance = torch.linalg.vector_norm(outside, dim=-1)
        point_distance = point_distance.masked_fill(~self.mask.unsqueeze(0), torch.inf)
        raw, nearest = torch.min(point_distance, dim=1)
        distance = torch.clamp(raw, max=self.truncation)
        if point_distance.shape[1] > 1:
            closest_two = torch.topk(point_distance, k=2, dim=1, largest=False).values
            tie = torch.isfinite(closest_two[:, 1]) & ((closest_two[:, 1] - closest_two[:, 0]).abs() <= 1e-10)
        else:
            tie = torch.zeros_like(raw, dtype=torch.bool)
        ambiguous = tie | (raw <= 1e-10)
        return distance, nearest, ambiguous

    def distance(self, queries: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        tensor = torch.as_tensor(np.asarray(queries, dtype=np.float64), dtype=torch.float64)
        with torch.no_grad():
            distance, nearest, _ = self._distance_tensor(tensor)
        return distance.numpy(), nearest.numpy()

    def distance_and_gradient(self, queries: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        query = torch.as_tensor(np.asarray(queries, dtype=np.float64), dtype=torch.float64).clone().requires_grad_(True)
        distance, nearest, ambiguous = self._distance_tensor(query)
        if not bool(self.mask.any()):
            count = query.shape[0]
            return distance.detach().numpy(), np.zeros((count, 3), dtype=np.float64), np.zeros(count, dtype=bool), nearest.detach().numpy()
        gradient = torch.autograd.grad(distance.sum(), query)[0]
        finite = torch.isfinite(distance) & torch.isfinite(gradient).all(dim=1)
        available = torch.full_like(finite, bool(self.mask.any()))
        valid = finite & available & ~ambiguous & (distance < self.truncation - 1e-12)
        gradient = torch.where(torch.isfinite(gradient), gradient, torch.zeros_like(gradient))
        return distance.detach().numpy(), gradient.detach().numpy(), valid.detach().numpy(), nearest.detach().numpy()


class ExactObservableChecker:
    """Online checker that owns only one LiDAR observation and robot geometry."""

    def __init__(self, scan: LidarScan, length: float, width: float, truncation: float):
        points = np.asarray(scan.points_world, dtype=np.float64).reshape((-1, 2))
        self.oracle = BatchedRectangleObservableOracle(points, np.ones(len(points), dtype=bool), length, width, truncation)

    def distance(self, states: np.ndarray) -> np.ndarray:
        return self.oracle.distance(states)[0]

    def distance_and_gradient(self, states: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        distance, gradient, valid, _ = self.oracle.distance_and_gradient(states)
        return distance, gradient, valid

    def linearization(self, states: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return self.distance_and_gradient(states)

    def recheck_observable_trajectory(self, states: np.ndarray, d_safe: float) -> dict[str, object]:
        observable = self.distance(states)
        finite = np.isfinite(observable)
        offending = np.flatnonzero((observable < d_safe - 1e-4) | ~finite)
        collision = np.flatnonzero(observable <= 0.0)
        return {
            "observable": observable,
            "min_observable": float(np.min(observable)) if finite.all() else float("nan"),
            "violated_points": int(len(offending)),
            "offending_indices": offending.tolist(),
            "collision_indices": collision.tolist(),
            "nonfinite_indices": np.flatnonzero(~finite).tolist(),
            "required_clearance": float(d_safe),
        }


class LegacyGeometryOracle:
    """Shapely/finite-difference reference retained for equivalence tests only."""

    def __init__(self, scene: ProceduralScene, scan: LidarScan, footprint: Polygon, truncation: float, spatial_step: float = .02, angular_step: float = .02):
        self.scene, self.scan, self.footprint, self.truncation = scene, scan, footprint, truncation
        self.spatial_step, self.angular_step = spatial_step, angular_step

    def linearization(self, states: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        distances, gradients, valid = [], [], []
        for state in states:
            pose = Pose2D(*map(float, state))
            label = self.scene.label(self.footprint, pose, self.scan, self.truncation)
            gradient = self.scene.gradient(self.footprint, pose, self.scan, self.truncation, "observable_clearance", self.spatial_step, self.angular_step)
            distances.append(label.observable_clearance); gradients.append(gradient.as_array()); valid.append(gradient.gradient_valid and label.observable_available)
        return np.asarray(distances), np.asarray(gradients), np.asarray(valid, dtype=bool)

    def observable_distance(self, states: np.ndarray) -> np.ndarray:
        values = []
        for state in states:
            label = self.scene.label(self.footprint, Pose2D(*map(float, state)), self.scan, self.truncation)
            values.append(label.observable_clearance)
        return np.asarray(values)


@dataclass(frozen=True)
class OfflineEvaluationResult:
    minimum_world_clearance: float
    world_collision: bool
    partial_observation_world_risk: bool
    collision_step: int | None
    evaluation_time_ms: float
    world_clearances: np.ndarray


class OfflineWorldEvaluator:
    """Complete-world evaluator used only after online planning returns."""

    def __init__(self, scene: ProceduralScene, footprint: Polygon, truncation: float):
        self.footprint = footprint
        self.truncation = float(truncation)
        self.world_geometry = unary_union(scene.obstacles_world) if scene.obstacles_world else None

    def evaluate_trajectory(self, states: np.ndarray, observable: np.ndarray | None = None, d_safe: float = 0.0) -> OfflineEvaluationResult:
        started = time.perf_counter(); clearances = []; collisions = []
        for state in np.asarray(states):
            footprint_world = transform_footprint(self.footprint, Pose2D(*map(float, state)))
            collision = bool(self.world_geometry is not None and footprint_world.intersects(self.world_geometry))
            clearance = 0.0 if collision else (float(footprint_world.distance(self.world_geometry)) if self.world_geometry is not None else self.truncation)
            clearances.append(clearance); collisions.append(collision)
        values = np.asarray(clearances); collision_array = np.asarray(collisions, dtype=bool)
        collision_indices = np.flatnonzero(collision_array)
        hidden = bool(observable is not None and np.any(collision_array & (np.asarray(observable) >= d_safe)))
        return OfflineEvaluationResult(
            minimum_world_clearance=float(values.min()), world_collision=bool(collision_array.any()),
            partial_observation_world_risk=hidden,
            collision_step=int(collision_indices[0]) if len(collision_indices) else None,
            evaluation_time_ms=(time.perf_counter() - started) * 1000.0, world_clearances=values,
        )
