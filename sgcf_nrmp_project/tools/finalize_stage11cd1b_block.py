#!/usr/bin/env python3
"""Record why the requested D1B Core patch would be an unsafe policy change."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d1b_core_recheck_fix'
OUT.mkdir(parents=True,exist_ok=True)
D1A=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d1a_speed_contract_and_geometry_diagnosis'
snapshot=json.loads((D1A/'planner_inputs/single_static_obstacle/sample_00.json').read_text())
runtime=json.loads((D1A/'runtime/single_static_obstacle/planner_result.json').read_text())
record=runtime['records'][0]
points=np.asarray(snapshot['laser']['observable_points_world'],float)

iterations=[]
for item in record['geometry_diagnosis']['geometry_recheck_samples']:
    candidate=np.asarray(item['candidate_trajectory'],float)
    exact=np.asarray(item['exact_rechecked_clearance'],float)
    overlaps=[]
    for index in np.flatnonzero(exact<=0.0):
        q=candidate[index]; c,s=math.cos(q[2]),math.sin(q[2]); delta=points-q[:2]
        local=np.column_stack((c*delta[:,0]+s*delta[:,1],-s*delta[:,0]+c*delta[:,1]))
        inside=(np.abs(local[:,0])<=.4+1e-12)&(np.abs(local[:,1])<=.25+1e-12)
        overlaps.append({'horizon_index':int(index),'pose':q.tolist(),'inside_observable_point_count':int(inside.sum()),'inside_observable_points_world':points[inside].tolist(),'inside_points_robot_frame':local[inside].tolist()})
    iterations.append({'iteration':item['iteration'],'qp_solver_status':item['solver_status'],'primary_reason':item['primary_reason'],'offending_indices':item['offending_indices'],'minimum_exact_clearance':item['minimum_exact_observable_clearance'],'linearized_clearance':item['linearized_clearance'],'exact_rechecked_clearance':item['exact_rechecked_clearance'],'trust_region':item['trust_region'],'trust_region_violation':item['trust_region_violation'],'overlap_proof':overlaps})

root_cause={
 'classification':'NO_CORE_CLEARANCE_DEFECT_FOUND',
 'requested_success_gate_met':False,
 'observed_zero_clearance_is_erroneous':False,
 'initial_clearance_m':record['current_clearance'],
 'observable_point_count':len(points),
 'qp_status_samples':record['geometry_diagnosis']['qp_status_samples'],
 'final_status':record['result']['status'],
 'root_cause':'The frozen avoid-reference nominal and each nonlinear QP candidate enter the observed cylinder surface within the 12-step horizon. Exact rectangle-to-point clearance correctly becomes 0.0 when observed points lie inside the robot footprint. Nominal collision slots have an unsigned zero distance and invalid gradient, so the QP relaxation can solve while the mandatory nonlinear exact recheck rejects the unsafe trajectory.',
 'candidate_state_order':'[x_m, y_m, yaw_rad] verified',
 'control_order':'[linear_velocity_mps, angular_velocity_radps] verified',
 'dt_s':0.2,'frame':'world points and world candidate poses verified','duplicate_pose_addition':False,'velocity_as_pose_delta':False,'dt_multiplied_twice':False,'batch_index_error':False,'yaw_wrap_error':False,'wrong_query_or_empty_field':False,'clearance_overwritten_with_zero':False,
 'iterations':iterations,
 'required_change_for_requested_eligibility':['relax or truncate the full-horizon exact recheck','change nominal/QP trajectory generation','change the clearance representation/gradient at collision'],
 'why_not_applied':'Each option changes Planner safety policy or main optimization behavior. The stage forbids threshold relaxation, disabling recheck, scenario logic, d_safe changes, or Planner-main rewrite.',
}

def dump(name,value): (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
dump('stage11cd1b_root_cause.json',root_cause)
dump('stage11cd1b_core_patch_audit.json',{'core_modified':False,'patch_applied':False,'files_changed_in_core':[],'reason':'No erroneous geometry value exists; patching acceptance would weaken the verified safety recheck.','core_source_hash_before_equals_after':True})
dump('stage11cd1b_offline_replay.json',{'snapshot':str((D1A/'planner_inputs/single_static_obstacle/sample_00.json').relative_to(ROOT)),'snapshot_sha256':hashlib.sha256((D1A/'planner_inputs/single_static_obstacle/sample_00.json').read_bytes()).hexdigest(),'formal_status_reproduced':'REJECTED_BY_GEOMETRY_CHECK','qp_status_reproduced':['SOLVED_SAFE','SOLVED_SAFE','SOLVED_SAFE'],'minimum_clearance_reproduced':0.0,'independent_overlap_proof':True,'candidate_unchanged':True,'command_eligible':False,'passed_requested_offline_gate':False})
dump('stage11cd1b_regression_matrix.json',{'empty_world':{'not_rerun':True,'frozen_D1A_status':'SOLVED_SAFE','reason':'No patch applied'},'initial_collision':{'not_rerun':True,'frozen_status':'EMERGENCY_STOP','reason':'No patch applied'},'semantic_infeasible':{'not_rerun':True,'frozen_status':'GEOMETRICALLY_INFEASIBLE','reason':'No patch applied'},'stage05_stage09b_suite':{'not_rerun':True,'reason':'Stopped before mutation because the proposed patch would weaken safety policy'}})
for name in ('stage11cd1b_single_static_closed_loop.json','stage11cd1b_command_consistency.json','stage11cd1b_clearance_and_collision.json','stage11cd1b_zero_stop_response.json'):
    dump(name,{'executed':False,'status':'NOT_RUN_OFFLINE_SAFETY_GATE_FAILED','reason':'The frozen candidate trajectory truly overlaps observed obstacle points; runtime nonzero execution was not authorized after offline failure.'})
dump('stage11cd1b_process_cleanup.json',{'residual_container_count':0,'residual_process_count':0,'gazebo_started':False,'passed':True})
(OUT/'files_changed.txt').write_text('sgcf_nrmp_project/tools/finalize_stage11cd1b_block.py\nsgcf_nrmp_project/artifacts/stages/stage_11c_d1b_core_recheck_fix/\n')
(OUT/'stage_11c_d1b_decision.md').write_text('''# Stage 11C-D1B Decision

```text
BLOCKED_CORE_GEOMETRY_RECHECK_FIX_UNSAFE
```

The alleged erroneous 0.0 clearance is a real observable collision along the nonlinear candidate horizon. No Core patch was applied and the single-static runtime closed loop was not started.
''')
(OUT/'stage_11c_d1b_report.md').write_text('''# Stage 11C-D1B Core Geometry Recheck Investigation

## Outcome

`BLOCKED_CORE_GEOMETRY_RECHECK_FIX_UNSAFE`

The D1A snapshot deterministically reproduces three `SOLVED_SAFE` QP results followed by `RECHECK_TRUST_REGION_VIOLATION` and minimum exact clearance 0.0. Independent rectangle-frame calculations prove the zero is correct: from horizon index 7 onward, multiple actual LiDAR cylinder-surface points lie inside the 0.8 × 0.5 m robot footprint.

The problem is not variable ordering, units, frame conversion, odometry, duplicate pose integration, dt multiplication, yaw wrapping, empty-point use, batch indexing, or result overwrite. The nominal trajectory itself crosses the obstacle; collision states have unsigned distance zero and invalid geometry gradients, so relaxed QP slots can solve while the nonlinear exact recheck correctly rejects the unsafe result.

Making the pre-fix QP candidate eligible would require weakening/truncating horizon recheck or changing Planner nominal/QP behavior. Both are safety-policy or Planner-main changes prohibited by this stage. Core was left unchanged, Gazebo was not started, and Stage 11C-D2 was not started.
''')
