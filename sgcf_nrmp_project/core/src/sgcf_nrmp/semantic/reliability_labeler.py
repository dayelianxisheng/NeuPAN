"""Deterministic reliability ground truth for projection/synchronization quality."""

import numpy as np


def reliability_ground_truth(projection_valid,border_distance_px,class_ids,image_age_s,max_image_age_s=.1,border_soft_width_px=12.,rgb_available=True,calibration_quality=1.,occlusion_edge=None):
    valid=np.asarray(projection_valid,bool); classes=np.asarray(class_ids); reliability=np.where(valid&(classes!=0),1.,0.)
    reliability*=np.clip(np.asarray(border_distance_px,float)/max(border_soft_width_px,1e-9),0,1); reliability*=float(np.clip(calibration_quality,0,1))
    if not rgb_available or image_age_s>max_image_age_s: reliability[:]=0
    if occlusion_edge is not None: reliability*=np.where(np.asarray(occlusion_edge,bool),.5,1.)
    return np.clip(reliability,0,1)
