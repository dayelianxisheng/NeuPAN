"""Versioned array schema for geometry_v1 NPZ shards."""

from __future__ import annotations

SCHEMA_VERSION = "geometry_v1"

FIELD_DTYPES = {
    "points_xy": "float32",
    "ranges": "float32",
    "point_valid_mask": "bool",
    "query_pose": "float32",
    "observable_clearance": "float32",
    "world_clearance": "float32",
    "observable_collision": "bool",
    "world_collision": "bool",
    "observable_gradient": "float32",
    "world_gradient": "float32",
    "observable_gradient_valid": "bool",
    "world_gradient_valid": "bool",
    "observable_available": "bool",
    "query_category": "int8",
    "scene_id": "int64",
    "query_id": "int64",
    "seed": "int64",
}

QUERY_CATEGORIES = {
    "free": 0,
    "safety_boundary": 1,
    "collision_boundary": 2,
    "collision": 3,
}
QUERY_CATEGORY_NAMES = {value: key for key, value in QUERY_CATEGORIES.items()}


def schema_description(fixed_point_count: int) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "fixed_point_count": fixed_point_count,
        "fields": {
            **{name: {"dtype": dtype} for name, dtype in FIELD_DTYPES.items()},
            "points_xy": {"dtype": "float32", "shape": [fixed_point_count, 2]},
            "ranges": {"dtype": "float32", "shape": [fixed_point_count]},
            "point_valid_mask": {"dtype": "bool", "shape": [fixed_point_count]},
            "query_pose": {"dtype": "float32", "shape": [4]},
            "observable_gradient": {"dtype": "float32", "shape": [3]},
            "world_gradient": {"dtype": "float32", "shape": [3]},
        },
        "query_categories": QUERY_CATEGORIES,
        "supervision_target": "observable_clearance",
        "evaluation_only": ["world_clearance", "world_collision"],
    }
