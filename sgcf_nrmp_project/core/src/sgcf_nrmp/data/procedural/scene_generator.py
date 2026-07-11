"""Obstacle constructors and deterministic random scene generator."""

from __future__ import annotations

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon, box

from sgcf_nrmp.data.procedural.scene import ProceduralScene


def circle_obstacle(center: tuple[float, float], radius: float, resolution: int = 32) -> Polygon:
    """Create a discretized circular obstacle."""
    from shapely.geometry import Point

    return Point(center).buffer(radius, resolution=resolution)


def rectangle_obstacle(center: tuple[float, float], length: float, width: float, yaw: float = 0.0) -> Polygon:
    polygon = box(-length / 2.0, -width / 2.0, length / 2.0, width / 2.0)
    polygon = affinity.rotate(polygon, yaw, origin=(0.0, 0.0), use_radians=True)
    return affinity.translate(polygon, center[0], center[1])


def convex_polygon_obstacle(vertices: list[tuple[float, float]]) -> Polygon:
    polygon = Polygon(vertices)
    if not polygon.is_valid or polygon.is_empty or not polygon.equals(polygon.convex_hull):
        raise ValueError("vertices must define a valid convex polygon")
    return polygon


def wall_obstacle(start: tuple[float, float], end: tuple[float, float], thickness: float) -> Polygon:
    from shapely.geometry import LineString

    if thickness <= 0.0:
        raise ValueError("wall thickness must be positive")
    return LineString([start, end]).buffer(thickness / 2.0, cap_style=2, join_style=2)


def corridor_obstacles(
    x_limits: tuple[float, float], center_y: float, clear_width: float, wall_thickness: float
) -> list[Polygon]:
    offset = clear_width / 2.0 + wall_thickness / 2.0
    return [
        wall_obstacle((x_limits[0], center_y - offset), (x_limits[1], center_y - offset), wall_thickness),
        wall_obstacle((x_limits[0], center_y + offset), (x_limits[1], center_y + offset), wall_thickness),
    ]


class SceneGenerator:
    """Generate reproducible mixtures of static convex obstacles."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng

    def random_scene(
        self,
        bounds: tuple[float, float, float, float],
        obstacle_count: int,
        exclusion_radius: float = 1.5,
        name: str = "random",
    ) -> ProceduralScene:
        x_min, y_min, x_max, y_max = bounds
        obstacles: list[Polygon] = []
        kinds: list[str] = []
        attempts = 0
        while len(obstacles) < obstacle_count and attempts < obstacle_count * 50:
            attempts += 1
            center = self.rng.uniform([x_min + 0.8, y_min + 0.8], [x_max - 0.8, y_max - 0.8])
            if np.linalg.norm(center) < exclusion_radius:
                continue
            kind = str(self.rng.choice(["circle", "rectangle", "polygon"]))
            if kind == "circle":
                obstacle = circle_obstacle(tuple(center), float(self.rng.uniform(0.25, 0.7)))
            elif kind == "rectangle":
                obstacle = rectangle_obstacle(
                    tuple(center), float(self.rng.uniform(0.4, 1.4)), float(self.rng.uniform(0.3, 1.0)),
                    float(self.rng.uniform(-np.pi, np.pi)),
                )
            else:
                angles = np.sort(self.rng.uniform(0.0, 2.0 * np.pi, 6))
                radii = self.rng.uniform(0.3, 0.7, 6)
                vertices = np.column_stack((np.cos(angles) * radii, np.sin(angles) * radii)) + center
                obstacle = Polygon(vertices).convex_hull
            obstacles.append(obstacle)
            kinds.append(kind)
        if len(obstacles) != obstacle_count:
            raise RuntimeError("could not place requested obstacles")
        return ProceduralScene(obstacles, bounds, name=name, metadata={"kinds": kinds})
