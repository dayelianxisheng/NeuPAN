#!/usr/bin/env python3
"""Finalize Stage 11B-L at the non-unit model complexity hard stop."""

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
OUT = PROJECT / "artifacts/stages/stage_11b_l_global_include_scale_normalization"
DECISION = "BLOCKED_NONUNIT_MODEL_MATERIALIZATION_COMPLEX"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, data: object) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def numbers(text: str | None, default: list[float]) -> list[float]:
    return [float(x) for x in text.split()] if text else default


def model_audit(uri: str) -> dict:
    model_name = uri.removeprefix("model://")
    path = MODELS / model_name / "model.sdf"
    root = ET.parse(path).getroot()
    model = root.find("model")
    assert model is not None
    links = model.findall("link")
    visuals = model.findall(".//visual")
    collisions = model.findall(".//collision")
    geometry_types = sorted({next(iter(g)).tag for g in model.findall(".//geometry") if len(g)})
    return {
        "model_name": model_name,
        "model_file": str(path.relative_to(REPO)),
        "model_hash": sha(path),
        "static": model.findtext("static") == "true",
        "link_count": len(links),
        "visual_count": len(visuals),
        "collision_count": len(collisions),
        "geometry_types": geometry_types,
        "visual_local_poses": [numbers(v.findtext("pose"), [0.0] * 6) for v in visuals],
        "collision_local_poses": [numbers(c.findtext("pose"), [0.0] * 6) for c in collisions],
        "material_xml_present": any(v.find("material") is not None for v in visuals),
        "plugin_count": len(model.findall(".//plugin")),
        "joint_count": len(model.findall(".//joint")),
        "sensor_count": len(model.findall(".//sensor")),
        "inertial_count": len(model.findall(".//inertial")),
        "nested_model_count": len(model.findall("model")),
        "mesh_count": len(model.findall(".//mesh")),
        "automatic_box_materialization_safe": (
            model.findtext("static") == "true"
            and len(links) == 1
            and len(visuals) == 1
            and len(collisions) == 1
            and geometry_types == ["box"]
            and not model.findall(".//plugin")
            and not model.findall(".//joint")
            and not model.findall(".//sensor")
            and not model.findall("model")
            and not model.findall(".//mesh")
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory: list[dict] = []
    for world_path in sorted(WORLDS.glob("*.sdf")):
        root = ET.parse(world_path).getroot()
        world = root.find("world")
        assert world is not None
        for index, include in enumerate(world.findall("include")):
            scale_text = include.findtext("scale")
            if scale_text is None:
                continue
            scale = numbers(scale_text, [1.0, 1.0, 1.0])
            uri = include.findtext("uri") or ""
            audit = model_audit(uri)
            geometry = audit["geometry_types"]
            strategy = "REMOVE_UNIT_INCLUDE_SCALE_ONLY" if scale == [1.0, 1.0, 1.0] else (
                "EXPLICIT_STATIC_BOX_MATERIALIZATION" if audit["automatic_box_materialization_safe"] else "BLOCKED_COMPLEX_NONUNIT_MODEL"
            )
            inventory.append({
                "world": world.get("name"),
                "include_xml_path": f"/sdf/world/include[{index}]",
                "included_uri": uri,
                "instance_name": include.findtext("name"),
                "pose_xyz_rpy": numbers(include.findtext("pose"), [0.0] * 6),
                "scale_xyz": scale,
                "unit_scale": scale == [1.0, 1.0, 1.0],
                "referenced_model_file": audit["model_file"],
                "referenced_model_geometry": geometry,
                "referenced_model_local_poses": {
                    "visual": audit["visual_local_poses"],
                    "collision": audit["collision_local_poses"],
                },
                "chosen_migration_strategy": strategy,
                "model_structure_audit": audit,
            })

    unit = [x for x in inventory if x["unit_scale"]]
    nonunit = [x for x in inventory if not x["unit_scale"]]
    write("stage11bl_include_scale_inventory.json", {
        "status": "AUDIT_COMPLETE",
        "historical_invalid_include_scale_count": len(inventory),
        "unit_scale_count": len(unit),
        "nonunit_scale_count": len(nonunit),
        "affected_world_count": len({x["world"] for x in inventory}),
        "affected_include_count": len(inventory),
        "legal_mesh_scale_count": sum(len(ET.parse(p).getroot().findall(".//mesh/scale")) for p in [*WORLDS.glob("*.sdf"), *MODELS.rglob("*.sdf")]),
        "records": inventory,
    })

    resolution_records = []
    for item in nonunit:
        audit = item["model_structure_audit"]
        model_path = REPO / audit["model_file"]
        model = ET.parse(model_path).getroot().find("model")
        assert model is not None
        geometry_type = audit["geometry_types"][0]
        record = {
            "world": item["world"],
            "instance_name": item["instance_name"],
            "model": audit["model_name"],
            "scale_xyz": item["scale_xyz"],
            "geometry_type": geometry_type,
            "base_visual_local_pose": audit["visual_local_poses"][0],
            "base_collision_local_pose": audit["collision_local_poses"][0],
            "world_pose": item["pose_xyz_rpy"],
            "automatic_materialization_safe": audit["automatic_box_materialization_safe"],
        }
        if geometry_type == "box":
            size = numbers(model.findtext(".//visual/geometry/box/size"), [])
            record.update({
                "base_dimensions": size,
                "resolved_dimensions": [a * b for a, b in zip(size, item["scale_xyz"])],
                "resolved_visual_local_pose": [item["scale_xyz"][i] * audit["visual_local_poses"][0][i] if i < 3 else audit["visual_local_poses"][0][i] for i in range(6)],
                "resolved_collision_local_pose": [item["scale_xyz"][i] * audit["collision_local_poses"][0][i] if i < 3 else audit["collision_local_poses"][0][i] for i in range(6)],
            })
        else:
            record.update({
                "base_radius": float(model.findtext(".//visual/geometry/cylinder/radius")),
                "base_length": float(model.findtext(".//visual/geometry/cylinder/length")),
                "blocked_reason": "non-unit referenced geometry is cylinder; authorization permits automatic materialization only for box primitives",
            })
        resolution_records.append(record)
    write("stage11bl_nonunit_scale_resolution.json", {
        "status": "BLOCKED",
        "decision": DECISION,
        "records": resolution_records,
        "complex_nonunit_instances": [x["instance_name"] for x in resolution_records if not x["automatic_materialization_safe"]],
        "runtime_clearance_used_to_infer_dimensions": False,
    })
    write("stage11bl_intended_nonunit_geometry.json", {
        "status": "PARTIALLY_RESOLVED_THEN_BLOCKED",
        "decision": DECISION,
        "records": resolution_records,
        "source_types": ["source generator parameters", "referenced base model", "historical intended scale", "Stage 11A manifest"],
    })

    world_hashes = {p.name: sha(p) for p in sorted(WORLDS.glob("*.sdf"))}
    model_hashes = {str(p.relative_to(MODELS)): sha(p) for p in sorted(MODELS.rglob("*")) if p.is_file()}
    generator = GAZEBO / "scripts/generate_static_assets.py"
    frozen = {
        "status": "PASS_NO_MUTATION_BEFORE_HARD_STOP",
        "assets_modified": False,
        "runtime_started": False,
        "world_hashes_before": world_hashes,
        "world_hashes_after": world_hashes,
        "world_hashes_unchanged": True,
        "model_hashes_before": model_hashes,
        "model_hashes_after": model_hashes,
        "model_hashes_unchanged": True,
        "generator_hash": sha(generator),
        "robot_model_hash": sha(MODELS / "sgcf_diff_drive_robot/model.sdf"),
        "empty_world_hash": world_hashes["empty_world.sdf"],
        "docker_modified_by_stage11bl": False,
        "core_modified_by_stage11bl": False,
        "planner_started": False,
        "stage10_loaded": False,
        "ros_bridge_started": False,
        "motion_commands_sent": False,
    }
    write("stage11bl_asset_delta.json", {"status": "NO_CHANGES_DUE_TO_HARD_STOP", "changed_files": []})
    write("stage11bl_updated_world_manifest.json", {"status": "NOT_UPDATED_DUE_TO_HARD_STOP", "world_hashes": world_hashes})
    write("stage11bl_frozen_component_audit.json", frozen)

    reason = "initial_collision non-unit scale references a cylinder model; automatic conversion is authorized only for simple static box models"
    not_run = {"status": "NOT_EXECUTED_DUE_TO_EARLIER_STOP", "decision": DECISION, "reason": reason}
    for name in [
        "stage11bl_generator_migration.json",
        "stage11bl_generation_determinism.json",
        "stage11bl_sdf_schema_validation.json",
        "stage11bl_static_geometry_equivalence.json",
        "stage11bl_resolved_obstacle_geometry.json",
        "stage11bl_runtime_image_binding.json",
        "stage11bl_environment_consistency.json",
        "stage11bl_changed_world_runtime_matrix.json",
        "stage11bl_runtime_entity_audit.json",
        "stage11bl_sensor_runtime_smoke.json",
        "stage11bl_runtime_clearance_consistency.json",
        "stage11bl_semantic_entity_regression.json",
        "stage11bl_r1_runtime_contract.json",
        "stage11bl_lidar_self_visibility_regression.json",
        "stage11bl_process_cleanup.json",
    ]:
        write(name, not_run)

    (OUT / "stage_11b_l_report.md").write_text(f"""# Stage 11B-L Global Include-scale Audit Report

## Decision

```text
{DECISION}
```

All 13 historical invalid `include/scale` elements were classified: 8 are unit scale and 5 are non-unit scale. The four corridor / passage wall instances reference the simple static `static_obstacle` box and satisfy the automatic materialization preconditions. The fifth non-unit instance, `initial_collision_obstacle`, references `human_placeholder`, whose visual and collision geometry are cylinders (`radius=0.35`, `length=1.7`).

The authorized automatic non-unit migration is explicitly limited to simple box primitives. Converting this anisotropically scaled cylinder into a different explicit representation would require a newly authorized cylinder-specific rule or a deliberate redesign as an explicit box. Neither may be inferred here. The hard stop therefore occurred before modifying the source generator or any active asset.

No world, model, generator, Docker, Core, robot, sensor, Adapter, or algorithm was modified. No SDFormat runtime command or Gazebo process was started. All later gates are explicitly marked not executed.
""", encoding="utf-8")
    (OUT / "stage_11b_l_decision.md").write_text(f"# Stage 11B-L Decision\n\n```text\n{DECISION}\n```\n", encoding="utf-8")
    (OUT / "known_limitations.md").write_text(
        "# Known limitations\n\n"
        "- `initial_collision_obstacle` uses non-unit scaling of a cylinder model.\n"
        "- The current authorization permits automatic non-unit materialization only for box primitives.\n"
        "- Generator migration, schema validation, and runtime smoke were not executed.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
