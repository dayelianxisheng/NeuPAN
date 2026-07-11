"""Observable-distance, collision, false-safe and world-risk metrics."""

from __future__ import annotations

import numpy as np


def clearance_metrics(prediction: np.ndarray, observable: np.ndarray, observable_collision: np.ndarray, world_collision: np.ndarray, d_safe: float, near_boundary_max: float, collision_logit: np.ndarray | None = None) -> tuple[dict[str,float],dict[str,object]]:
    prediction=np.asarray(prediction).reshape(-1); observable=np.asarray(observable).reshape(-1); observable_collision=np.asarray(observable_collision,dtype=bool).reshape(-1); world_collision=np.asarray(world_collision,dtype=bool).reshape(-1)
    error=prediction-observable; absolute=np.abs(error)
    def mae(mask): return float(np.mean(absolute[mask])) if np.any(mask) else float("nan")
    metrics={"mae":float(np.mean(absolute)),"rmse":float(np.sqrt(np.mean(error**2))),"median_absolute_error":float(np.median(absolute)),"p90_absolute_error":float(np.quantile(absolute,.9)),"near_boundary_mae":mae(observable<=near_boundary_max),"collision_region_mae":mae(observable_collision),"free_region_mae":mae(observable>near_boundary_max),"pearson_correlation":float(np.corrcoef(prediction,observable)[0,1])}
    predicted_unsafe=prediction<d_safe; unsafe=observable<d_safe; tp=np.sum(predicted_unsafe&unsafe); fp=np.sum(predicted_unsafe&~unsafe); fn=np.sum(~predicted_unsafe&unsafe); tn=np.sum(~predicted_unsafe&~unsafe)
    metrics.update({"safety_threshold_accuracy":float((tp+tn)/len(unsafe)),"safety_threshold_precision":float(tp/max(tp+fp,1)),"safety_threshold_recall":float(tp/max(tp+fn,1)),"safety_threshold_f1":float(2*tp/max(2*tp+fp+fn,1))})
    if collision_logit is not None:
        predicted_collision=np.asarray(collision_logit).reshape(-1)>=0; true=observable_collision; tp=np.sum(predicted_collision&true); fp=np.sum(predicted_collision&~true); fn=np.sum(~predicted_collision&true); tn=np.sum(~predicted_collision&~true)
        metrics.update({"collision_accuracy":float((tp+tn)/len(true)),"collision_precision":float(tp/max(tp+fp,1)),"collision_recall":float(tp/max(tp+fn,1)),"collision_f1":float(2*tp/max(2*tp+fp+fn,1))})
    model_false_safe=(prediction>=d_safe)&(observable<d_safe)
    world_risk=(prediction>=d_safe)&world_collision
    partial_observation=world_risk&(observable>=d_safe)
    model_error_world=world_risk&(observable<d_safe)
    report={"d_safe":d_safe,"model_false_safe_count":int(model_false_safe.sum()),"model_false_safe_rate":float(model_false_safe.mean()),"world_risk_count":int(world_risk.sum()),"world_risk_rate":float(world_risk.mean()),"world_risk_partial_observation_count":int(partial_observation.sum()),"world_risk_model_error_count":int(model_error_world.sum()),"model_false_safe_indices":np.flatnonzero(model_false_safe).tolist(),"world_risk_partial_observation_indices":np.flatnonzero(partial_observation).tolist()}
    return metrics,report
