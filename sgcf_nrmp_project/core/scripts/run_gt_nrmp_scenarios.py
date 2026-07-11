#!/usr/bin/env python3
"""Stage-05 exact-Oracle scenario suite, plots, animation and analyses."""

from __future__ import annotations

import json
from pathlib import Path
import time

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Polygon as PolygonPatch
import numpy as np
import yaml

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle, corridor_obstacles, rectangle_obstacle, wall_obstacle
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.planner.geometry_checker import ExactGeometryChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import polyline_path
from sgcf_nrmp.planner.trust_region import TrustRegion
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig

ROOT=Path("sgcf_nrmp_project")
OUT=ROOT/"artifacts/stages/stage_05_gt_nrmp_solver"
CONFIG=yaml.safe_load((ROOT/"core/configs/planner/diff_drive_gt_nrmp.yaml").read_text())
LIDAR=LidarConfig(num_beams=181,range_max=8.)


def draw_case(name,scene,path,result):
    fig,ax=plt.subplots(figsize=(7,4.5))
    for obstacle in scene.obstacles_world:
        ax.add_patch(PolygonPatch(np.asarray(obstacle.exterior.coords),fc="0.35",ec="black"))
    ax.plot(path[:,0],path[:,1],"--",color="tab:blue",label="reference")
    ax.plot(result["states"][:,0],result["states"][:,1],color="tab:orange",lw=2,label="closed loop")
    ax.scatter(result["states"][0,0],result["states"][0,1],c="green",label="start")
    ax.scatter(path[-1,0],path[-1,1],c="red",marker="*",s=100,label="goal")
    ax.set_aspect("equal"); ax.grid(alpha=.2); ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.legend(fontsize=8)
    ax.set_title(f"{name}: {result['statuses'][-1] if result['statuses'] else 'none'}")
    fig.tight_layout(); fig.savefig(OUT/f"{name}.png",dpi=150); plt.close(fig)


def cases():
    empty=ProceduralScene([],(-2,-3,6,3))
    circle=ProceduralScene([circle_obstacle((1.5,0),.35)],(-2,-2,5,2))
    corridor=ProceduralScene(corridor_obstacles((-.5,4.5),0,1.25,.15),(-2,-2,5,2))
    narrow=ProceduralScene(corridor_obstacles((-.5,4.5),0,1.02,.15),(-2,-2,5,2))
    uobs=[wall_obstacle((1,-1),(3,-1),.15),wall_obstacle((3,-1),(3,1.3),.15),wall_obstacle((3,1.3),(1,1.3),.15)]
    ushape=ProceduralScene(uobs,(-2,-2,5,3))
    blocked=ProceduralScene(corridor_obstacles((-.5,4.5),0,.65,.15),(-2,-2,5,2))
    return {
      "no_obstacle_tracking":(empty,polyline_path([(0,0),(4,0)]),60),
      "no_obstacle_turning":(empty,polyline_path([(0,0),(1,0),(2,1),(3,1.5)]),70),
      "single_obstacle_avoidance":(circle,polyline_path([(0,0),(.7,.7),(1.5,1),(2.3,.7),(4,0)]),80),
      "rotated_rectangle":(ProceduralScene([rectangle_obstacle((1.6,0),.7,.9,.55)],(-2,-2,5,2)),polyline_path([(0,0),(.8,.9),(1.8,1.2),(3,.6),(4,0)]),90),
      "corridor_navigation":(corridor,polyline_path([(0,0),(4,0)]),70),
      "narrow_passage":(narrow,polyline_path([(0,0),(4,0)]),70),
      "u_shape_case":(ushape,polyline_path([(0,0),(.5,1.8),(3.5,1.8),(4,0)]),100),
      "infeasible_case":(blocked,polyline_path([(0,0),(4,0)]),35),
    }


def linearization_analysis(scene,path):
    footprint=rectangular_footprint(CONFIG["robot"]["footprint_length_m"],CONFIG["robot"]["footprint_width_m"])
    base=np.asarray([.65,.7,.35]); scan=scene.scan(Pose2D(*base),LIDAR,np.random.default_rng(3)); checker=ExactGeometryChecker(scene,scan,footprint,8.)
    d,g,valid=checker.linearization(base[None,:]); radii=[.01,.03,.05,.10]; yaw_deg=[1,3,5,10]; rng=np.random.default_rng(4); data={}
    for radius,angle in zip(radii,yaw_deg):
        errors=[]
        for _ in range(80):
            delta=np.r_[rng.uniform(-radius,radius,2),rng.uniform(-np.deg2rad(angle),np.deg2rad(angle))]
            actual=checker.recheck((base+delta)[None,:],CONFIG["planner"]["d_safe_m"])["observable"][0]
            errors.append(abs(actual-(d[0]+g[0]@delta)))
        data[f"xy_{radius:.2f}m_yaw_{angle}deg"]={"mae_m":float(np.mean(errors)),"p95_m":float(np.percentile(errors,95)),"gradient_valid":bool(valid[0])}
    (OUT/"linearization_error_by_radius.json").write_text(json.dumps(data,indent=2)+"\n")
    fig,ax=plt.subplots(); labels=list(data); ax.plot(radii,[data[k]["mae_m"] for k in labels],"o-",label="MAE"); ax.plot(radii,[data[k]["p95_m"] for k in labels],"s--",label="P95"); ax.set(xlabel="xy trust radius [m]",ylabel="linearization error [m]"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT/"linearization_error_by_radius.png",dpi=150); plt.close(fig)
    return data


def animate(scene,path,result):
    fig,ax=plt.subplots(figsize=(7,4.5)); footprint=rectangular_footprint(.8,.5)
    def update(i):
        ax.clear()
        for obstacle in scene.obstacles_world: ax.add_patch(PolygonPatch(np.asarray(obstacle.exterior.coords),fc="0.35"))
        ax.plot(path[:,0],path[:,1],"b--",label="reference"); ax.plot(result["states"][:i+1,0],result["states"][:i+1,1],color="tab:orange",label="executed")
        state=result["states"][i]; c,s=np.cos(state[2]),np.sin(state[2]); pts=np.asarray(footprint.exterior.coords); world=pts@np.asarray([[c,s],[-s,c]])+state[:2]; ax.add_patch(PolygonPatch(world,fc="tab:green",alpha=.6))
        scan=scene.scan(Pose2D(*state),LIDAR,np.random.default_rng(i)); ax.scatter(scan.points_world[:,0],scan.points_world[:,1],s=3,c="red",label="observable points")
        if i<len(result["results"]):
            planned=result["results"][i].states; ax.plot(planned[:,0],planned[:,1],"m-",lw=1,label="optimized/nominal"); control=result["controls"][i]; status=result["statuses"][i]; ax.set_title(f"v={control[0]:.2f}, omega={control[1]:.2f}, {status}")
        ax.set(xlim=(-.8,4.7),ylim=(-1.7,2),xlabel="x [m]",ylabel="y [m]"); ax.set_aspect("equal"); ax.legend(fontsize=6,loc="upper left"); ax.grid(alpha=.2)
    animation=FuncAnimation(fig,update,frames=len(result["states"]),interval=120); animation.save(OUT/"gt_nrmp_closed_loop.gif",writer=PillowWriter(fps=8)); plt.close(fig)


def main():
    OUT.mkdir(parents=True,exist_ok=True); results={}; raw={}
    for name,(scene,path,max_steps) in cases().items():
        started=time.perf_counter(); result=run_closed_loop(GTNRMPPlanner(CONFIG),scene,path,CONFIG,LIDAR,max_steps=max_steps,seed=5); elapsed=(time.perf_counter()-started)*1000
        raw[name]=(scene,path,result); metrics=dict(result["metrics"]); metrics["wall_run_ms"]=elapsed; results[name]=metrics; draw_case(name,scene,path,result)
    (OUT/"scenario_metrics.json").write_text(json.dumps(results,indent=2)+"\n")
    linearization_analysis(*raw["single_obstacle_avoidance"][:2])
    trusts={"small":TrustRegion(.10,.15,.20,.40),"medium":TrustRegion.from_dict(CONFIG["trust_region"]),"large":TrustRegion(.5,.5,.6,1.)}; trust_report={}
    scene,path,_=raw["single_obstacle_avoidance"]
    for name,trust in trusts.items():
        cfg=yaml.safe_load(yaml.safe_dump(CONFIG)); cfg["trust_region"]={"xy_m":trust.xy_m,"yaw_rad":trust.yaw_rad,"linear_velocity_mps":trust.linear_velocity_mps,"angular_velocity_radps":trust.angular_velocity_radps}; r=run_closed_loop(GTNRMPPlanner(cfg),scene,path,cfg,LIDAR,max_steps=80,seed=5); trust_report[name]=r["metrics"]
    (OUT/"trust_region_analysis.json").write_text(json.dumps(trust_report,indent=2)+"\n")
    fig,ax=plt.subplots(); names=list(trust_report); ax.bar(names,[trust_report[n]["average_end_to_end_ms"] for n in names]); ax.set(ylabel="mean end-to-end [ms]",title="Trust-region comparison"); fig.tight_layout(); fig.savefig(OUT/"trust_region_comparison.png",dpi=150); plt.close(fig)
    gate=json.loads((OUT/"persistent_qp_gate_results.json").read_text()); solves=[v for case in gate["cases"].values() for v in [case["metrics"]["average_qp_solve_ms"],case["metrics"]["p95_qp_solve_ms"],case["metrics"]["max_qp_solve_ms"]]]
    fig,ax=plt.subplots(); ax.bar(range(len(solves)),solves); ax.axhline(200,color="r",ls="--"); ax.set(ylabel="QP wall time [ms]",title="Mean/P95/max by gate"); fig.tight_layout(); fig.savefig(OUT/"solver_latency_distribution.png",dpi=150); plt.close(fig)
    fig,ax=plt.subplots(); example=raw["single_obstacle_avoidance"][2]; ax.plot([r.objective for r in example["results"]]); ax.set(xlabel="control cycle",ylabel="final SCP objective",title="SCP progress"); ax.grid(); fig.tight_layout(); fig.savefig(OUT/"scp_iteration_progress.png",dpi=150); plt.close(fig)
    animate(*raw["single_obstacle_avoidance"])
    fallback={name:{"fallback_count":m["fallback_count"],"emergency_stop_count":m["emergency_stop_count"],"geometry_recheck_rejections":m["geometry_recheck_rejections"]} for name,m in results.items()}; (OUT/"fallback_test_report.json").write_text(json.dumps(fallback,indent=2)+"\n")


if __name__=="__main__": main()
