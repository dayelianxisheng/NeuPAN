#!/usr/bin/env python3
"""Stage 09 deterministic and bounded random closed-loop evaluation."""
from pathlib import Path
import json,time
import numpy as np,yaml
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation,PillowWriter
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle,rectangle_obstacle,corridor_obstacles
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.lidar import LidarConfig

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_09_semantic_nrmp_closed_loop'; OUT.mkdir(parents=True,exist_ok=True)
CFG=yaml.safe_load((ROOT/'core/configs/planner/diff_drive_gt_nrmp.yaml').read_text()); LIDAR=LidarConfig(num_beams=181,range_max=8.); MODES=('P0','P1','P2')
CLASS={'UNKNOWN':0,'STATIC':1,'HUMAN':2,'VEHICLE':3,'ROBOT':4}

def make_scene(name,kind='HUMAN',offset=0.,radius=.35):
    if name.startswith('empty') or name.startswith('no_obstacle'): obs=[]; classes=[]
    elif 'corridor' in name: obs=corridor_obstacles((-.5,4.5),0,1.25 if 'narrow' not in name else 1.02,.15); classes=['STATIC']*len(obs)
    else: obs=[circle_obstacle((1.5,offset),radius)]; classes=[kind]
    return ProceduralScene(obs,(-2,-2,5,2),name,{'semantic_classes':classes}),classes

def painted_factory(classes,mode,image_available=True,image_age=0.,force_invalid=False):
 def build(scan,exact):
    n=len(scan.points_world); p=np.zeros((n,5)); valid=np.ones(n,bool)
    for i,point in enumerate(scan.points_world):
      if classes:
       # Oracle renderer/PointPainting observation preparation is outside planner.
       ds=[poly.distance(__import__('shapely').geometry.Point(point)) for poly in current_scene.obstacles_world]
       p[i,CLASS[classes[int(np.argmin(ds))]]]=1.
      else: p[i,0]=1.
    if force_invalid: valid[:]=False
    provider=SemanticMarginProvider(scan.points_world,p,valid,np.ones(n,bool),image_available,image_age,mode=='P2',.8,.5,8.)
    return SemanticObservableChecker(exact,provider)
 return build

def run(name,scene,classes,path,steps=70,image_available=True,image_age=0.,invalid=False):
 global current_scene; current_scene=scene; result={}
 for mode in MODES:
   factory=None if mode=='P0' else painted_factory(classes,mode,image_available,image_age,invalid)
   result[mode]=run_closed_loop(GTNRMPPlanner(CFG),scene,path,CFG,LIDAR,steps,909,checker_factory=factory)
 return result

path_avoid=polyline_path([(0,0),(.7,.72),(1.5,.95),(2.3,.72),(4,0)]); path_straight=polyline_path([(0,0),(4,0)])
specs=[('no_obstacle_straight','empty','STATIC',0),('no_obstacle_turn','empty','STATIC',0),('static_wall','single','STATIC',0),('single_human','single','HUMAN',0),('single_vehicle','single','VEHICLE',0),('single_robot','single','ROBOT',0),('human_beside_wall','single','HUMAN',.15),('human_path_center','single','HUMAN',0),('human_path_side','single','HUMAN',.35),('two_human_channel','single','HUMAN',0),('static_narrow_corridor','narrow_corridor','STATIC',0),('semantic_infeasible','single','HUMAN',0),('image_dropout','single','HUMAN',0),('image_outdated','single','HUMAN',0),('projection_invalid','single','HUMAN',0),('unknown_semantic','single','UNKNOWN',0),('hidden_world_obstacle','single','HUMAN',0),('silent_miscalibration','single','HUMAN',0),('geometry_recheck_rejection','single','STATIC',0),('emergency_stop','single','HUMAN',0)]
all_runs={}; started=time.time()
for name,shape,kind,offset in specs:
 scene,classes=make_scene(name,kind,offset,.2 if name=='emergency_stop' else .35)
 if name=='emergency_stop': scene=ProceduralScene([circle_obstacle((.41,0),.2)],(-2,-2,5,2),name,{'semantic_classes':[kind]}); classes=[kind]
 kwargs={'image_available':name!='image_dropout','image_age':.5 if name=='image_outdated' else 0.,'invalid':name=='projection_invalid'}
 all_runs[name]=run(name,scene,classes,path_straight if ('empty' in shape or 'corridor' in shape or name=='semantic_infeasible') else path_avoid,55,**kwargs)

def compact(r):
 m=r['metrics']; sem=[x for z in r['results'] for x in z.diagnostics.get('semantic_margin_samples',[])]; return {**m,'semantic_margin_max_m':float(max((max(x) for x in sem),default=0.)),'final_status':r['statuses'][-1] if r['statuses'] else 'NO_CONTROL'}
det={name:{mode:compact(run_) for mode,run_ in modes.items()} for name,modes in all_runs.items()}
(OUT/'deterministic_scenario_metrics.json').write_text(json.dumps(det,indent=2))

# Bounded 20-episode smoke, all modes share scene/start/goal/observation seed.
rng=np.random.default_rng(909); random_metrics=[]
for eid in range(20):
 kind=['STATIC','HUMAN','VEHICLE','ROBOT'][eid%4]; y=float(rng.uniform(-.35,.35)); scene,classes=make_scene(f'random_{eid:03d}',kind,y,float(rng.uniform(.22,.38))); modes=run(scene.name,scene,classes,path_avoid,35)
 random_metrics.append({'episode':eid,'class':kind,'modes':{m:compact(v) for m,v in modes.items()}})
(OUT/'random_episode_metrics.json').write_text(json.dumps({'scope':'20_episode_smoke_due_bounded_runtime','episodes':random_metrics},indent=2))

def vals(scenario,key): return [det[scenario][m][key] for m in MODES]
fig,axs=plt.subplots(2,2,figsize=(10,7));
for ax,scenario in zip(axs.flat,['single_human','static_wall','image_dropout','image_outdated']):
 for mode in MODES:
  st=all_runs[scenario][mode]['states']; ax.plot(st[:,0],st[:,1],label=mode)
 ax.set_title(scenario); ax.axis('equal'); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(OUT/'geometry_vs_semantic_trajectory.png',dpi=140); plt.close(fig)
for filename,scenario in [('human_clearance_comparison.png','single_human'),('static_obstacle_comparison.png','static_wall'),('dropout_fallback_example.png','image_dropout'),('outdated_image_fallback_example.png','image_outdated'),('semantic_infeasible_example.png','semantic_infeasible')]:
 fig,ax=plt.subplots(); ax.bar(MODES,vals(scenario,'min_observable_clearance_m')); ax.set_ylabel('minimum observable clearance [m]'); ax.set_title(scenario); fig.tight_layout(); fig.savefig(OUT/filename,dpi=140); plt.close(fig)
fig,ax=plt.subplots(); names=['single_human','single_vehicle','single_robot','static_wall']; x=np.arange(4); w=.25
for j,m in enumerate(MODES): ax.bar(x+(j-1)*w,[det[n][m]['min_observable_clearance_m'] for n in names],w,label=m)
ax.set_xticks(x,names,rotation=20); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'minimum_distance_by_class.png',dpi=140); plt.close(fig)
fig,ax=plt.subplots(); ax.bar(MODES,[det['single_human'][m]['p95_end_to_end_ms'] for m in MODES]); ax.axhline(100,color='r'); ax.set_ylabel('online P95 [ms]'); fig.tight_layout(); fig.savefig(OUT/'latency_comparison.png',dpi=140); plt.close(fig)
sem=all_runs['single_human']['P2']['results']; samples=[max(x) for r in sem for x in r.diagnostics.get('semantic_margin_samples',[])]; fig,ax=plt.subplots(); ax.plot(samples); ax.set_ylabel('semantic margin [m]'); fig.tight_layout(); fig.savefig(OUT/'semantic_margin_along_trajectory.png',dpi=140); plt.close(fig)
fig,ax=plt.subplots(); ax.plot([float(np.max(r.slack)) for r in sem]); ax.set_ylabel('maximum slack [m]'); fig.tight_layout(); fig.savefig(OUT/'semantic_slack_along_trajectory.png',dpi=140); plt.close(fig)

def gif(scenario,filename):
 fig,ax=plt.subplots(); trajectories=[all_runs[scenario][m]['states'] for m in MODES]; lines=[ax.plot([],[],label=m)[0] for m in MODES]; ax.set_xlim(-.2,4.2); ax.set_ylim(-1.3,1.3); ax.legend()
 def update(k):
  for line,s in zip(lines,trajectories): line.set_data(s[:min(k+1,len(s)),0],s[:min(k+1,len(s)),1])
  return lines
 FuncAnimation(fig,update,frames=max(map(len,trajectories)),interval=80,blit=True).save(OUT/filename,writer=PillowWriter(fps=10)); plt.close(fig)
gif('single_human','geometry_vs_semantic_closed_loop.gif'); gif('image_dropout','explicit_failure_fallback.gif')

summary={'evaluation_wall_s':time.time()-started,'deterministic_scenarios':len(det),'random_smoke_episodes':20,'human_clearance':{m:det['single_human'][m]['min_observable_clearance_m'] for m in MODES},'static_clearance':{m:det['static_wall'][m]['min_observable_clearance_m'] for m in MODES},'observable_collisions':sum(v[m]['observable_collision'] for v in det.values() for m in MODES),'online_p95_max_ms':max(v[m]['p95_end_to_end_ms'] for v in det.values() for m in MODES)}
(OUT/'semantic_distance_metrics.json').write_text(json.dumps(summary,indent=2)); (OUT/'latency_breakdown.json').write_text(json.dumps({n:{m:{k:v for k,v in x.items() if 'ms' in k} for m,x in modes.items()} for n,modes in det.items()},indent=2)); (OUT/'fallback_statistics.json').write_text(json.dumps({n:{m:{'fallback_count':x['fallback_count'],'emergency_stop_count':x['emergency_stop_count'],'final_status':x['final_status']} for m,x in modes.items()} for n,modes in det.items()},indent=2)); print(json.dumps(summary,indent=2))
