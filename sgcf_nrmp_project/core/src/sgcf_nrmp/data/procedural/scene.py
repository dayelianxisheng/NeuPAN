"""Static procedural scene and label API."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import Polygon

from sgcf_nrmp.geometry.footprint_distance import clearance_labels, finite_difference_gradient
from sgcf_nrmp.geometry.raycast import simulate_lidar
from sgcf_nrmp.types.geometry import ClearanceLabel, GradientLabel, Pose2D
from sgcf_nrmp.types.lidar import LidarConfig, LidarScan


@dataclass
class ProceduralScene:
    """Complete static world geometry plus one robot-local LiDAR observation."""

    obstacles_world: list[Polygon]
    bounds: tuple[float, float, float, float]
    name: str = "scene"
    metadata: dict[str, object] = field(default_factory=dict)

    def scan(self, sensor_pose_world: Pose2D, config: LidarConfig, rng: np.random.Generator) -> LidarScan:
        return simulate_lidar(self.obstacles_world, sensor_pose_world, config, rng)

    def label(
        self,
        footprint_robot: Polygon,
        query_pose_world: Pose2D,
        scan: LidarScan,
        observable_truncation: float,
    ) -> ClearanceLabel:
        return clearance_labels(
            footprint_robot,
            query_pose_world,
            self.obstacles_world,
            scan.points_world,
            observable_truncation,
        )

    def gradient(
        self,
        footprint_robot: Polygon,
        query_pose_world: Pose2D,
        scan: LidarScan,
        observable_truncation: float,
        target: str,
        spatial_step: float,
        angular_step: float,
    ) -> GradientLabel:
        if target not in {"observable_clearance", "world_clearance"}:
            raise ValueError("target must be observable_clearance or world_clearance")

        def value_at_pose(pose: Pose2D) -> tuple[float, bool]:
            label = self.label(footprint_robot, pose, scan, observable_truncation)
            if target == "observable_clearance":
                return label.observable_clearance, label.observable_collision
            return label.world_clearance, label.world_collision

        return finite_difference_gradient(value_at_pose, query_pose_world, spatial_step, angular_step)
