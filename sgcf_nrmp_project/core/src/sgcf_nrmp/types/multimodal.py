"""Oracle semantic image and painted-point containers."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class OracleSemanticImages:
    semantic_id_image: np.ndarray
    instance_id_image: np.ndarray
    depth_image: np.ndarray
    rgb_debug_image: np.ndarray


@dataclass(frozen=True)
class PaintedPoints:
    features: np.ndarray
    class_ids: np.ndarray
    class_probability: np.ndarray
    projection_valid: np.ndarray
    projection_confidence: np.ndarray
    reliability: np.ndarray
