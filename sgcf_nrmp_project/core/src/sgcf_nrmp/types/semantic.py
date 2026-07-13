"""Semantic classes and oracle obstacle metadata."""

from dataclasses import dataclass
from enum import IntEnum
from shapely.geometry import Polygon


class SemanticClass(IntEnum):
    UNKNOWN=0; STATIC_OBSTACLE=1; HUMAN=2; VEHICLE=3; ROBOT=4


@dataclass(frozen=True)
class SemanticObstacle:
    footprint_world: Polygon
    semantic_class: SemanticClass
    instance_id: int
    height: float
    visual_color: tuple[float,float,float]
    material_id: int = 0

    def __post_init__(self):
        if self.height<=0 or self.instance_id<=0: raise ValueError("height and instance_id must be positive")
