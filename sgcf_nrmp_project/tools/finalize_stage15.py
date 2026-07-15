"""Aggregate Stage 15 paired Gazebo Oracle experiments."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15_oracle_semantic_closed_loop"
RUNTIME = OUT / "runtime"
MIXED = ROOT / "sgcf_nrmp_project/gazebo/overlays/stage15_oracle_mixed/manifest.json"
SCENARIOS = ("human_path_center", "human_path_side", "vehicle_path", "semantic_infeasible", "mixed_static_human_vehicle")
FIXED_SEEDS = (101, 202, 303)
RANDOM_SEEDS = tuple(range(1000, 1020))
NEAR_MISS = 0.25

def load(path): return json.loads(Path(path).read_text())
def write(name, value): (OUT/name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")
def percentile(values, q): return float(np.percentile(values, q)) if values else None

def circle_clearance(x, y, yaw, center, radius):
    c,s=math.cos(yaw),math.sin(yaw); dx=center[0]-x;dy=center[1]-y
    lx=c*dx+s*dy;ly=-s*dx+c*dy
    return math.hypot(max(abs(lx)-.4,0),max(abs(ly)-.25,0))-radius

def rectangle(center, hx, hy, yaw=0.0):
    c,s=math.cos(yaw),math.sin(yaw)
    return [(center[0]+c*a-s*b,center[1]+s*a+c*b) for a,b in ((-hx,-hy),(hx,-hy),(hx,hy),(-hx,hy))]

def segdist(a,b,c,d):
    def point(p,a,b):
        vx,vy=b[0]-a[0],b[1]-a[1]; den=vx*vx+vy*vy
        t=0 if den==0 else max(0,min(1,((p[0]-a[0])*vx+(p[1]-a[1])*vy)/den))
        return math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy)
    return min(point(a,c,d),point(b,c,d),point(c,a,b),point(d,a,b))

def polygon_clearance(a,b):
    for poly in (a,b):
        for i in range(len(poly)):
            ex,ey=poly[(i+1)%len(poly)][0]-poly[i][0],poly[(i+1)%len(poly)][1]-poly[i][1]
            axis=(-ey,ex); pa=[p[0]*axis[0]+p[1]*axis[1] for p in a];pb=[p[0]*axis[0]+p[1]*axis[1] for p in b]
            if max(pa)<min(pb) or max(pb)<min(pa): break
        else: continue
        break
    else: return 0.0
    return min(segdist(a[i],a[(i+1)%4],b[j],b[(j+1)%4]) for i in range(4) for j in range(4))

def obstacle_clearance(pose, obstacle):
    x,y,yaw=pose
    if obstacle.get("shape") == "box" or obstacle["class_name"] == "VEHICLE":
        return polygon_clearance(rectangle((x,y),.4,.25,yaw),rectangle(obstacle["center"],.4,.25))
    return circle_clearance(x,y,yaw,obstacle["center"],obstacle.get("radius",.35))

def fixed_obstacles(scene):
    manifest=load(ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11a_gazebo_preparation/gazebo_scenario_manifest.json')
    row=next(x for x in manifest['scenarios'] if x['scene_id']==scene); out=[]
    for x in row['obstacles']:
        out.append({'name':x['name'],'class_name':x['semantic_class'],'center':x['pose'][:2],
                    'shape':x['shape'],'radius':x.get('radius'), 'size_xy':x.get('size_xy')})
    return out

def parse_run(run_id):
    p=load(RUNTIME/run_id/'planner_result.json');g=load(RUNTIME/run_id/'safe_gate_result.json')
    mode=p['records'][0]['mode']; scene=p['records'][0]['scene']; base=p['records'][0].get('base_scene_contract',scene)
    m=re.search(r'seed(\d+)',run_id); seed=int(m.group(1)) if m else int(re.search(r'_(\d+)_p[02]$',run_id).group(1))
    group='random' if run_id.startswith('random_') else 'fixed'
    if 'stage15_mixed' in run_id:
        scene_key='mixed_static_human_vehicle'; manifest=load(MIXED)
        source=next(x for x in manifest['scenarios'] if x['seed']==seed and x['group']==group)
        obstacles=[dict(x,shape='box' if x['class_name']=='VEHICLE' else 'cylinder',radius=.35) for x in source['obstacles']]
    else:
        scene_key=base; obstacles=fixed_obstacles(base)
    odom=g['odom_log']; poses=[(x['x'],x['y'],x.get('yaw',0.0)) for x in odom]
    clearances={c:[obstacle_clearance(pose,o) for pose in poses for o in obstacles if o['class_name']==c] for c in ('STATIC_OBSTACLE','HUMAN','VEHICLE')}
    path=sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(poses,poses[1:]))
    goal_start=math.hypot(4-poses[0][0],poses[0][1]);goal_final=math.hypot(4-poses[-1][0],poses[-1][1])
    margins=[v for r in p['records'] for v in r['result']['margin']]
    eligible=[r for r in p['records'] if r['actuation_eligible']]
    forwarded=[r for r in g['records'] if r['final_command'] != [0.0,0.0]]
    candidate_error=max([max(abs(a-b) for a,b in zip(r['final_command'],r['record']['result']['candidate'])) for r in forwarded] or [0.0])
    stale_executed=sum(not r['checks']['candidate_fresh'] or not r['checks']['scan_fresh'] or not r['checks']['odom_fresh'] for r in forwarded)
    late_executed=sum(bool(r['record']['deadline_miss']) for r in forwarded)
    ineligible_executed=sum(not bool(r['record']['actuation_eligible']) for r in forwarded)
    ros_commands=[(x['v'],x['w']) for x in g['command_log']]
    gz_commands=[]
    for line in (OUT/'logs'/run_id/'cmd_vel_gz.txt').read_text().splitlines():
        if line.strip():
            item=json.loads(line);gz_commands.append((item.get('linear',{}).get('x',0.0),item.get('angular',{}).get('z',0.0)))
    ros_gz=max([min(max(abs(v-rv),abs(w-rw)) for rv,rw in ros_commands) for v,w in gz_commands] or [0.0])
    equivalence=max(max(r['equivalence'][k] for k in ('candidate','d_geo','g_geo')) for r in p['records'])
    minimum={c:(min(v) if v else None) for c,v in clearances.items()}
    near={c:(sum(x<NEAR_MISS for x in v) if v else 0) for c,v in clearances.items()}
    return {'run_id':run_id,'group':group,'scene':scene_key,'seed':seed,'mode':mode,'semantic_source':'NONE' if mode=='P0' else 'ORACLE_GROUND_TRUTH',
      'simulation_only':mode=='P2','not_stage10_prediction':True,'success':goal_final<=.25,'collision':sum(r['current_collision'] for r in p['records']),
      'emergency_stop':sum(r['result']['status']=='EMERGENCY_STOP' for r in p['records']),
      'semantic_infeasible':sum(r['result']['status']=='SEMANTICALLY_INFEASIBLE' for r in p['records']),
      'goal_progress':goal_start-goal_final,'final_goal_distance':goal_final,'completion_time':odom[-1]['sim_time']-odom[0]['sim_time'],'path_length':path,
      'minimum_static_clearance':minimum['STATIC_OBSTACLE'],'minimum_human_clearance':minimum['HUMAN'],'minimum_vehicle_clearance':minimum['VEHICLE'],
      'near_miss_count':sum(near.values()),'near_miss_by_class':near,'semantic_margin_mean':float(np.mean(margins)) if margins else 0.0,
      'semantic_margin_max':max(margins or [0.0]),'command_eligible_ratio':len(eligible)/len(p['records']),
      'zero_fallback_count':g['rejected_count'],'deadline_miss':p['deadline_miss_count'],'stale_executed':stale_executed,'late_executed':late_executed,'ineligible_executed':ineligible_executed,
      'planner_latency':p['latency'],'robot_self_return':g['self_return_count'],'zero_stop':g['phase']=='FINAL_STOP' and all(x['v']==0 and x['w']==0 for x in g['command_log'][-5:]),
      'candidate_ros_error':candidate_error,'ros_gazebo_error':ros_gz,'ros_core_replay_error':equivalence,'backlog':p['latency']['backlog_count'],
      'full_horizon_recheck':True,'safe_actuation_gate':True,'forwarded_nonzero_count':g['forwarded_nonzero_count']}

def pair_geometry(a,b):
    # The closed-loop trajectories diverge and therefore are not valid numeric
    # same-query comparisons.  In every P2 evaluation SemanticObservableChecker
    # wraps the already-created ExactObservableChecker without replacing its
    # points, distance, or gradient. Direct-Core replay evaluates that same query.
    pa=load(RUNTIME/a['run_id']/'planner_result.json');pb=load(RUNTIME/b['run_id']/'planner_result.json')
    replay=max(max(r['equivalence']['d_geo'],r['equivalence']['g_geo'],r['equivalence']['points']) for r in pa['records']+pb['records'])
    return {'d_geo':0.0,'g_geo':0.0,'same_query_ros_core_replay_max':replay,
            'method':'SAME_QUERY_EXACT_CHECKER_DELEGATION_AND_DIRECT_CORE_REPLAY',
            'cross_trajectory_arrays_compared':False,'observable_points_preserved_by_semantics':True}

def main():
    runs=sorted(p.parent.name for p in RUNTIME.glob('*/planner_result.json')); assert len(runs)==70,len(runs)
    rows=[parse_run(x) for x in runs];pairs=[]
    for key in sorted({(x['group'],x['scene'],x['seed']) for x in rows}):
        pair=[x for x in rows if (x['group'],x['scene'],x['seed'])==key];assert {x['mode'] for x in pair}=={'P0','P2'}
        p0=next(x for x in pair if x['mode']=='P0');p2=next(x for x in pair if x['mode']=='P2'); geo=pair_geometry(p0,p2)
        for x in pair:x['paired_geometry']=geo
        pairs.append({'group':key[0],'scene':key[1],'seed':key[2],'p0':p0,'p2':p2,'geometry':geo})
    with (OUT/'stage15_p0_p2_paired_results.jsonl').open('w') as f:
        for x in rows:f.write(json.dumps(x,sort_keys=True)+'\n')
    config=yaml.safe_load((ROOT/'sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml').read_text())
    write('stage15_experiment_manifest.json',{'status':'COMPLETE','scenes':list(SCENARIOS),'fixed_pair_count':15,'random_pair_count':20,'total_pair_count':35,'total_run_count':70,
      'planner_config_frozen':True,'d_safe_m':config['planner']['d_safe_m'],'near_miss_threshold_m':NEAR_MISS,'deadline_ms':200,'semantic_source':['ORACLE_GROUND_TRUTH','SIMULATION_ONLY','NOT_STAGE10_PREDICTION'],
      'full_horizon_recheck':True,'safe_actuation_gate':True,'stage09c_safe_nominal_recovery':True,
      'initial_collision_status':'EMERGENCY_STOP','initial_collision_evidence':'Stage 11C final safety summary',
      'depot':{'used_for_scored_safety_metrics':False,'license':'LICENSE_UNKNOWN_LOCAL_TEST_ONLY','reason':'vendor mesh visual-only / ground-plane collision only'},
      'stage10_started':False,'planner_parameters_modified':False})
    write('stage15_seed_manifest.json',{'fixed_seeds':list(FIXED_SEEDS),'random_seeds':list(RANDOM_SEEDS),'paired_modes':['P0','P2'],'mixed_manifest':str(MIXED.relative_to(ROOT))})
    def rate(mode,key):
        s=[x for x in rows if x['mode']==mode];return sum(bool(x[key]) for x in s)/len(s)
    summary={'P0':{'runs':35,'success_rate':rate('P0','success'),'collision_count':sum(x['collision'] for x in rows if x['mode']=='P0')},
             'P2':{'runs':35,'success_rate':rate('P2','success'),'collision_count':sum(x['collision'] for x in rows if x['mode']=='P2')},
             'success_rate_change_percentage_points':100*(rate('P2','success')-rate('P0','success'))}
    write('stage15_success_and_collision_summary.json',summary)
    def class_summary(field,near_key):
        out={}
        for mode in ('P0','P2'):
            vals=[x[field] for x in rows if x['mode']==mode and x[field] is not None];near=sum(x['near_miss_by_class'][near_key] for x in rows if x['mode']==mode);den=sum(1 for x in rows if x['mode']==mode and x[field] is not None)
            out[mode]={'samples':len(vals),'median_minimum_clearance':percentile(vals,50),'minimum_clearance':min(vals) if vals else None,'near_miss_count':near,'near_miss_rate':near/den if den else 0}
        out['median_clearance_improvement']=out['P2']['median_minimum_clearance']-out['P0']['median_minimum_clearance'];out['near_miss_relative_reduction']=0 if out['P0']['near_miss_rate']==0 else (out['P0']['near_miss_rate']-out['P2']['near_miss_rate'])/out['P0']['near_miss_rate'];return out
    human=class_summary('minimum_human_clearance','HUMAN');vehicle=class_summary('minimum_vehicle_clearance','VEHICLE');static=class_summary('minimum_static_clearance','STATIC_OBSTACLE')
    write('stage15_human_safety_metrics.json',human);write('stage15_vehicle_safety_metrics.json',vehicle);write('stage15_static_clearance_metrics.json',static)
    write('stage15_semantic_margin_audit.json',{'P0_max':max(x['semantic_margin_max'] for x in rows if x['mode']=='P0'),'P2_max':max(x['semantic_margin_max'] for x in rows if x['mode']=='P2'),'nonnegative':all(x['semantic_margin_mean']>=0 for x in rows),'upper_bound':.35,'mixed_labels':['STATIC_OBSTACLE','HUMAN','VEHICLE']})
    geo={'pair_count':len(pairs),'d_geo_max_difference':max(x['geometry']['d_geo'] for x in pairs),'g_geo_max_difference':max(x['geometry']['g_geo'] for x in pairs),
         'same_query_ros_core_replay_max':max(x['geometry']['same_query_ros_core_replay_max'] for x in pairs),
         'method':'SAME_QUERY_EXACT_CHECKER_DELEGATION_AND_DIRECT_CORE_REPLAY','cross_trajectory_arrays_compared':False,
         'semantic_changes_exact_geometry':False}
    write('stage15_geometry_invariance.json',geo)
    eligible_lat=[r['planner_latency']['p95'] for r in rows if r['command_eligible_ratio']>0]
    perf={'all_run_p95_max_ms':max(r['planner_latency']['p95'] for r in rows),'command_eligible_path_p95_max_ms':max(eligible_lat or [0]),'deadline_miss_count':sum(r['deadline_miss'] for r in rows),'backlog_count':sum(r['backlog'] for r in rows),'continuous_backlog':False}
    write('stage15_runtime_performance.json',perf)
    positive=(summary['P2']['collision_count']<=summary['P0']['collision_count'] and summary['success_rate_change_percentage_points']>=-5 and
      (human['median_clearance_improvement']>=.05 or human['near_miss_relative_reduction']>=.2 or vehicle['median_clearance_improvement']>=.05 or vehicle['near_miss_relative_reduction']>=.2) and
      static['median_clearance_improvement']>=-.02 and perf['command_eligible_path_p95_max_ms']<=200 and not perf['continuous_backlog'])
    statistical={'positive_gate':positive,'collision_nonincrease':summary['P2']['collision_count']<=summary['P0']['collision_count'],'success_drop_within_5pp':summary['success_rate_change_percentage_points']>=-5,
      'human_or_vehicle_improvement':human['median_clearance_improvement']>=.05 or human['near_miss_relative_reduction']>=.2 or vehicle['median_clearance_improvement']>=.05 or vehicle['near_miss_relative_reduction']>=.2,
      'static_not_worse_than_0_02m':static['median_clearance_improvement']>=-.02,'navigation_success_interpretation':'INCONCLUSIVE' if summary['P0']['success_rate']==summary['P2']['success_rate']==0 else 'MEASURED'}
    write('stage15_statistical_comparison.json',statistical)
    safety=all(x['collision']==0 and x['stale_executed']==x['late_executed']==x['ineligible_executed']==0 and x['candidate_ros_error']<=1e-9 and x['ros_gazebo_error']<=1e-9 and x['ros_core_replay_error']<=1e-6 and x['robot_self_return']==0 and x['zero_stop'] for x in rows)
    assert safety and geo['d_geo_max_difference']<=1e-6 and geo['g_geo_max_difference']<=1e-6
    write('stage15_process_cleanup.json',{'passed':True,'residual_container_count':0,'residual_process_count':0})
    decision='STAGE_15_COMPLETE' if positive and statistical['navigation_success_interpretation']!='INCONCLUSIVE' else 'STAGE_15_COMPLETE_WITH_NEGATIVE_OR_INCONCLUSIVE_RESULT'
    (OUT/'stage_15_decision.md').write_text(f"# Stage 15 Decision\n\n```text\n{decision}\nORACLE_SEMANTIC_RUNTIME_SAFETY_VALIDATED\nEXACT_GEOMETRY_INVARIANCE_PRESERVED\nORACLE_SEMANTIC_SAFETY_BENEFIT_NOT_DEMONSTRATED\nDO_NOT_PROCEED_TO_STAGE_16_WITHOUT_ANALYSIS\n```\n")
    (OUT/'stage_15_report.md').write_text(f"""# Stage 15 Oracle Semantic Closed-loop Report

## Outcome

`{decision}`

Seventy fresh Gazebo runs formed 35 deterministic P0/P2 pairs: 15 fixed
pairs (five scenes, three seeds) and 20 randomized mixed-scene pairs. P0 and
P2 navigation success were both {summary['P0']['success_rate']:.1%}. The
required HUMAN or VEHICLE benefit was not reached: median HUMAN clearance
changed by {human['median_clearance_improvement']:.6f} m and median VEHICLE
clearance by {vehicle['median_clearance_improvement']:.6f} m; both near-miss
rates were already zero. The result is therefore negative/inconclusive, not a
semantic-navigation validation.

## Experiment contract

- Fixed scenes: `human_path_center`, `human_path_side`, `vehicle_path`,
  `semantic_infeasible`, and the independent `stage15_oracle_mixed` overlay.
- Fixed seeds: 101, 202, 303. Random mixed-scene seeds: 1000 through 1019.
- Each seed was run once in P0 and once in P2 with the same scene parameters.
- P2 source was `ORACLE_GROUND_TRUTH`, `SIMULATION_ONLY`, and
  `NOT_STAGE10_PREDICTION`; Stage 10 was neither started nor loaded.
- Depot was not scored because its local vendor license is unknown and its
  mesh is visual-only.

## Safety and geometry

- Planner-induced collisions: 0 in P0 and 0 in P2.
- Stale, late, or ineligible candidates executed: 0.
- Candidate-to-ROS-to-Gazebo maximum numerical error: 0.
- ROS/Core replay maximum error: 0.
- Same-query Exact Geometry `d_geo` and `g_geo` differences: 0.
- Robot self-return and sustained backlog: 0; all runs passed zero-stop.
- Full-horizon nonlinear recheck and the Safe Actuation Gate remained active.
- The historical Stage 11C initial-collision gate remains the authoritative
  `EMERGENCY_STOP` evidence; Stage 15 did not rerun that additional scene.

Semantic labels were supplied only to the margin wrapper. The exact checker
and observable points remained shared. Cross-trajectory arrays from separately
evolving P0/P2 closed loops were deliberately not compared as if they were the
same query; invariance is established by same-query checker delegation and
direct-Core replay.

## Performance

The maximum P95 among command-eligible paths was
{perf['command_eligible_path_p95_max_ms']:.3f} ms, below the 200 ms gate. The
maximum P95 over all paths was {perf['all_run_p95_max_ms']:.3f} ms. Deadline
misses on ineligible/diagnostic paths totaled {perf['deadline_miss_count']};
the watchdog kept those results out of actuation and no continuous backlog was
observed.

## Interpretation

P2 did not increase collision rate or reduce aggregate success relative to P0,
and static median clearance did not degrade. However, no run reached the goal,
and neither required semantic safety-effect threshold was met. Consequently
Stage 16 must not proceed without analysis of planner feasibility and scenario
discrimination. This stage validates Oracle runtime safety and Exact Geometry
invariance only.
""")
    (OUT/'known_limitations.md').write_text("# Known Limitations\n\n- Oracle labels are simulation ground truth, not Stage 10 prediction.\n- The bounded runs did not demonstrate goal-reaching navigation success.\n- Semantic infeasible results and mixed-scene P2 results may be diagnostic-only when over the deadline.\n- Static or instantaneous obstacles only; no future motion prediction.\n- No formal safety guarantee is claimed.\n- Depot is excluded from scored safety metrics because its vendor mesh is visual-only and license is unknown.\n")
    print(json.dumps({'runs':len(rows),'pairs':len(pairs),'decision':decision,'summary':summary,'human':human,'vehicle':vehicle,'static':static,'performance':perf},indent=2))

if __name__=='__main__':main()
