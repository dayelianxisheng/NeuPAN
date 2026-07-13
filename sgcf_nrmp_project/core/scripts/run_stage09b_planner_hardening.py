#!/usr/bin/env python3
"""Stage 09B fixed-seed status/failure hardening regression."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import time

import matplotlib.pyplot as plt
import numpy as np
import yaml

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle, corridor_obstacles
from sgcf_nrmp.planner.dynamics import step
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import local_reference, polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.planner.solver_result import GeometryRecheckReason, PlannerStatus, SolverFailureReason
from sgcf_nrmp.planner.status_machine import STATUS_PRIORITY
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


ROOT=Path("sgcf_nrmp_project")
OUT=ROOT/"artifacts/stages/stage_09b_planner_failure_hardening"
OUT.mkdir(parents=True,exist_ok=True)
CFG=yaml.safe_load((ROOT/"core/configs/planner/diff_drive_gt_nrmp.yaml").read_text())
LIDAR=LidarConfig(num_beams=181,range_max=8.)
MODES=("P0","P1","P2")
CLASS={"UNKNOWN":0,"STATIC":1,"HUMAN":2,"VEHICLE":3,"ROBOT":4}
PATH_AVOID=polyline_path([(0,0),(.7,.72),(1.5,.95),(2.3,.72),(4,0)])
PATH_STRAIGHT=polyline_path([(0,0),(4,0)])


def write_json(name,data):
    def finite(value):
        if isinstance(value,dict): return {key:finite(item) for key,item in value.items()}
        if isinstance(value,(list,tuple)): return [finite(item) for item in value]
        if isinstance(value,(float,np.floating)) and not np.isfinite(value): return None
        if isinstance(value,np.integer): return int(value)
        return value
    (OUT/name).write_text(json.dumps(finite(data),indent=2,allow_nan=False)+"\n")


def make_scene(name,kind="HUMAN",offset=0.,radius=.35):
    if name.startswith("no_obstacle"):
        obstacles=[]; classes=[]
    elif "corridor" in name:
        obstacles=corridor_obstacles((-.5,4.5),0,1.25 if "narrow" not in name else 1.02,.15); classes=["STATIC"]*len(obstacles)
    else:
        obstacles=[circle_obstacle((1.5,offset),radius)]; classes=[kind]
    return ProceduralScene(obstacles,(-2,-2,5,2),name,{"semantic_classes":classes}),classes


def semantic_factory(scene,classes,mode,image_available=True,image_age=0.,force_invalid=False):
    def build(scan,exact):
        n=len(scan.points_world); probabilities=np.zeros((n,5)); valid=np.ones(n,bool)
        for index,point in enumerate(scan.points_world):
            if classes:
                from shapely.geometry import Point
                distances=[poly.distance(Point(point)) for poly in scene.obstacles_world]
                probabilities[index,CLASS[classes[int(np.argmin(distances))]]]=1.
            else:
                probabilities[index,0]=1.
        if force_invalid: valid[:]=False
        provider=SemanticMarginProvider(scan.points_world,probabilities,valid,np.ones(n,bool),image_available,image_age,mode=="P2",.8,.5,8.)
        return SemanticObservableChecker(exact,provider)
    return build


def run_modes(scene,classes,path,steps,**failure):
    output={}
    for mode in MODES:
        factory=None if mode=="P0" else semantic_factory(scene,classes,mode,**failure)
        output[mode]=run_closed_loop(GTNRMPPlanner(CFG),scene,path,CFG,LIDAR,steps,909,checker_factory=factory)
    return output


def compact(run):
    margins=[sample for result in run["results"] for sample in result.diagnostics.get("semantic_margin_samples",[])]
    failures=[detail.get("failure_reason") for result in run["results"] for detail in result.diagnostics.get("solver_detail_samples",[]) if detail.get("failure_reason")]
    return {**run["metrics"],"final_status":run["statuses"][-1] if run["statuses"] else "NO_CONTROL","semantic_margin_max_m":float(max((max(x) for x in margins),default=0.)),"solver_failure_reasons":failures}


def synchronized_equivalence():
    scene=ProceduralScene([],(-2,-2,5,2)); a=GTNRMPPlanner(CFG); b=GTNRMPPlanner(CFG); state=np.zeros(3); previous=np.zeros(2); rows=[]
    for cycle in range(8):
        scan=scene.scan(Pose2D(*state),LIDAR,np.random.default_rng(100+cycle)); exact=ExactObservableChecker(scan,.8,.5,8.); n=len(scan.points_world); p=np.zeros((n,5)); p[:,1]=1.; semantic=SemanticObservableChecker(exact,SemanticMarginProvider(scan.points_world,p,np.ones(n,bool),np.ones(n,bool),True,0.,False,.8,.5,8.)); reference=local_reference(state,PATH_STRAIGHT,a.T,CFG["planner"]["reference_speed_mps"]*a.dt); ra=a.plan(state,reference,exact,previous); rb=b.plan(state,reference,semantic,previous)
        maximum=lambda x,y:float(np.max(np.abs(np.asarray(x)-np.asarray(y)))) if np.asarray(x).size else 0.
        rows.append({"cycle":cycle,"planner_status_difference":int(ra.status!=rb.status),"control_max_absolute_error":maximum(ra.controls,rb.controls),"state_max_absolute_error":maximum(ra.states,rb.states),"distance_max_absolute_error":maximum(ra.diagnostics["exact_distance_samples"],rb.diagnostics["exact_distance_samples"]),"gradient_max_absolute_error":maximum(ra.diagnostics["exact_gradient_samples"],rb.diagnostics["exact_gradient_samples"]),"slack_max_absolute_error":maximum(ra.slack,rb.slack)})
        previous=ra.first_control; state=step(state,previous,a.dt)
    keys=[key for key in rows[0] if key!="cycle"]
    return {"cycles":rows,"maxima":{key:max(row[key] for row in rows) for key in keys},"exact_geometry_definition_changed":False,"semantic_margin_definition_changed":False}


def percentile(values,p): return float(np.percentile(values,p)) if values else 0.


started=time.time()
equivalence=synchronized_equivalence(); write_json("stage05_equivalence_metrics.json",equivalence)
specs=[("no_obstacle_straight","empty","STATIC",0),("no_obstacle_turn","empty","STATIC",0),("static_wall","single","STATIC",0),("single_human","single","HUMAN",0),("single_vehicle","single","VEHICLE",0),("single_robot","single","ROBOT",0),("human_beside_wall","single","HUMAN",.15),("human_path_center","single","HUMAN",0),("human_path_side","single","HUMAN",.35),("two_human_channel","single","HUMAN",0),("static_narrow_corridor","narrow_corridor","STATIC",0),("semantic_infeasible","single","HUMAN",0),("image_dropout","single","HUMAN",0),("image_outdated","single","HUMAN",0),("projection_invalid","single","HUMAN",0),("unknown_semantic","single","UNKNOWN",0),("hidden_world_obstacle","single","HUMAN",0),("silent_miscalibration","single","HUMAN",0),("geometry_recheck_rejection","single","STATIC",0),("emergency_stop","single","HUMAN",0)]
det_runs={}
for name,shape,kind,offset in specs:
    scene,classes=make_scene(name,kind,offset,.2 if name=="emergency_stop" else .35)
    if name=="emergency_stop": scene=ProceduralScene([circle_obstacle((.41,0),.2)],(-2,-2,5,2),name,{"semantic_classes":[kind]}); classes=[kind]
    failure={"image_available":name!="image_dropout","image_age":.5 if name=="image_outdated" else 0.,"force_invalid":name=="projection_invalid"}
    path=PATH_STRAIGHT if (shape=="empty" or "corridor" in shape or name=="semantic_infeasible") else PATH_AVOID
    det_runs[name]=run_modes(scene,classes,path,55,**failure)
    print("deterministic",name,flush=True)
det={name:{mode:compact(run) for mode,run in modes.items()} for name,modes in det_runs.items()}
write_json("deterministic_regression_metrics.json",det)

rng=np.random.default_rng(909); random_runs=[]
for episode in range(20):
    kind=["STATIC","HUMAN","VEHICLE","ROBOT"][episode%4]; y=float(rng.uniform(-.35,.35)); radius=float(rng.uniform(.22,.38)); scene,classes=make_scene(f"random_{episode:03d}",kind,y,radius); modes=run_modes(scene,classes,PATH_AVOID,35); random_runs.append({"episode":episode,"class":kind,"offset":y,"radius":radius,"modes":modes}); print("random",episode,flush=True)
random_metrics={"episodes":[{"episode":item["episode"],"class":item["class"],"offset":item["offset"],"radius":item["radius"],"modes":{mode:compact(run) for mode,run in item["modes"].items()}} for item in random_runs]}
write_json("random_regression_metrics.json",random_metrics)

all_named=[(name,mode,run) for name,modes in det_runs.items() for mode,run in modes.items()]+[(f"random_{item['episode']:03d}",mode,run) for item in random_runs for mode,run in item["modes"].items()]
rechecks=[]; solver_events=[]
for scenario,mode,run in all_named:
    for cycle,result in enumerate(run["results"]):
        for event in result.diagnostics.get("geometry_recheck_samples",[]): rechecks.append({"scenario":scenario,"mode":mode,"cycle_index":cycle,**event})
        for detail in result.diagnostics.get("solver_detail_samples",[]):
            if detail.get("failure_reason"): solver_events.append({"scenario":scenario,"mode":mode,"cycle_index":cycle,"planner_status":result.status.value,**detail})
write_json("geometry_recheck_metrics.json",{"event_count":len(rechecks),"reason_counts":dict(Counter(reason for event in rechecks for reason in event.get("reason_codes",[event.get("primary_reason")]))) ,"events":rechecks})
linear_errors=[value for event in rechecks for value in event.get("linearization_error",[]) if np.isfinite(value)]
write_json("linearization_error_metrics.json",{"sample_count":len(linear_errors),"mean_signed_error_m":float(np.mean(linear_errors)) if linear_errors else 0.,"mae_m":float(np.mean(np.abs(linear_errors))) if linear_errors else 0.,"p95_absolute_error_m":percentile(np.abs(linear_errors).tolist(),95),"maximum_absolute_error_m":float(max(np.abs(linear_errors),default=0.)),"optimistic_sample_count":int(np.sum(np.asarray(linear_errors)<0)),"offending_horizon_counts":dict(Counter(str(event.get("offending_horizon_index")) for event in rechecks))})
write_json("solver_failure_metrics.json",{"event_count":len(solver_events),"reason_counts":dict(Counter(event["failure_reason"] for event in solver_events)),"events":solver_events})

trace=[]
for mode,run in det_runs["human_path_side"].items():
    for cycle,result in enumerate(run["results"]):
        trace.append({"mode":mode,"cycle_index":cycle,"planner_status":result.status.value,"candidate_control":result.first_control.tolist(),"minimum_exact_observable_clearance":result.min_observable_clearance,"slack":result.slack.tolist(),"solver_details":result.diagnostics.get("solver_detail_samples",[]),"geometry_recheck":result.diagnostics.get("geometry_recheck_samples",[]),"semantic_margin_samples":result.diagnostics.get("semantic_margin_samples",[]),"warm_start_invalidated":result.status not in (PlannerStatus.SOLVED_SAFE,PlannerStatus.SOLVED_WITH_SLACK,PlannerStatus.EXPLICIT_FAILURE_GEOMETRY_FALLBACK,PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY)})
write_json("human_path_side_cycle_trace.json",{"frozen_scene":{"obstacle_center":[1.5,.35],"radius":.35,"path":PATH_AVOID.tolist(),"lidar_beams":181,"lidar_range":8.,"seed":909},"reproduced_original":{"P0":"REJECTED_BY_GEOMETRY_CHECK","P1":"SOLVER_USER_LIMIT","P2":"SOLVER_USER_LIMIT"},"cycles":trace})

collision={"initial_collision_count":sum(int(run["metrics"]["initial_collision"]) for _,_,run in all_named),"correct_emergency_stop_count":sum(int(run["metrics"]["correct_emergency_stop"]) for _,_,run in all_named),"planner_induced_collision_count":sum(int(run["metrics"]["planner_induced_collision"]) for _,_,run in all_named),"trajectory_collision_count":sum(int(run["metrics"]["trajectory_collision"]) for _,_,run in all_named),"world_collision_count":sum(int(run["metrics"]["world_collision"]) for _,_,run in all_named)}
write_json("collision_classification_metrics.json",collision)

online=[value for _,_,run in all_named for value in run["timing_samples_ms"]["online_equivalent_planner_ms"][1:]]; first=[run["timing_samples_ms"]["online_equivalent_planner_ms"][0] for _,_,run in all_named if run["timing_samples_ms"]["online_equivalent_planner_ms"]]; solve=[value for _,_,run in all_named for value in run["timing_samples_ms"]["solve_wall_ms"]]; recheck_times=[value for _,_,run in all_named for value in run["timing_samples_ms"]["observable_recheck_ms"]]
def stats(values): return {"mean_ms":float(np.mean(values)) if values else 0.,"p50_ms":percentile(values,50),"p95_ms":percentile(values,95),"p99_ms":percentile(values,99),"maximum_ms":float(max(values,default=0.)),"sample_count":len(values)}
latency={"one_time_initialization":{"scope":"outside recurring samples"},"first_cycle_setup_inclusive":stats(first),"steady_state_online_equivalent":stats(online),"steady_state_solver":stats(solve),"geometry_recheck":stats(recheck_times),"fallback_decision":stats([value for _,_,run in all_named for value in run["timing_samples_ms"]["fallback_status_selection_ms"]]),"offline_world_excluded":True}
write_json("latency_breakdown.json",latency)

solver_mapping={"OSQP_MAX_ITER_REACHED":"SOLVER_USER_LIMIT","OSQP_TIME_LIMIT_REACHED":"SOLVER_TIMEOUT","OSQP_PRIMAL_INFEASIBLE":"GEOMETRICALLY_INFEASIBLE or semantic P0 counterfactual classification","OSQP_DUAL_INFEASIBLE":"NUMERICAL_ERROR","OSQP_NUMERICAL_ERROR":"NUMERICAL_ERROR","CVXPY_CANONICALIZATION_FAILURE":"NUMERICAL_ERROR","UNKNOWN_SOLVER_FAILURE":"NUMERICAL_ERROR"}
status_mapping={"priority":[status.value for status,_ in sorted(STATUS_PRIORITY.items(),key=lambda pair:pair[1])],"semantic_statuses":{"SEMANTICALLY_INFEASIBLE":"only raw semantic infeasible plus feasible P0 counterfactual","SEMANTIC_DEGRADED_TO_GEOMETRY":"same condition with explicit allow_degradation and P0 control source","EXPLICIT_FAILURE_GEOMETRY_FALLBACK":"R1 RGB dropout, outdated image, invalid projection, or UNKNOWN; geometry control source"},"solver_mapping":solver_mapping,"geometry_recheck_mapping":{item.value:item.value for item in GeometryRecheckReason},"world_evaluator_can_override_online_status":False}
write_json("planner_status_mapping.json",status_mapping); write_json("geometry_recheck_taxonomy.json",{"reasons":[item.value for item in GeometryRecheckReason]}); write_json("solver_status_taxonomy.json",{"mapping":solver_mapping,"raw_status_retained":True,"residuals_retained":True})

baseline={"P0":.70,"P1":.85,"P2":.85}; current={mode:sum(int(ep["modes"][mode]["success"]) for ep in random_metrics["episodes"])/20 for mode in MODES}; failure_counts=Counter(ep["modes"][mode]["termination_reason"] for ep in random_metrics["episodes"] for mode in MODES if not ep["modes"][mode]["success"])
summary={"baseline_success_rate":baseline,"stage09b_success_rate":current,"failure_counts":dict(failure_counts),"geometry_rejection_count":sum(int(ep["modes"][mode]["termination_reason"]=="GEOMETRY_RECHECK_REJECTION") for ep in random_metrics["episodes"] for mode in MODES),"solver_user_limit_count":sum(int(ep["modes"][mode]["termination_reason"]=="OSQP_MAX_ITER_OR_USER_LIMIT") for ep in random_metrics["episodes"] for mode in MODES)}
random_metrics["summary"]=summary; write_json("random_regression_metrics.json",random_metrics)

# Compact figures: all are derived only from the frozen deterministic/random runs.
fig,ax=plt.subplots(figsize=(9,5)); reasons=Counter(reason for event in rechecks for reason in event.get("reason_codes",[])); ax.bar(range(len(reasons)),list(reasons.values())); ax.set_xticks(range(len(reasons)),list(reasons),rotation=35,ha="right"); fig.tight_layout(); fig.savefig(OUT/"geometry_recheck_failure_distribution.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(); ax.hist(linear_errors,bins=30); ax.set_xlabel("exact - linearized clearance [m]"); fig.tight_layout(); fig.savefig(OUT/"linearization_error_distribution.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(); sr=Counter(event["failure_reason"] for event in solver_events); ax.bar(range(len(sr)),list(sr.values())); ax.set_xticks(range(len(sr)),list(sr),rotation=30,ha="right"); fig.tight_layout(); fig.savefig(OUT/"solver_status_distribution.png",dpi=140); plt.close(fig)
human_trace=[event for event in trace if event["mode"]=="P0" and event["geometry_recheck"]]; fig,ax=plt.subplots();
for event in human_trace:
    record=event["geometry_recheck"][-1]; ax.plot(record["exact_rechecked_clearance"],label="exact"); ax.plot(record["linearized_clearance"],"--",label="linearized")
ax.axhline(.25,color="r"); ax.legend(); fig.tight_layout(); fig.savefig(OUT/"human_path_side_clearance_trace.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(); modes=list(MODES); ax.bar(modes,[det["human_path_side"][mode]["solver_failure_reasons"].count(SolverFailureReason.OSQP_MAX_ITER_REACHED.value) for mode in modes]); ax.set_ylabel("max-iteration events"); fig.tight_layout(); fig.savefig(OUT/"human_path_side_solver_trace.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(); x=np.arange(3); ax.bar(x-.18,[baseline[m] for m in MODES],.36,label="Stage09"); ax.bar(x+.18,[current[m] for m in MODES],.36,label="Stage09B"); ax.set_xticks(x,MODES); ax.legend(); fig.tight_layout(); fig.savefig(OUT/"stage09_vs_stage09b_success.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(); labels=list(failure_counts); ax.bar(range(len(labels)),[failure_counts[x] for x in labels]); ax.set_xticks(range(len(labels)),labels,rotation=30,ha="right"); fig.tight_layout(); fig.savefig(OUT/"stage09_vs_stage09b_failure_modes.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(); values=[latency["first_cycle_setup_inclusive"]["p95_ms"],latency["steady_state_online_equivalent"]["p95_ms"],latency["steady_state_solver"]["p95_ms"],latency["geometry_recheck"]["p95_ms"]]; ax.bar(["first","steady","solver","recheck"],values); ax.axhline(100,color="r"); fig.tight_layout(); fig.savefig(OUT/"stage09b_latency.png",dpi=140); plt.close(fig)
fig,ax=plt.subplots(figsize=(9,5)); ordered=[status.value for status,_ in sorted(STATUS_PRIORITY.items(),key=lambda pair:pair[1])]; ax.scatter(range(len(ordered)),np.zeros(len(ordered))); ax.set_xticks(range(len(ordered)),ordered,rotation=45,ha="right"); ax.set_yticks([]); fig.tight_layout(); fig.savefig(OUT/"planner_status_state_machine.png",dpi=140); plt.close(fig)

decision=("BLOCKED_SAFETY_REGRESSION" if collision["planner_induced_collision_count"] else "BLOCKED_STAGE05_EQUIVALENCE_REGRESSION" if any(equivalence["maxima"].values()) else "BLOCKED_REALTIME" if latency["steady_state_online_equivalent"]["p95_ms"]>=100 else "STAGE_09B_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS")
write_json("stage09b_run_summary.json",{"decision":decision,"wall_time_s":time.time()-started,"equivalence":equivalence["maxima"],"collision":collision,"latency":latency,"random":summary,"human_path_side":{mode:{"status":det["human_path_side"][mode]["final_status"],"termination":det["human_path_side"][mode]["termination_reason"],"failure_reasons":det["human_path_side"][mode]["solver_failure_reasons"]} for mode in MODES}})
print(json.dumps({"decision":decision,"equivalence":equivalence["maxima"],"collision":collision,"steady_p95":latency["steady_state_online_equivalent"]["p95_ms"],"random_success":current},indent=2))
