"""Order-preserving oracle PointPainting baseline."""

import numpy as np
from sgcf_nrmp.types.multimodal import PaintedPoints
from sgcf_nrmp.types.semantic import SemanticClass


def paint_points(points_xy,ranges,projection,semantic_image,image_age_s,class_count=5,label_smoothing=0.,max_image_age_s=.1,border_soft_width_px=12.,depth_tolerance_m=.2,rgb_available=True):
    points=np.asarray(points_xy,np.float64); ranges=np.asarray(ranges,np.float64); n=len(points); class_ids=np.zeros(n,np.int64); valid=projection.valid_mask.copy()&bool(rgb_available)&(image_age_s<=max_image_age_s)
    indices=np.flatnonzero(valid); uv=np.rint(projection.uv[indices]).astype(int); uv[:,0]=np.clip(uv[:,0],0,semantic_image.shape[1]-1); uv[:,1]=np.clip(uv[:,1],0,semantic_image.shape[0]-1); class_ids[indices]=semantic_image[uv[:,1],uv[:,0]]; valid &= class_ids!=int(SemanticClass.UNKNOWN)
    confidence=np.where(valid,np.clip(projection.border_distance_px/max(border_soft_width_px,1e-9),0,1),0.); probs=np.full((n,class_count),label_smoothing/max(class_count-1,1),np.float64); probs[np.arange(n),class_ids]=1-label_smoothing; probs[~valid]=0.; probs[~valid,0]=1.
    features=np.c_[points,ranges,probs,valid.astype(float),confidence,np.full(n,image_age_s)]; return PaintedPoints(features,class_ids,probs,valid,confidence,confidence.copy())
