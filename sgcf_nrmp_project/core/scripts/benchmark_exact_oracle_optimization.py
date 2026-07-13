#!/usr/bin/env python3
"""Stage-05 exact observable Oracle equivalence, latency, and scenario gates."""

from __future__ import annotations

import json
from pathlib import Path
import time

import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import MultiPoint
from shapely.ops import nearest_points
import yaml

from sgcf_nrmp.data.procedural.dataset_generator import make_scene
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle,corridor_obstacles
from sgcf_nrmp.geometry.footprint import rectangular_footprint,transform_footprint
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import polyline_path
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig

ROOT=Path("sgcf_nrmp_project"); OUT=ROOT/"artifacts/stages/stage_05_gt_nrmp_solver"
PLANNER=yaml.safe_load((ROOT/"core/configs/planner/diff_drive_gt_nrmp.yaml").read_text())
DATA=yaml.safe_load((ROOT/"artifacts/datasets/geometry_v1/config_snapshot.yaml").read_text())
LENGTH=float(PLANNER["robot"]["footprint_length_m"]); WIDTH=float(PLANNER["robot"]["footprint_width_m"]); TRUNC=8.; FOOTPRINT=rectangular_footprint(LENGTH,WIDTH)
LIDAR=LidarConfig(num_beams=181,range_max=TRUNC)


def dump(name,data): (OUT/name).write_text(json.dumps(data,indent=2)+"\n")
def summary(values):
    values=np.asarray(values,float); return {"mean_ms":float(values.mean()),"p50_ms":float(np.percentile(values,50)),"p95_ms":float(np.percentile(values,95)),"p99_ms":float(np.percentile(values,99)),"count":len(values)}
def legacy_distance(points,queries):
    if not len(points): return np.full(len(queries),TRUNC)
    geometry=MultiPoint(points); return np.asarray([min(transform_footprint(FOOTPRINT,Pose2D(*map(float,q))).distance(geometry),TRUNC) for q in queries])
def legacy_distance_gradient(points,queries,eps=.02):
    center=legacy_distance(points,queries); gradients=np.zeros((len(queries),3)); valid=np.ones(len(queries),bool)
    if not len(points): return center,gradients,np.zeros(len(queries),bool)
    for axis,step in enumerate((eps,eps,eps)):
        delta=np.zeros_like(queries); delta[:,axis]=step; plus=legacy_distance(points,queries+delta); minus=legacy_distance(points,queries-delta); gradients[:,axis]=(plus-minus)/(2*step)
        forward=(plus-center)/step; backward=(center-minus)/step; valid &= np.abs(forward-backward)<=.5
    valid &= np.isfinite(gradients).all(1) & (center>1e-10) & (center<TRUNC-1e-10)
    return center,gradients,valid


def equivalence():
    rng=np.random.default_rng(20260712); distance_errors=[]; legacy_all=[]; new_all=[]; collision_matches=[]; nearest_matches=[]; grad_new=[]; grad_old=[]
    valid_gradient_count=0; ambiguity_count=0
    for scene_id in range(100):
        scene_rng=np.random.default_rng(9000+scene_id); scene=make_scene(scene_id,DATA,scene_rng); scan=scene.scan(Pose2D(0,0,0),LIDAR,scene_rng); points=np.asarray(scan.points_world)
        queries=rng.uniform([-5,-5,-np.pi],[5,5,np.pi],(100,3)); oracle=BatchedRectangleObservableOracle(points,np.ones(len(points),bool),LENGTH,WIDTH,TRUNC)
        new,nearest=oracle.distance(queries); old=legacy_distance(points,queries); _,gradient,valid,_=oracle.distance_and_gradient(queries); _,finite_gradient,legacy_valid=legacy_distance_gradient(points,queries)
        errors=np.abs(new-old); distance_errors.extend(errors); legacy_all.extend(old); new_all.extend(new); collision_matches.extend((new<=1e-12)==(old<=1e-12))
        if len(points):
            geometry=MultiPoint(points)
            for q,index,distance in zip(queries,nearest,new):
                footprint=transform_footprint(FOOTPRINT,Pose2D(*map(float,q))); point=np.asarray(nearest_points(footprint,geometry)[1].coords[0]); reference=int(np.argmin(np.linalg.norm(points-point,axis=1)))
                # Nearest identity is meaningful only away from collisions/ties.
                if distance>1e-10: nearest_matches.append(reference==int(index))
        selected=valid & legacy_valid & (new>1e-6)
        valid_gradient_count+=int(selected.sum()); ambiguity_count+=int((~valid).sum()); grad_new.extend(gradient[selected]); grad_old.extend(finite_gradient[selected])
    distance_errors=np.asarray(distance_errors); grad_new=np.asarray(grad_new); grad_old=np.asarray(grad_old); grad_error=np.abs(grad_new-grad_old)
    translation_dot=np.sum(grad_new[:,:2]*grad_old[:,:2],axis=1); translation_norm=np.linalg.norm(grad_new[:,:2],axis=1)*np.linalg.norm(grad_old[:,:2],axis=1); cosine=translation_dot/np.maximum(translation_norm,1e-12)
    distance_report={"scene_count":100,"queries_per_scene":100,"sample_count":10000,"maximum_absolute_distance_error_m":float(distance_errors.max()),"mean_absolute_distance_error_m":float(distance_errors.mean()),"p95_absolute_distance_error_m":float(np.percentile(distance_errors,95)),"collision_agreement":float(np.mean(collision_matches)),"nearest_obstacle_agreement":float(np.mean(nearest_matches)),"pass":bool(distance_errors.max()<=1e-9 and np.mean(collision_matches)==1.)}
    gradient_report={"compared_sample_count":valid_gradient_count,"ambiguous_or_invalid_count":ambiguity_count,"gx_mae":float(grad_error[:,0].mean()),"gy_mae":float(grad_error[:,1].mean()),"yaw_mae":float(grad_error[:,2].mean()),"translation_cosine_similarity_mean":float(np.mean(cosine)),"gradient_sign_disagreement":float(np.mean(np.sign(grad_new)!=np.sign(grad_old))),"nan_or_inf_count":int(np.size(grad_new)-np.isfinite(grad_new).sum()),"pass":bool(np.isfinite(grad_new).all() and np.mean(cosine)>.999)}
    dump("oracle_equivalence_report.json",distance_report); dump("observable_oracle_equivalence.json",distance_report); dump("oracle_gradient_equivalence.json",gradient_report)
    fig,ax=plt.subplots(); ax.scatter(legacy_all,new_all,s=2,alpha=.25); limits=[0,TRUNC]; ax.plot(limits,limits,"r--"); ax.set(xlabel="legacy Shapely distance [m]",ylabel="batched exact distance [m]",title="Observable distance equivalence"); fig.tight_layout(); fig.savefig(OUT/"distance_equivalence_scatter.png",dpi=150); plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(10,3)); names=("gx","gy","yaw");
    for i,ax in enumerate(axes): ax.scatter(grad_old[:,i],grad_new[:,i],s=2,alpha=.2); ax.set(title=names[i],xlabel="legacy FD",ylabel="exact autograd")
    fig.tight_layout(); fig.savefig(OUT/"gradient_equivalence.png",dpi=150); plt.close(fig)
    return distance_report,gradient_report


def oracle_benchmark():
    rng=np.random.default_rng(77); points=rng.uniform(-6,6,(181,2)); report={"device":"cpu","warmup":3,"repeats":20,"batches":{}}
    for count in (1,10,12,32,128):
        queries=rng.uniform([-4,-4,-np.pi],[4,4,np.pi],(count,3)); oracle=BatchedRectangleObservableOracle(points,np.ones(len(points),bool),LENGTH,WIDTH,TRUNC)
        for _ in range(3): oracle.distance(queries); oracle.distance_and_gradient(queries); legacy_distance(points,queries)
        samples={key:[] for key in ("legacy_distance","legacy_distance_finite_difference","batched_exact_distance","batched_exact_autograd")}
        for _ in range(20):
            start=time.perf_counter(); legacy_distance(points,queries); samples["legacy_distance"].append((time.perf_counter()-start)*1000)
            start=time.perf_counter(); legacy_distance_gradient(points,queries); samples["legacy_distance_finite_difference"].append((time.perf_counter()-start)*1000)
            start=time.perf_counter(); oracle.distance(queries); samples["batched_exact_distance"].append((time.perf_counter()-start)*1000)
            start=time.perf_counter(); oracle.distance_and_gradient(queries); samples["batched_exact_autograd"].append((time.perf_counter()-start)*1000)
        report["batches"][str(count)]={key:summary(value) for key,value in samples.items()}
    dump("oracle_benchmark_comparison.json",report)
    counts=np.asarray([1,10,12,32,128]); fig,ax=plt.subplots(figsize=(7,4))
    for key,label in (("legacy_distance_finite_difference","legacy + FD"),("batched_exact_autograd","batched + autograd")): ax.plot(counts,[report["batches"][str(x)][key]["p95_ms"] for x in counts],"o-",label=label)
    ax.set(xlabel="query count",ylabel="P95 [ms]",title="Exact observable Oracle before/after"); ax.legend(); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(OUT/"oracle_latency_before_after.png",dpi=150); plt.close(fig)
    return report


def scenario_gate():
    cases={
      "single_obstacle":(ProceduralScene([circle_obstacle((1.5,0),.35)],(-2,-2,5,2)),polyline_path([(0,0),(.7,.7),(1.5,1),(2.3,.7),(4,0)]),80),
      "corridor":(ProceduralScene(corridor_obstacles((-.5,4.5),0,1.25,.15),(-2,-2,5,2)),polyline_path([(0,0),(4,0)]),70),
      "narrow_passage":(ProceduralScene(corridor_obstacles((-.5,4.5),0,1.02,.15),(-2,-2,5,2)),polyline_path([(0,0),(4,0)]),70),
    }; report={}; visualization=[]
    for name,(scene,path,steps) in cases.items():
        result=run_closed_loop(GTNRMPPlanner(PLANNER),scene,path,PLANNER,LIDAR,max_steps=steps,seed=5); timing=result["timing_samples_ms"]
        item={"metrics":result["metrics"],"latency":{key:summary(value) for key,value in timing.items()}}
        item["online_p95_under_100ms"]=item["latency"]["online_equivalent_planner_ms"]["p95_ms"]<100.; report[name]=item
        start=time.perf_counter(); fig,ax=plt.subplots(); ax.plot(path[:,0],path[:,1],"--"); ax.plot(result["states"][:,0],result["states"][:,1]); ax.set_aspect("equal"); fig.tight_layout(); fig.savefig(OUT/f"{name}_oracle_optimized.png",dpi=150); plt.close(fig); visualization.append((time.perf_counter()-start)*1000)
        dump(f"{name}_latency_after.json",item)
    report["visualization_latency"]=summary(visualization); report["all_online_p95_under_100ms"]=all(report[name]["online_p95_under_100ms"] for name in cases); dump("planner_latency_breakdown.json",report); dump("offline_world_evaluation_report.json",{name:report[name]["latency"]["offline_world_evaluation_ms"] for name in cases}); dump("oracle_profile_after.json",report)
    before={"source":"pre-optimization Stage-05 report","corridor":{"online_mixed_mean_ms":310.87,"online_mixed_p95_ms":364.44},"narrow_passage":{"online_mixed_mean_ms":320.72,"online_mixed_p95_ms":374.64},"note":"Legacy timing mixed observable Shapely/finite differences with complete-world scene.label evaluation; plotting/GIF were outside cycle timing."}; dump("oracle_profile_before.json",before); dump("latency_breakdown_before_after.json",{"before":before,"after":report})
    names=list(cases); components=("observable_distance_gradient_ms","parameter_update_ms","solve_wall_ms","observable_recheck_ms")
    fig,ax=plt.subplots(figsize=(8,4)); bottom=np.zeros(3)
    for key in components:
        values=np.asarray([report[name]["latency"][key]["mean_ms"] for name in names]); ax.bar(names,values,bottom=bottom,label=key); bottom+=values
    ax.set(ylabel="mean latency [ms]",title="Online latency breakdown"); ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(OUT/"latency_breakdown.png",dpi=150); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4)); ax.bar(names,[report[name]["latency"]["online_equivalent_planner_ms"]["p95_ms"] for name in names]); ax.axhline(100,color="r",ls="--"); ax.set(ylabel="online P95 [ms]",title="Planner latency after exact Oracle optimization"); fig.tight_layout(); fig.savefig(OUT/"planner_latency_distribution_after.png",dpi=150); plt.close(fig)
    return report


def main():
    OUT.mkdir(parents=True,exist_ok=True); distance,gradient=equivalence()
    if not distance["pass"] or not gradient["pass"]: raise SystemExit("Oracle equivalence gate failed")
    benchmark=oracle_benchmark(); scenarios=scenario_gate()
    print(json.dumps({"distance":distance,"gradient":gradient,"batch_12":benchmark["batches"]["12"],"scenario_gate":{name:data["online_p95_under_100ms"] for name,data in scenarios.items() if isinstance(data,dict) and "online_p95_under_100ms" in data}},indent=2))


if __name__=="__main__": main()
