"""Static-world closed-loop simulator and metrics."""

from __future__ import annotations

import numpy as np
import time

from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.planner.dynamics import step
from sgcf_nrmp.planner.geometry_checker import ExactGeometryChecker
from sgcf_nrmp.planner.reference import local_reference
from sgcf_nrmp.planner.solver_result import PlannerStatus
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


def run_closed_loop(planner,scene,path,config,lidar_config:LidarConfig,max_steps=120,seed=0):
    state=path[0].copy(); footprint=rectangular_footprint(config["robot"]["footprint_length_m"],config["robot"]["footprint_width_m"]); states=[state.copy()]; controls=[]; statuses=[]; results=[]; solve_times=[]; cycle_times=[]; fallback_count=0; emergency_count=0; rejections=0; rng=np.random.default_rng(seed); previous=np.zeros(2)
    for _ in range(max_steps):
        cycle_started=time.perf_counter()
        scan=scene.scan(Pose2D(*map(float,state)),lidar_config,rng); checker=ExactGeometryChecker(scene,scan,footprint,lidar_config.range_max); reference=local_reference(state,path,planner.T,config["planner"]["reference_speed_mps"]*planner.dt); result=planner.plan(state,reference,checker,previous); control=result.first_control
        cycle_times.append((time.perf_counter()-cycle_started)*1000.)
        if result.status not in (PlannerStatus.SOLVED_SAFE,PlannerStatus.SOLVED_WITH_SLACK): fallback_count+=1
        if result.status == PlannerStatus.EMERGENCY_STOP: emergency_count+=1
        state=step(state,control,planner.dt); state[2]=(state[2]+np.pi)%(2*np.pi)-np.pi; states.append(state.copy()); controls.append(control.copy()); statuses.append(result.status.value); results.append(result); solve_times.append(result.solve_time_ms); rejections+=result.rejection_count; previous=control
        if np.linalg.norm(state[:2]-path[-1,:2])<.25: break
        if result.status in (PlannerStatus.EMERGENCY_STOP,PlannerStatus.INFEASIBLE,PlannerStatus.SOLVER_TIMEOUT,PlannerStatus.NUMERICAL_ERROR,PlannerStatus.REJECTED_BY_GEOMETRY_CHECK): break
    states=np.asarray(states); controls=np.asarray(controls); evaluation_rng=np.random.default_rng(seed+991); labels=[]
    for s in states:
        evaluation_scan=scene.scan(Pose2D(*map(float,s)),lidar_config,evaluation_rng); labels.append(scene.label(footprint,Pose2D(*map(float,s)),evaluation_scan,lidar_config.range_max))
    observable=np.asarray([l.observable_clearance for l in labels]); world=np.asarray([l.world_clearance for l in labels]); success=bool(np.linalg.norm(states[-1,:2]-path[-1,:2])<.25)
    smooth=float(np.mean(np.linalg.norm(np.diff(controls,axis=0),axis=1))) if len(controls)>1 else 0.; length=float(np.sum(np.linalg.norm(np.diff(states[:,:2],axis=0),axis=1)))
    qp_iterations=[value for result in results for value in result.diagnostics.get("solve_wall_ms",[])]
    timing_keys=("geometry_query_ms","parameter_update_ms","solve_wall_ms","osqp_internal_ms","recheck_ms")
    timing={key:[value for result in results for value in result.diagnostics.get(key,[])] for key in timing_keys}
    percentile=lambda values,p: float(np.percentile(values,p)) if values else 0.
    return {"states":states,"controls":controls,"statuses":statuses,"results":results,"cycle_times_ms":cycle_times,"timing_samples_ms":timing,"metrics":{"success":success,"steps":len(controls),"navigation_time_s":len(controls)*planner.dt,"path_length_m":length,"control_smoothness":smooth,"min_observable_clearance_m":float(observable.min()),"min_world_clearance_m":float(world.min()),"observable_collision":bool(np.any(observable<=0)),"world_collision":bool(np.any(world<=0)),"partial_observation_world_risk":bool(any(r.partial_observation_world_risk for r in results)),"average_qp_solve_ms":float(np.mean(qp_iterations)) if qp_iterations else 0.,"p95_qp_solve_ms":percentile(qp_iterations,95),"max_qp_solve_ms":float(max(qp_iterations,default=0.)),"average_end_to_end_ms":float(np.mean(cycle_times)) if cycle_times else 0.,"p95_end_to_end_ms":percentile(cycle_times,95),"max_end_to_end_ms":float(max(cycle_times,default=0.)),"end_to_end_over_200ms_count":int(np.count_nonzero(np.asarray(cycle_times)>200.)),"scp_iterations_mean":float(np.mean([r.scp_iterations for r in results])) if results else 0.,"max_slack":float(max((np.max(r.slack) for r in results),default=0.)),"geometry_recheck_rejections":rejections,"fallback_count":fallback_count,"emergency_stop_count":emergency_count}}
