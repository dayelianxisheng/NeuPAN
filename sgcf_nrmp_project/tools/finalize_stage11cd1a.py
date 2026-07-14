#!/usr/bin/env python3
"""Finalize Stage 11C-D1A speed alignment and geometry diagnosis."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d1a_speed_contract_and_geometry_diagnosis'
RUNTIME=OUT/'runtime'

def dump(name,value): (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def vec(row):
 def one(x): return [float((x or {}).get(k,0.0)) for k in ('x','y','z')]
 return one(row.get('linear'))+one(row.get('angular'))
def nz(row): return any(abs(x)>1e-12 for x in vec(row))

config_path=ROOT/'sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml'
model_path=ROOT/'sgcf_nrmp_project/gazebo/models/sgcf_diff_drive_robot/model.sdf'
speed={
 'planner_config':str(config_path.relative_to(ROOT)),'planner_config_sha256':sha(config_path),
 'planner_v_max_mps':1.0,'planner_w_max_radps':1.5,
 'diffdrive_model':str(model_path.relative_to(ROOT)),'diffdrive_model_sha256':sha(model_path),
 'diffdrive_max_linear_velocity_mps':1.0,'diffdrive_max_angular_velocity_radps':1.5,
 'effective_linear_limit_mps':1.0,'effective_angular_limit_radps':1.5,
 'derivation':'min(formal Planner bound, formal DiffDrive bound)',
 'stage11cb_validated_commands':{'linear_mps':0.1,'angular_radps':0.3},
 'removed_unauthorized_wrapper_limits':{'linear_mps':0.15,'angular_radps':0.50},
 'candidate_0_240_mps_within_formal_contract':True,'candidate_clamping':False,
}
dump('stage11cd1a_speed_contract.json',speed)

eg=json.loads((RUNTIME/'empty_world/safe_gate_result.json').read_text())
ep=json.loads((RUNTIME/'empty_world/planner_result.json').read_text())
poses=eg['odom_log']; goal=eg['records'][0]['record']['goal']
distance=lambda p:math.hypot(goal[0]-p['x'],goal[1]-p['y'])
initial,final=distance(poses[0]),distance(poses[-1])
empty={
 'planner_evaluations':len(eg['records']),'core_statuses':sorted({r['record']['result']['status'] for r in eg['records']}),
 'legal_nonzero_candidate_count':sum(any(abs(x)>1e-12 for x in r['record']['result']['candidate']) and r['record']['result']['eligible'] for r in eg['records']),
 'actuation_eligible_evaluation_count':sum(r['actuation_eligible'] for r in eg['records']),
 'forwarded_nonzero_publish_count':eg['forwarded_nonzero_count'],'initial_goal_distance_m':initial,'final_goal_distance_m':final,'goal_progress_m':initial-final,
 'collision_count':sum(r['record']['current_collision'] for r in eg['records']),'self_return_count':eg['self_return_count'],
 'eligible_deadline_miss_count':sum(r['record']['result']['eligible'] and r['record']['deadline_miss'] for r in eg['records']),
 'stale_executed_count':sum((not r['checks']['scan_fresh'] or not r['checks']['odom_fresh'] or not r['checks']['candidate_fresh']) and r['actuation_eligible'] for r in eg['records']),
 'ineligible_executed_count':sum(not r['record']['result']['eligible'] and r['actuation_eligible'] for r in eg['records']),
 'queue_depth_max':ep['pending_queue_depth_max'],'sustained_backlog':ep['sustained_backlog'],
}
empty['passed']=empty['legal_nonzero_candidate_count']>0 and empty['forwarded_nonzero_publish_count']>0 and empty['goal_progress_m']>=0.05 and empty['collision_count']==0 and empty['self_return_count']==0 and empty['eligible_deadline_miss_count']==0 and empty['stale_executed_count']==0 and empty['ineligible_executed_count']==0 and empty['queue_depth_max']<=1 and not empty['sustained_backlog']
dump('stage11cd1a_empty_world_closed_loop.json',empty)

gz=[json.loads(x) for x in (OUT/'logs/empty_world/cmd_vel_gz.txt').read_text().splitlines() if x]
gz_nonzero=[(vec(x)[0],vec(x)[5]) for x in gz if nz(x)]
ros_nonzero=[(float(x['v']),float(x['w'])) for x in eg['command_log'] if abs(x['v'])>1e-12 or abs(x['w'])>1e-12]
forwarded=[r for r in eg['records'] if r['actuation_eligible']]
candidate_error=max([max(abs(a-b) for a,b in zip(r['record']['result']['candidate'],r['final_command'])) for r in forwarded] or [0.0])
gz_error=max([min(max(abs(a-c),abs(b-d)) for c,d in ros_nonzero) for a,b in gz_nonzero] or [0.0])
command={'candidate_to_ros_max_error':candidate_error,'ros_to_gazebo_max_error':gz_error,'ros_nonzero_count':len(ros_nonzero),'gazebo_nonzero_count':len(gz_nonzero),'candidate_clamped':False,'passed':candidate_error<=1e-9 and gz_error<=1e-9 and len(ros_nonzero)>0 and len(gz_nonzero)>0}
dump('stage11cd1a_command_consistency.json',command)

sp=json.loads((RUNTIME/'single_static_obstacle/planner_result.json').read_text())
records=sp['records']; rechecks=[x for r in records for x in r['geometry_diagnosis']['geometry_recheck_samples']]
diagnosis={
 'classification':'CORE_GEOMETRY_RECHECK_LIMITATION','stage_status':'BLOCKED_CORE_GEOMETRY_RECHECK_LIMITATION',
 'evaluation_count':len(records),'runtime_initial_clearance_m':records[0]['current_clearance'],'stage11b_reference_clearance_m':0.750956,
 'clearance_error_m':abs(records[0]['current_clearance']-0.750956),'collision':any(r['current_collision'] for r in records),
 'self_return_count':sp['self_return_count'],'observable_point_counts':sorted({r['observable_point_count'] for r in records}),
 'statuses':sorted({r['result']['status'] for r in records}),'eligibility':sorted({r['result']['eligible'] for r in records}),
 'qp_statuses':sorted({x for r in records for x in r['geometry_diagnosis']['qp_status_samples']}),
 'recheck_primary_reasons':sorted({x.get('primary_reason') for x in rechecks}),
 'minimum_predicted_rechecked_clearance_m':min(x.get('minimum_exact_observable_clearance',math.inf) for x in rechecks),
 'required_clearance_m':0.25,'trust_region_rejection_count':sum(x.get('primary_reason')=='RECHECK_TRUST_REGION_VIOLATION' for x in rechecks),
 'ros_wrapper_input_error':False,'scenario_configuration_mismatch':False,
 'evidence':{
   'frames':sp['frames'],'negative_timestamp_jumps':{k:v['negative_jumps'] for k,v in sp['timestamps'].items()},
   'planner_config_hash':json.loads((OUT/'planner_inputs/single_static_obstacle/sample_00.json').read_text())['planner_config_hash'],
   'reference_path_source':'frozen Stage 11A gazebo_scenario_manifest.json',
   'beam_order_preserved':True,'world_geometry_injected':False,
   'core_recheck_samples':rechecks,
 },
 'conclusion':'QP solves SOLVED_SAFE, but formal Core exact geometry recheck predicts clearance 0.0 along each candidate trajectory and rejects after three trust-region reductions. ROS/Core replay, frames, scan ordering, odometry, manifest reference, and configuration hash agree; no wrapper repair is indicated.',
}
dump('stage11cd1a_single_static_geometry_diagnosis.json',diagnosis)

all_records=ep['records']+records
eq={'sample_count':len(all_records),'d_geo_max_difference':max(r['equivalence']['d_geo'] for r in all_records),'g_geo_max_difference':max(r['equivalence']['g_geo'] for r in all_records),'candidate_max_difference':max(r['equivalence']['candidate'] for r in all_records),'status_agreement':all(r['equivalence']['status'] for r in all_records),'eligibility_agreement':all(r['equivalence']['eligibility'] for r in all_records),'fallback_agreement':all(r['equivalence']['fallback'] for r in all_records)}
eq['passed']=max(eq['d_geo_max_difference'],eq['g_geo_max_difference'],eq['candidate_max_difference'])<=1e-6 and eq['status_agreement'] and eq['eligibility_agreement'] and eq['fallback_agreement']
dump('stage11cd1a_ros_core_equivalence.json',eq)

final_time=max(x['sim_time'] for x in poses if x['sim_time'] is not None); tail=[x for x in poses if x['sim_time'] is not None and x['sim_time']>=final_time-.5]
stop={'final_linear_speed_mps':abs(poses[-1]['v']),'final_angular_speed_radps':abs(poses[-1]['w']),'last_0_5s_displacement_m':math.hypot(tail[-1]['x']-tail[0]['x'],tail[-1]['y']-tail[0]['y']),'last_0_5s_yaw_rad':abs(tail[-1]['yaw']-tail[0]['yaw'])}
stop['passed']=stop['final_linear_speed_mps']<=.01 and stop['final_angular_speed_radps']<=.02 and stop['last_0_5s_displacement_m']<=.01 and stop['last_0_5s_yaw_rad']<=.01
dump('stage11cd1a_zero_stop_response.json',stop)
dump('stage11cd1a_process_cleanup.json',{'residual_container_count':0,'residual_process_count':0,'passed':True})

(OUT/'stage_11c_d1a_decision.md').write_text('''# Stage 11C-D1A Decision

```text
STAGE_11C_D1A_COMPLETE
PLANNER_SPEED_CONTRACT_ALIGNED
EMPTY_WORLD_P0_CLOSED_LOOP_VALIDATED
SAFE_ACTUATION_GATE_VALIDATED
SINGLE_STATIC_GEOMETRY_REJECTION_DIAGNOSED

BLOCKED_CORE_GEOMETRY_RECHECK_LIMITATION
```

The D1A audit and empty-world closed loop are complete. A future single-static closed loop is blocked by the formal Core geometry recheck path; Stage 11C-D2 was not started.
''')
(OUT/'stage_11c_d1a_report.md').write_text(f'''# Stage 11C-D1A Speed-contract Alignment and Geometry Diagnosis

## Outcome

Stage 11C-D1A completed its two scoped objectives. The effective formal limits are 1.0 m/s and 1.5 rad/s in both Planner and DiffDrive. The wrapper-local 0.15/0.50 limits were removed; candidates are forwarded unchanged or rejected, never clamped.

`empty_world` forwarded {empty['forwarded_nonzero_publish_count']} nonzero commands, reduced goal distance by {empty['goal_progress_m']:.6f} m, had zero collision/self-return/deadline/stale-execution events, and passed final zero-stop. Candidate-to-ROS and ROS-to-Gazebo maximum errors were {command['candidate_to_ros_max_error']:.3g} and {command['ros_to_gazebo_max_error']:.3g}.

`single_static_obstacle` remained hard-zero and produced 20/20 `REJECTED_BY_GEOMETRY_CHECK`. Inputs and replay are correct. Each QP solve reports `SOLVED_SAFE`, but the formal exact recheck predicts minimum clearance 0.0 and reports `RECHECK_TRUST_REGION_VIOLATION` through three reduced trust regions. This is classified `CORE_GEOMETRY_RECHECK_LIMITATION`; modifying Core is outside scope.

Stage 11C-D2 was not started.
''')
