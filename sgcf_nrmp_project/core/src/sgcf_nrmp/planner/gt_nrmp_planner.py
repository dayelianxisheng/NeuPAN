"""Trust-region SCP planner driven only by exact observable geometry."""

from __future__ import annotations

import numpy as np
import time

from sgcf_nrmp.planner.angle_utils import wrap_angle
from sgcf_nrmp.planner.dynamics import rollout
from sgcf_nrmp.planner.fallback import fallback_control
from sgcf_nrmp.planner.geometry_checker import ExactGeometryChecker
from sgcf_nrmp.planner.qp_problem import PersistentPlannerQP
from sgcf_nrmp.planner.solver_result import PlannerStatus,SolverResult
from sgcf_nrmp.planner.trust_region import TrustRegion


class GTNRMPPlanner:
    def __init__(self,config:dict):
        self.config=config; self.T=int(config["planner"]["horizon"]); self.dt=float(config["planner"]["dt_s"]); self.previous_controls=None; self.last_safe_control=None
        self.qp = PersistentPlannerQP(config)

    def _initial_controls(self,state,reference):
        if self.previous_controls is not None:
            return np.vstack((self.previous_controls[1:],self.previous_controls[-1:]))
        controls=[]; bounds=self.config["bounds"]
        for k in range(self.T):
            delta=reference[k+1,:2]-reference[k,:2]; heading=np.arctan2(delta[1],delta[0]) if np.linalg.norm(delta)>1e-8 else reference[k,2]; v=np.linalg.norm(delta)/self.dt; omega=wrap_angle(heading-reference[k,2])/self.dt
            controls.append([np.clip(v,bounds["v_min_mps"],bounds["v_max_mps"]),np.clip(omega,bounds["omega_min_radps"],bounds["omega_max_radps"])])
        return np.asarray(controls)

    def plan(self,state,reference,checker:ExactGeometryChecker,previous_control=None,simulate_timeout=False,simulate_infeasible=False,trust_override:TrustRegion|None=None):
        cycle_started=time.perf_counter(); timing={"geometry_query_ms":[],"parameter_update_ms":[],"solve_wall_ms":[],"osqp_internal_ms":[],"recheck_ms":[]}
        state=np.asarray(state,float); previous_control=np.zeros(2) if previous_control is None else np.asarray(previous_control,float); controls=self._initial_controls(state,reference)
        bounds=self.config["bounds"]; prior=previous_control.copy()
        for control in controls:
            control[0]=np.clip(control[0],prior[0]+bounds["acceleration_min_mps2"]*self.dt,prior[0]+bounds["acceleration_max_mps2"]*self.dt); control[1]=np.clip(control[1],prior[1]+bounds["angular_acceleration_min_radps2"]*self.dt,prior[1]+bounds["angular_acceleration_max_radps2"]*self.dt); prior=control.copy()
        nominal=rollout(state,controls,self.dt); trust=trust_override or TrustRegion.from_dict(self.config["trust_region"]); total_time=0.; rejections=0; last_status=PlannerStatus.MAX_ITERATIONS; last_candidate=None
        recheck_started=time.perf_counter(); current=checker.recheck(state[None,:],self.config["planner"]["d_safe_m"]); timing["recheck_ms"].append((time.perf_counter()-recheck_started)*1000.)
        if current["min_observable"]<self.config["planner"]["emergency_distance_m"]:
            zeros=np.zeros((self.T,2)); timing["end_to_end_ms"]=(time.perf_counter()-cycle_started)*1000.; return SolverResult(PlannerStatus.EMERGENCY_STOP,rollout(state,zeros,self.dt),zeros,np.zeros(self.T),min_observable_clearance=current["min_observable"],min_world_clearance=current["min_world"],diagnostics=timing)
        for iteration in range(1,int(self.config["planner"]["scp_iterations"])+1):
            geometry_started=time.perf_counter(); distances,gradients,valid=checker.linearization(nominal); timing["geometry_query_ms"].append((time.perf_counter()-geometry_started)*1000.)
            timing["parameter_update_ms"].append(self.qp.update(state,reference,nominal,controls,previous_control,distances,gradients,valid,trust))
            status,values,elapsed,internal=self.qp.solve(simulate_timeout,simulate_infeasible); timing["solve_wall_ms"].append(elapsed); timing["osqp_internal_ms"].append(internal); total_time+=elapsed; last_status=status
            if values is None:
                fallback=fallback_control(status,self.last_safe_control); fallback_controls=np.tile(fallback,(self.T,1)); timing["end_to_end_ms"]=(time.perf_counter()-cycle_started)*1000.; return SolverResult(status,rollout(state,fallback_controls,self.dt),fallback_controls,np.zeros(self.T),solve_time_ms=total_time,scp_iterations=iteration,diagnostics=timing)
            qp_states,qp_controls,qp_slack=values; candidate=rollout(state,qp_controls,self.dt); recheck_started=time.perf_counter(); check=checker.recheck(candidate,self.config["planner"]["d_safe_m"]); timing["recheck_ms"].append((time.perf_counter()-recheck_started)*1000.); last_candidate=(candidate,qp_controls,qp_slack,self.qp.problem.value,check)
            if check["violated_points"]:
                rejections+=1; trust=trust.scaled(.5); last_status=PlannerStatus.REJECTED_BY_GEOMETRY_CHECK
                if rejections>int(self.config["planner"]["max_rejections"]): break
                continue
            difference=float(np.linalg.norm(qp_controls-controls)); nominal=candidate; controls=qp_controls
            if difference<self.config["planner"]["convergence_tolerance"]: break
        if last_candidate is None:
            zeros=np.zeros((self.T,2)); timing["end_to_end_ms"]=(time.perf_counter()-cycle_started)*1000.; return SolverResult(last_status,rollout(state,zeros,self.dt),zeros,np.zeros(self.T),solve_time_ms=total_time,scp_iterations=iteration,rejection_count=rejections,diagnostics=timing)
        candidate,controls,slack,objective,check=last_candidate
        if check["violated_points"]:
            zeros=np.zeros((self.T,2)); timing["end_to_end_ms"]=(time.perf_counter()-cycle_started)*1000.; return SolverResult(PlannerStatus.REJECTED_BY_GEOMETRY_CHECK,rollout(state,zeros,self.dt),zeros,slack,objective,total_time,iteration,check["min_observable"],check["min_world"],check["violated_points"],check["partial_observation_world_risk"],rejections,timing)
        maximum=float(np.max(slack)); final_status=PlannerStatus.SOLVED_WITH_SLACK if maximum>self.config["planner"]["slack_acceptance_m"] else PlannerStatus.SOLVED_SAFE
        self.previous_controls=controls.copy(); self.last_safe_control=controls[0].copy()
        timing["end_to_end_ms"]=(time.perf_counter()-cycle_started)*1000.
        return SolverResult(final_status,candidate,controls,slack,objective,total_time,iteration,check["min_observable"],check["min_world"],check["violated_points"],check["partial_observation_world_risk"],rejections,timing)
