"""Unit-aware translation/yaw gradient and local-linearity metrics."""

from __future__ import annotations

import numpy as np


def gradient_metrics(predicted: np.ndarray, target: np.ndarray, valid: np.ndarray, linearity_error: np.ndarray) -> dict[str,float]:
    predicted=np.asarray(predicted)[valid]; target=np.asarray(target)[valid]
    xy_error=predicted[:,:2]-target[:,:2]; yaw_error=predicted[:,2]-target[:,2]
    numerator=np.sum(predicted[:,:2]*target[:,:2],axis=1); denominator=np.linalg.norm(predicted[:,:2],axis=1)*np.linalg.norm(target[:,:2],axis=1); usable=denominator>1e-8
    return {"valid_count":int(len(predicted)),"translation_l1":float(np.mean(np.abs(xy_error))),"translation_l2":float(np.mean(np.linalg.norm(xy_error,axis=1))),"translation_cosine_similarity":float(np.mean(numerator[usable]/denominator[usable])) if np.any(usable) else float("nan"),"x_mae":float(np.mean(np.abs(xy_error[:,0]))),"y_mae":float(np.mean(np.abs(xy_error[:,1]))),"yaw_mae_per_radian":float(np.mean(np.abs(yaw_error))),"yaw_rmse_per_radian":float(np.sqrt(np.mean(yaw_error**2))),"local_linearity_mae_m":float(np.mean(linearity_error))}
