"""Stable simulator-side dataclasses with explicit frames and timestamps."""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class GazeboScanFrame:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    ranges: np.ndarray; angle_min_rad: float; angle_increment_rad: float
    range_min_m: float; range_max_m: float


@dataclass(frozen=True)
class GazeboImageFrame:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    image_rgb: np.ndarray


@dataclass(frozen=True)
class GazeboCameraInfo:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    width: int; height: int; fx: float; fy: float; cx: float; cy: float


@dataclass(frozen=True)
class GazeboRobotState:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    position_xyz: np.ndarray; orientation_xyzw: np.ndarray; twist_vw: np.ndarray


@dataclass(frozen=True)
class GazeboTransformSnapshot:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    target_frame: str; source_frame: str; T_target_source: np.ndarray


@dataclass(frozen=True)
class GazeboOracleSemanticFrame:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    class_ids: np.ndarray; simulation_only: bool = True; ground_truth_only: bool = True


@dataclass(frozen=True)
class PlannerInputFrame:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    points_xy: np.ndarray; point_valid_mask: np.ndarray; ranges: np.ndarray
    semantic_class_ids: np.ndarray | None = None


@dataclass(frozen=True)
class PlannerOutputFrame:
    timestamp_s: float; frame_id: str; sequence_id: int; valid: bool; source: str
    linear_velocity_mps: float; angular_velocity_radps: float; planner_status: str
    fallback_status: str | None = None; solver_status: str | None = None
    geometry_recheck_status: str | None = None; latency_ms: dict[str,float] = field(default_factory=dict)
