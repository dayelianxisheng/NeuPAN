"""Programmatic 2D geometry enriched with semantic prism metadata."""

from dataclasses import dataclass
from sgcf_nrmp.types.semantic import SemanticObstacle


@dataclass(frozen=True)
class SemanticScene:
    obstacles: tuple[SemanticObstacle,...]
    bounds: tuple[float,float,float,float]
    name: str="semantic_scene"

    @property
    def obstacles_world(self): return [item.footprint_world for item in self.obstacles]
