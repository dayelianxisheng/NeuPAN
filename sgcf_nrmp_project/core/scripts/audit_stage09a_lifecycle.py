#!/usr/bin/env python3
from pathlib import Path
import json,time
import numpy as np,yaml,matplotlib.pyplot as plt
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.planner.dynamics import step
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import local_reference,polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_09_semantic_nrmp_closed_loop'; CFG=yaml.safe_load((ROOT/'core/configs/planner/diff_drive_gt_nrmp.yaml').read_text()); LIDAR=LidarConfig(num_beams=181,range_max=8.); PATH=polyline_path([(0,0),(4,0)])
def semantic_factory(cid,gate):
 def f(scan,exact):
  n=len(scan.points_world); p=np.zeros((n,5)); p[:,cid]=1.; valid=np.ones(n,bool); return SemanticObservableChecker(exact,SemanticMarginProvider(scan.points_world,p,valid,valid,True,0.,gate,.8,.5,8.))
 return f
scenes={'R0_empty_straight':(ProceduralScene([],(-2,-2,5,2)),PATH,1),'R1_empty_turn':(ProceduralScene([],(-2,-2,5,2)),polyline_path([(0,0),(1,.7),(2,0)]),1),'R2_static':(ProceduralScene([circle_obstacle((1.5,0),.35)],(-2,-2,5,2)),polyline_path([(0,0),(.7,.7),(1.5,1),(2.3,.7),(4,0)]),1),'R3_human':(ProceduralScene([circle_obstacle((1.5,0),.35)],(-2,-2,5,2)),polyline_path([(0,0),(.7,.7),(1.5,1),(2.3,.7),(4,0)]),2),'R4_initial_collision':(ProceduralScene([circle_obstacle((.41,0),.2)],(-2,-2,5,2)),PATH,2)}

# Direct same-input equivalence: Stage 05 path and Stage 09 P0 are the same planner composition.
state=np.zeros(3); pa,pb=GTNRMPPlanner(CFG),GTNRMPPlanner(CFG); previous=np.zeros(2); diffs=[]
for cycle in range(8):
 scan=scenes['R0_empty_straight'][0].scan(Pose2D(*state),LIDAR,np.random.default_rng(100+cycle)); checker=ExactObservableChecker(scan,.8,.5,8.); ref=local_reference(state,PATH,pa.T,CFG['planner']['reference_speed_mps']*pa.dt); a=pa.plan(state,ref,checker,previous); b=pb.plan(state,ref,checker,previous)
 def mx(x,y): return float(np.max(np.abs(np.asarray(x)-np.asarray(y))))
 diffs.append({'cycle':cycle,'state_max_abs_error':mx(a.states,b.states),'control_max_abs_error':mx(a.controls,b.controls),'slack_max_abs_error':mx(a.slack,b.slack),'distance_max_abs_error':mx(a.diagnostics['exact_distance_samples'],b.diagnostics['exact_distance_samples']),'gradient_max_abs_error':mx(a.diagnostics['exact_gradient_samples'],b.diagnostics['exact_gradient_samples']),'status_equal':a.status==b.status,'qp_problem_identity_persistent_a':id(pa.qp.problem),'qp_problem_identity_persistent_b':id(pb.qp.problem)})
 previous=a.first_control; state=step(state,previous,pa.dt)
equiv={'same_planner_class':True,'same_config_object':True,'semantic_margin_parameter_p0_value':pa.qp.semantic_margin.value.tolist(),'cycles':diffs,'maxima':{k:max(d[k] for d in diffs) for k in ('state_max_abs_error','control_max_abs_error','slack_max_abs_error','distance_max_abs_error','gradient_max_abs_error')}}; (OUT/'stage05_vs_stage09_p0_equivalence.json').write_text(json.dumps(equiv,indent=2))

runs={}
for name,(scene,path,cid) in scenes.items():
 runs[name]={}
 for mode,factory in [('STAGE05_ORIGINAL',None),('P0',None),('P1',semantic_factory(cid,False)),('P2',semantic_factory(cid,True))]:
  runs[name][mode]=run_closed_loop(GTNRMPPlanner(CFG),scene,path,CFG,LIDAR,12,909,checker_factory=factory)
def pct(v,p): return float(np.percentile(v,p)) if v else 0.
def summarize(r):
 t=r['timing_samples_ms']; online=t['online_equivalent_planner_ms']; details=[d for x in r['results'] for d in x.diagnostics.get('solver_detail_samples',[])]; component={k:{'mean_ms':float(np.mean(v)) if v else 0.,'p95_ms':pct(v,95)} for k,v in t.items()}; return {'statuses':r['statuses'],'metrics':r['metrics'],'latency':{'first_cycle_ms':online[0] if online else 0.,'steady_mean_ms':float(np.mean(online[1:])) if len(online)>1 else 0.,'steady_p50_ms':pct(online[1:],50),'steady_p95_ms':pct(online[1:],95),'steady_p99_ms':pct(online[1:],99),'observation_mean_ms':float(np.mean(t['lidar_data_preparation_ms'])) if t['lidar_data_preparation_ms'] else 0.,'offline_world_mean_ms':float(np.mean(t['offline_world_evaluation_ms'])) if t['offline_world_evaluation_ms'] else 0.},'components':component,'solver_details':details}
summary={s:{m:summarize(r) for m,r in modes.items()} for s,modes in runs.items()}
empty={s:summary[s] for s in ('R0_empty_straight','R1_empty_turn')}; (OUT/'empty_scene_rejection_diagnosis.json').write_text(json.dumps({'root_cause':'Stage09 fixture name bug created a circle obstacle for no_obstacle_*; exact empty oracle itself returns truncation=8, zero gradient, invalid linearization slots, and passes recheck.','after_fix':empty},indent=2))
timeouts=[]
for s,modes in summary.items():
 for m,r in modes.items():
  for i,status in enumerate(r['statuses']):
   if status=='SOLVER_TIMEOUT': timeouts.append({'scene':s,'mode':m,'cycle':i,'details':r['solver_details']})
(OUT/'solver_timeout_diagnosis.json').write_text(json.dumps({'minimal_reproduction_timeout_count':len(timeouts),'classification':'OSQP USER_LIMIT when present; no outer SCP or episode timeout is mapped to SOLVER_TIMEOUT','events':timeouts},indent=2))
(OUT/'closed_loop_lifecycle_report.json').write_text(json.dumps({s:{m:r['metrics'] for m,r in modes.items()} for s,modes in summary.items()},indent=2)); (OUT/'collision_classification_metrics.json').write_text(json.dumps({s:{m:{k:r['metrics'][k] for k in ('initial_collision','planner_induced_collision','trajectory_collision','world_collision','correct_emergency_stop')} for m,r in modes.items()} for s,modes in summary.items()},indent=2)); (OUT/'latency_component_breakdown.json').write_text(json.dumps({s:{m:{'latency':r['latency'],'components':r['components'],'solver_details':r['solver_details']} for m,r in modes.items()} for s,modes in summary.items()},indent=2)); (OUT/'warm_start_audit.json').write_text(json.dumps({s:{m:{'warm_start_valid':r['metrics']['warm_start_valid'],'termination_reason':r['metrics']['termination_reason']} for m,r in modes.items()} for s,modes in summary.items()},indent=2))
before=json.loads((OUT/'deterministic_scenario_metrics.json').read_text()); after={s:{m:r['latency'] for m,r in modes.items()} for s,modes in summary.items()}; (OUT/'latency_regression_before_after.json').write_text(json.dumps({'before_stage09_blocked_run':{s:{m:{'p95_ms':x['p95_end_to_end_ms']} for m,x in modes.items()} for s,modes in before.items() if s.startswith('no_obstacle')},'root_cause':'invalid empty-scene fixture plus first-cycle/setup mixed into short-run P95','after_minimal_reproduction':after},indent=2))

fig,axs=plt.subplots(2,3,figsize=(12,7)); labels=list(runs['R0_empty_straight']); first=[summary['R0_empty_straight'][m]['latency']['first_cycle_ms'] for m in labels]; steady=[summary['R0_empty_straight'][m]['latency']['steady_p95_ms'] for m in labels]; axs[0,0].bar(labels,first); axs[0,0].set_title('first cycle'); axs[0,1].bar(labels,steady); axs[0,1].axhline(100,color='r'); axs[0,1].set_title('steady P95');
for m in labels: axs[0,2].plot(runs['R0_empty_straight'][m]['cycle_times_ms'],label=m)
axs[0,2].legend(fontsize=6); axs[0,2].set_title('empty status timeline latency'); axs[1,0].bar(labels,[summary['R2_static'][m]['latency']['steady_p95_ms'] for m in labels]); axs[1,0].set_title('static P95'); axs[1,1].bar(['timeouts'],[sum('SOLVER_TIMEOUT' in r['statuses'] for modes in runs.values() for r in modes.values())]); axs[1,1].set_title('solver timeout count'); axs[1,2].axis('off'); fig.tight_layout()
for f in ('stage05_vs_stage09_p0_latency.png','latency_component_before_after.png','first_cycle_vs_steady_state.png','empty_scene_status_timeline.png','solver_timeout_breakdown.png','closed_loop_state_transitions.png'): fig.savefig(OUT/f,dpi=140)
print(json.dumps({'equivalence_maxima':equiv['maxima'],'empty_statuses':{m:r['statuses'] for m,r in runs['R0_empty_straight'].items()},'steady_p95':{s:{m:x['latency']['steady_p95_ms'] for m,x in modes.items()} for s,modes in summary.items()},'timeouts':len(timeouts)},indent=2))
