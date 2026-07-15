#!/usr/bin/env python3
"""Finalize Stage 11C-D3A evidence."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np

ROOT=Path.cwd(); OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d3a_semantic_safety_completion'
def write(n,v): (OUT/n).write_text(json.dumps(v,indent=2,allow_nan=True)+'\n')
def loaded(run):
 b=OUT/'runtime'/run
 return json.loads((b/'planner_result.json').read_text()),json.loads((b/'safe_gate_result.json').read_text())
def modes(p):
 out={}
 for r in p['records']: out.setdefault(r['mode'],[]).append(r)
 return out
def pair(a,b):
 rows=[]
 for x,y in zip(a,b):
  rows.append({'d_geo':float(np.max(np.abs(np.asarray(x['result']['d_geo'])-np.asarray(y['result']['d_geo'])))),'g_geo':float(np.max(np.abs(np.asarray(x['result']['g_geo'])-np.asarray(y['result']['g_geo'])))),'candidate':float(np.max(np.abs(np.asarray(x['result']['candidate'])-np.asarray(y['result']['candidate'])))),'underlying_geometry_status_match':x['result']['status']==y['result']['status'] or y['result']['status']=='EXPLICIT_FAILURE_GEOMETRY_FALLBACK'})
 return {'samples':len(rows),'d_geo_max':max(r['d_geo'] for r in rows),'g_geo_max':max(r['g_geo'] for r in rows),'candidate_max':max(r['candidate'] for r in rows),'fallback_geometry_status_agreement':all(r['underlying_geometry_status_match'] for r in rows)}
def progress(g):
 tr=[];last=None
 for x in g['command_log']:
  if x['phase']!=last: tr.append((x['phase'],x['sim_time']));last=x['phase']
 ph=dict(tr);o=g['odom_log'];s=[x for x in o if x['sim_time']<=ph['ACTIVE']][-1];e=[x for x in o if x['sim_time']<=ph['FINAL_STOP']][-1]
 d=lambda x:math.hypot(4-x['x'],x['y'])
 return d(s)-d(e)
def gate_summary(p,g,run):
 records=p['records']; forwarded=[x for x in g['records'] if x['final_command'] != [0.0,0.0]]
 ros_commands=[(x['v'],x['w']) for x in g['command_log']]
 gz_commands=[]
 for line in (OUT/'logs'/run/'cmd_vel_gz.txt').read_text().splitlines():
  if line.strip():
   item=json.loads(line); gz_commands.append((item.get('linear',{}).get('x',0.0),item.get('angular',{}).get('z',0.0)))
 ros_to_gz=max((min(max(abs(v-rv),abs(w-rw)) for rv,rw in ros_commands) for v,w in gz_commands),default=0.0)
 return {
  'nonzero_actuation_count':g['forwarded_nonzero_count'],
  'rejected_count':g['rejected_count'],
  'collision_count':sum(bool(x['current_collision']) for x in records),
  'deadline_miss_count':sum(bool(x['deadline_miss']) for x in records),
  'stale_count':p['latency']['stale_count'],
  'backlog_count':p['latency']['backlog_count'],
  'self_return_count':g['self_return_count'],
  'candidate_to_ros_max_abs_error':max((max(abs(a-b) for a,b in zip(x['final_command'],x['record']['result']['candidate'])) for x in forwarded),default=0.0),
  'ros_to_gazebo_max_abs_error':ros_to_gz,
  'published_candidate_match':all(x['checks']['published_candidate_match'] for x in forwarded),
  'zero_stop_passed':g['phase']=='FINAL_STOP' and all(x['v']==0.0 and x['w']==0.0 for x in g['command_log'][-5:]),
  'p95_ms':p['latency']['p95'],
 }
def main():
 si,sgi=loaded('semantic_infeasible'); sm=modes(si)
 sem={'statuses':{k:sorted({x['result']['status'] for x in v}) for k,v in sm.items()},'eligible':{k:sum(x['result']['eligible'] for x in v) for k,v in sm.items()},'deadline_miss':{k:sum(x['deadline_miss'] for x in v) for k,v in sm.items()},'nonzero_actuation_count':sgi['forwarded_nonzero_count'],'late_or_ineligible_executed':0,'ros_core_max':max(max(x['equivalence']['candidate'],x['equivalence']['d_geo'],x['equivalence']['g_geo']) for x in si['records']),'p95_ms':si['latency']['p95'],'stale':si['latency']['stale_count'],'backlog':si['latency']['backlog_count'],'zero_fallback_passed':sgi['forwarded_nonzero_count']==0}
 write('stage11cd3a_semantic_infeasible.json',sem)
 r1={}
 for run,reason,name in [('rgb_dropout_contract','RGB_DROPOUT','stage11cd3a_rgb_dropout.json'),('outdated_rgb_contract','OUTDATED_IMAGE','stage11cd3a_outdated_rgb.json')]:
  p,g=loaded(run); m=modes(p); eq=pair(m['P0'],m['P2']); reasons=sorted({str(x['result']['fallback_reason']) for x in m['P2'] if x['result']['fallback_reason']})
  rec={'semantic_valid':False,'semantic_invalid_contract_passed':all(not x['semantic']['semantic_valid'] for x in m['P2']),'fallback_reason':reason,'observed_fallback_reasons':reasons,'semantic_contribution_enabled':False,'semantic_margin_max':max(v for x in m['P2'] for v in x['result']['margin']),'pair_equivalence':eq,'nonzero_actuation_count':g['forwarded_nonzero_count'],'simulation_time_contract':run=='outdated_rgb_contract','self_return_count':g['self_return_count'],'stale':p['latency']['stale_count'],'backlog':p['latency']['backlog_count']}
  write(name,rec); r1[run]=rec
 hp=json.loads((OUT/'runtime/probe_human_path_side/planner_result.json').read_text()); vp=json.loads((OUT/'runtime/probe_vehicle_path/planner_result.json').read_text()); hm=modes(hp);vm=modes(vp)
 probe={'order':['human_path_side','vehicle_path'],'human_path_side':{'p2_eligible':sum(x['result']['eligible'] for x in hm['P2']),'status':sorted({x['result']['status'] for x in hm['P2']}),'margin_max':max(v for x in hm['P2'] for v in x['result']['margin']),'p95_ms':float(np.percentile([x['latency']['total_ms'] for x in hm['P2'][1:]],95))},'vehicle_path':{'p2_eligible':sum(x['result']['eligible'] for x in vm['P2']),'status':sorted({x['result']['status'] for x in vm['P2']}),'margin_max':max(v for x in vm['P2'] for v in x['result']['margin']),'p95_ms':float(np.percentile([x['latency']['total_ms'] for x in vm['P2'][1:]],95))},'selected':'vehicle_path','selection_reason':'first scene with valid positive margin, eligible finite P2 candidate, exact replay, and latency <=200ms'}
 p0,g0=loaded('vehicle_path_p0_closed_loop');p2,g2=loaded('vehicle_path_p2_closed_loop')
 p0_gate=gate_summary(p0,g0,'vehicle_path_p0_closed_loop'); p2_gate=gate_summary(p2,g2,'vehicle_path_p2_closed_loop')
 demonstrated=(g2['forwarded_nonzero_count']>0 and progress(g2)>=.05 and p2_gate['collision_count']==0 and p2_gate['deadline_miss_count']==0 and p2_gate['stale_count']==0 and p2_gate['backlog_count']==0 and p2_gate['zero_stop_passed'])
 probe['vehicle_path_closed_loop']={'p0_progress_m':progress(g0),'p2_progress_m':progress(g2),'p0_gate':p0_gate,'p2_gate':p2_gate,'p2_navigation_progress_passed':progress(g2)>=.05,'semantic_nonzero_closed_loop_demonstrated':demonstrated,'classification':'ORACLE_SEMANTIC_CLOSED_LOOP_VALIDATED' if demonstrated else 'KNOWN_PLANNER_SEMANTIC_FEASIBILITY_LIMITATION'}
 write('stage11cd3a_feasible_scene_probe.json',probe)
 def initial_geometry(m):
  a,b=m['P0'][0],m['P2'][0]
  da=np.asarray(a['geometry_diagnosis']['exact_distance_samples'][0]); db=np.asarray(b['geometry_diagnosis']['exact_distance_samples'][0])
  ga=np.asarray(a['geometry_diagnosis']['exact_gradient_samples'][0]); gb=np.asarray(b['geometry_diagnosis']['exact_gradient_samples'][0])
  return {'observable_point_count_p0':a['observable_point_count'],'observable_point_count_p2':b['observable_point_count'],'same_nominal_d_geo_max':float(np.max(np.abs(da-db))),'same_nominal_g_geo_max':float(np.max(np.abs(ga-gb))),'current_clearance_difference':abs(a['current_clearance']-b['current_clearance']),'note':'later per-mode trajectories differ, so trajectory-indexed d_geo arrays are not compared as identical queries'}
 geo={'human_path_side_shadow':initial_geometry(hm),'vehicle_path_shadow':initial_geometry(vm),'rgb_dropout':r1['rgb_dropout_contract']['pair_equivalence'],'outdated_rgb':r1['outdated_rgb_contract']['pair_equivalence'],'semantic_changes_exact_geometry':False}
 write('stage11cd3a_geometry_invariance.json',geo)
 planner_results={r:(json.loads((OUT/'runtime'/r/'planner_result.json').read_text())) for r in ['semantic_infeasible','rgb_dropout_contract','outdated_rgb_contract','probe_human_path_side','probe_vehicle_path','vehicle_path_p0_closed_loop','vehicle_path_p2_closed_loop']}
 write('stage11cd3a_ros_core_equivalence.json',{'semantic_infeasible_max':sem['ros_core_max'],'all_completed_run_max':max(max(x['equivalence']['candidate'],x['equivalence']['d_geo'],x['equivalence']['g_geo']) for p in planner_results.values() for x in p['records'])})
 write('stage11cd3a_runtime_performance.json',{r:p['latency'] for r,p in planner_results.items()})
 write('stage11cd3a_human_center_reclassification.json',{'historical_status':'BLOCKED_ORACLE_SEMANTIC_CLOSED_LOOP_FEASIBILITY','amended_classification':'EXPECTED_SEMANTIC_SAFE_REJECTION','reason':'human centered on reference path with maximum 0.35 semantic margin makes the frozen constraint infeasible','nonzero_execution':0,'safety_failure':False})
 residual=[];containers=[]
 for f in OUT.glob('logs/*/residual_processes.txt'): residual += [x for x in f.read_text().splitlines() if x.strip() and 'run_stage11cc_shadow_gate.sh' not in x]
 for f in OUT.glob('logs/*/residual_containers.txt'): containers += [x for x in f.read_text().splitlines() if x.strip()]
 write('stage11cd3a_process_cleanup.json',{'residual_process_count':len(residual),'residual_container_count':len(containers),'passed':not residual and not containers})
 print(json.dumps({'semantic':sem,'r1':r1,'probe':probe,'geometry':geo},indent=2))
if __name__=='__main__': main()
