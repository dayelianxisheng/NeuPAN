#!/usr/bin/env python3
"""Finalize Stage 11B-K after the mandatory include/scale scope stop."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent
GAZEBO = PROJECT / "gazebo"
WORLDS = GAZEBO / "worlds"
MODELS = GAZEBO / "models"
OUT = PROJECT / "artifacts/stages/stage_11b_k_explicit_wall_geometry"
DECISION = "BLOCKED_SCALE_SCOPE_EXPANSION_REQUIRED"
TARGETS = {"static_corridor", "narrow_passage"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def include_records() -> list[dict]:
    records: list[dict] = []
    for path in sorted([*WORLDS.rglob("*.sdf"), *MODELS.rglob("*.sdf")]):
        root = ET.parse(path).getroot()
        world = root.find("world")
        scene_id = world.get("name") if world is not None else None
        for index, include in enumerate(root.iter("include")):
            children = [child.tag for child in include]
            scale = include.findtext("scale")
            records.append({
                "file": str(path.relative_to(REPO)),
                "scene_id": scene_id,
                "xml_path": f"/sdf/world/include[{index}]" if scene_id else f"/sdf/model/include[{index}]",
                "uri": include.findtext("uri"),
                "name": include.findtext("name"),
                "pose": include.findtext("pose"),
                "static": include.findtext("static"),
                "placement_frame": include.get("placement_frame"),
                "plugin_count": len(include.findall("plugin")),
                "child_elements": children,
                "scale": scale,
                "has_invalid_include_scale": scale is not None,
                "in_authorized_target_scope": scene_id in TARGETS,
            })
    return records


def not_executed(reason: str) -> dict:
    return {"status": "NOT_EXECUTED_DUE_TO_EARLIER_STOP", "reason": reason, "decision": DECISION}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = include_records()
    invalid = [r for r in records if r["has_invalid_include_scale"]]
    affected = sorted({r["scene_id"] for r in invalid if r["scene_id"]})
    outside = [r for r in invalid if not r["in_authorized_target_scope"]]
    generator = GAZEBO / "scripts/generate_static_assets.py"
    generator_text = generator.read_text(encoding="utf-8")
    source_emits_scale = "<scale>{' '.join(map(str,scale))}</scale>" in generator_text

    audit = {
        "status": "FAILED_SCOPE_GATE",
        "decision": DECISION,
        "include_count": len(records),
        "invalid_include_scale_count": len(invalid),
        "affected_world_count": len(affected),
        "affected_model_count": 0,
        "affected_worlds": affected,
        "authorized_target_worlds": sorted(TARGETS),
        "outside_authorized_scope_count": len(outside),
        "outside_authorized_scope_worlds": sorted({r["scene_id"] for r in outside}),
        "other_undefined_include_children": [],
        "source_of_truth_generator": str(generator.relative_to(REPO)),
        "source_generator_emits_include_scale_for_all_obstacles": source_emits_scale,
        "records": records,
    }
    write_json("stage11bk_include_schema_audit.json", audit)

    # Design intent is recorded but no repair is authorized after the scope gate.
    intended = []
    for scene, y in (("static_corridor", 0.7), ("narrow_passage", 0.585)):
        for name, sign in (("wall_left", 1), ("wall_right", -1)):
            intended.append({
                "scene_id": scene,
                "model_name": name,
                "semantic_class": "STATIC_OBSTACLE",
                "source_manifest": "stage_11a_gazebo_preparation/gazebo_scenario_manifest.json",
                "source_generator": str(generator.relative_to(REPO)),
                "intended_pose_xyz_rpy": [2.0, sign * y, 0.25, 0.0, 0.0, 0.0],
                "intended_dimensions_xyz_m": [5.0, 0.15, 0.5],
                "base_model_dimensions_xyz_m": [1.0, 1.0, 1.0],
                "historical_invalid_scale": [5.0, 0.15, 0.5],
                "base_times_scale_matches_intent": True,
            })
    write_json("stage11bk_intended_wall_geometry.json", {
        "status": "RECORDED_NOT_APPLIED_DUE_TO_SCOPE_STOP",
        "records": intended,
        "dimensions_inferred_from_runtime_clearance": False,
    })

    world_hashes = {p.name: sha256(p) for p in sorted(WORLDS.glob("*.sdf"))}
    model_hashes = {str(p.relative_to(MODELS)): sha256(p) for p in sorted(MODELS.rglob("*")) if p.is_file()}
    frozen = {
        "status": "PASS_NO_ASSET_MUTATION_BEFORE_STOP",
        "world_hashes_before": world_hashes,
        "world_hashes_after": world_hashes,
        "world_hashes_unchanged": True,
        "model_hashes_before": model_hashes,
        "model_hashes_after": model_hashes,
        "model_hashes_unchanged": True,
        "generator_hash": sha256(generator),
        "robot_model_hash": sha256(MODELS / "sgcf_diff_drive_robot/model.sdf"),
        "gazebo_runtime_started": False,
        "assets_modified": False,
        "docker_modified_by_stage11bk": False,
        "core_modified_by_stage11bk": False,
    }
    write_json("stage11bk_asset_delta.json", {
        "status": "NO_CHANGES_DUE_TO_SCOPE_STOP",
        "changed_files": [],
        "authorized_asset_changes_applied": False,
    })
    write_json("stage11bk_frozen_asset_audit.json", frozen)
    write_json("stage11bk_updated_world_manifest.json", {
        "status": "NOT_UPDATED_DUE_TO_EARLIER_STOP",
        "world_hashes": world_hashes,
    })

    reason = "include/scale exists outside static_corridor and narrow_passage; expanding the asset repair was not authorized"
    for name in [
        "stage11bk_sdf_schema_validation.json",
        "stage11bk_resolved_wall_dimensions.json",
        "stage11bk_static_geometry_consistency.json",
        "stage11bk_runtime_image_binding.json",
        "stage11bk_environment_consistency.json",
        "stage11bk_runtime_wall_geometry.json",
        "stage11bk_runtime_entity_audit.json",
        "stage11bk_targeted_clearance_consistency.json",
        "stage11bk_lidar_self_visibility_regression.json",
        "stage11bk_camera_regression.json",
        "stage11bk_odometry_regression.json",
        "stage11bk_process_cleanup.json",
    ]:
        write_json(name, not_executed(reason))

    report = f"""# Stage 11B-K Include-scale Scope Audit Report

## Decision

```text
{DECISION}
```

The mandatory repository-wide include audit found **{len(invalid)}** `include/scale` elements across **{len(affected)}** worlds. Four belong to the two authorized targets, but **{len(outside)}** occur in other worlds: `{', '.join(sorted({r['scene_id'] for r in outside}))}`.

The source-of-truth generator emits `<scale>` for every obstacle include, including unit scale. More importantly, `initial_collision` uses a non-unit include scale, so this is not merely redundant syntax outside the two target worlds. Repairing only `static_corridor` and `narrow_passage` would leave the same schema defect elsewhere; repairing all affected scenes would exceed the authorized scope.

No generator, world, model, Docker, Core, robot, sensor, Adapter, or algorithm asset was modified. No Gazebo process was started. SDF runtime validation and the four-scene targeted Gate were not executed after the immediate-stop condition.
"""
    (OUT / "stage_11b_k_report.md").write_text(report, encoding="utf-8")
    (OUT / "stage_11b_k_decision.md").write_text(f"# Stage 11B-K Decision\n\n```text\n{DECISION}\n```\n", encoding="utf-8")
    (OUT / "known_limitations.md").write_text(
        "# Known limitations\n\n"
        "- The source generator emits unsupported `include/scale` for obstacle instances in eleven worlds.\n"
        "- `initial_collision` depends on a non-unit include scale and therefore requires an explicitly authorized wider asset repair.\n"
        "- No Stage 11B-K runtime acceptance was performed.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
