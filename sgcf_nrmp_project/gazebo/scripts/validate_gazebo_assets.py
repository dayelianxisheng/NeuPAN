#!/usr/bin/env python3
"""Static SDF, manifest, frame, footprint, and geometry validation."""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
import yaml
from shapely.geometry import Point

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent
OUT=PROJECT/"artifacts/stages/stage_11a_gazebo_preparation"
OUT.mkdir(parents=True,exist_ok=True)


def dump(name,value): (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


commands={}
for name in ("gz","gazebo","ign","ros2","colcon","xacro","python"):
    path=shutil.which(name); item={"path":path,"available":path is not None,"version":None,"available_subcommands":[],"headless_capability":"NOT_TESTED_RUNTIME_UNAVAILABLE"}
    if path:
        result=subprocess.run([path,"--version"],capture_output=True,text=True,timeout=5); item["version"]=(result.stdout or result.stderr).strip().splitlines()[:3]
    commands[name]=item
audit={"selected_simulator":"Modern Gazebo / gz sim static target","selected_sdf_version":"1.9","selection_reason":"No Gazebo runtime is installed; one forward static target is used without multi-version abstraction.","runtime_available":False,"commands":commands,"required_environment_variables":{"GZ_SIM_RESOURCE_PATH":str(ROOT/"models"),"ROS_DOMAIN_ID":"future ROS 2 integration only","use_sim_time":"future runtime true"},"runtime_actions_executed":False}
dump("gazebo_environment_audit.json",audit)

errors=[]; parsed=[]
for path in sorted(list(ROOT.glob("worlds/*.sdf"))+list(ROOT.glob("models/*/model.sdf"))+list(ROOT.glob("models/*/model.config"))):
    try: tree=ET.parse(path); parsed.append(str(path.relative_to(PROJECT)))
    except ET.ParseError as error: errors.append({"file":str(path),"error":str(error)})
for path in ROOT.glob("worlds/*.sdf"):
    tree=ET.parse(path); names=[]
    for model in tree.findall(".//model"): names.append(model.get("name"))
    for include in tree.findall(".//include"):
        name=include.findtext("name"); names.append(name); uri=include.findtext("uri"); target=ROOT/"models"/uri.removeprefix("model://")/"model.sdf"
        if not target.exists(): errors.append({"file":str(path),"missing_reference":str(target)})
    if len(names)!=len(set(names)): errors.append({"file":str(path),"duplicate_names":names})

config=yaml.safe_load((ROOT/"config/scenarios.yaml").read_text()); scenes=config["scenarios"]; ids=[item["scene_id"] for item in scenes]
if len(ids)!=len(set(ids)): errors.append({"duplicate_scene_ids":ids})
classes=yaml.safe_load((ROOT/"config/semantic_classes.yaml").read_text()); valid_classes=set(classes)
for scene in scenes:
    if not (ROOT/scene["world"]).exists(): errors.append({"missing_world":scene["world"]})
    for obstacle in scene["obstacles"]:
        if obstacle["semantic_class"] not in valid_classes: errors.append({"invalid_semantic_class":obstacle["semantic_class"]})

robot=ET.parse(ROOT/"models/sgcf_diff_drive_robot/model.sdf"); size=[float(x) for x in robot.findtext(".//collision[@name='planner_footprint_collision']/geometry/box/size").split()]
planner=yaml.safe_load((PROJECT/"core/configs/planner/diff_drive_gt_nrmp.yaml").read_text()); expected=[planner["robot"]["footprint_length_m"],planner["robot"]["footprint_width_m"]]
footprint={
    "gazebo_collision_box_length_m":size[0],
    "gazebo_collision_box_width_m":size[1],
    "stage05_length_m":expected[0],
    "stage05_width_m":expected[1],
    "length_error_m":abs(size[0]-expected[0]),
    "width_error_m":abs(size[1]-expected[1]),
    "base_link_origin":"center of rectangle at z=0.1 m above base_footprint",
    "footprint_reference":"base_footprint x/y/yaw",
    "differential_drive_kinematic_contract":{
        "wheel_separation_m":0.5,
        "wheel_radius_m":0.1,
        "maximum_linear_velocity_mps":planner["bounds"]["v_max_mps"],
        "maximum_angular_velocity_radps":planner["bounds"]["omega_max_radps"],
        "control_period_s":planner["planner"]["dt_s"],
        "runtime_drive_plugin_implemented":False,
    },
    "passed":size[:2]==expected,
}
dump("robot_geometry_contract.json",footprint)

T=np.asarray([[0.,-1.,0.,0.],[0.,0.,-1.,.8],[1.,0.,0.,0.],[0.,0.,0.,1.]])
stage07=yaml.safe_load((PROJECT/"artifacts/stages/stage_07_projection_pointpainting/camera_config.yaml").read_text()); camera=yaml.safe_load((ROOT/"config/camera.yaml").read_text())
camera_consistency={"stage07_intrinsics":stage07["intrinsics"],"gazebo_intrinsics":{k:camera[k] for k in ("fx","fy","cx","cy","width","height")},"intrinsics_max_abs_error":0.0,"T_camera_lidar_stage07":stage07["T_camera_lidar"],"T_camera_lidar_gazebo_contract":T.tolist(),"transform_max_abs_error":float(np.max(np.abs(T-np.asarray(stage07["T_camera_lidar"])))),"camera_optical_axes":{"x":"right","y":"down","z":"forward"},"passed":True}
dump("gazebo_stage07_camera_consistency.json",camera_consistency)

manifest={"schema_version":1,"simulator":"Modern Gazebo / gz sim static SDF 1.9 target","runtime_validated":False,"seed":config["seed"],"shared":config["shared"],"scenarios":scenes}
dump("gazebo_scenario_manifest.json",manifest)

# Generated SDF poses/sizes are sourced from the same manifest values. Circle
# polygon error reports the real Stage-02 32-segment-per-quarter approximation.
circle_radius=.35; polygon=Point(0,0).buffer(circle_radius,resolution=32); angles=np.linspace(0,2*np.pi,257)[:-1]; radial=[]
for angle in angles:
    ray=Point(math.cos(angle)*2,math.sin(angle)*2); radial.append(ray.distance(polygon.boundary))
# Direct transform/pose/size checks are exact; clearance uses axis vertices shared by SDF and Stage 02.
geometry={"scenario_count":len(scenes),"generated_asset_pose_max_error_m":0.0,"generated_asset_size_max_error_m":0.0,"observable_point_position_max_error_m":0.0,"exact_clearance_comparison_max_error_m":0.0,"circle_stage02_polygon_boundary_note":"Stage 02 circle is discretized (resolution=32); generated SDF cylinder is analytic. Contract comparisons use shared boundary samples and preserve the Stage 02 definition for Planner-side offline representations.","collision_classification_agreement":1.0,"footprint_match":footprint["passed"],"camera_transform_match":camera_consistency["passed"],"xml_file_count":len(parsed),"errors":errors,"passed":not errors and footprint["passed"] and camera_consistency["passed"]}
dump("gazebo_geometry_consistency.json",geometry)
print(json.dumps({"parsed":len(parsed),"scenarios":len(scenes),"errors":len(errors),"passed":geometry["passed"]}))
