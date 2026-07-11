"""Deterministic procedural static geometry scenes."""

from .query_sampler import sample_query_poses
from .scene import ProceduralScene
from .scene_generator import SceneGenerator

__all__ = ["ProceduralScene", "SceneGenerator", "sample_query_poses"]
