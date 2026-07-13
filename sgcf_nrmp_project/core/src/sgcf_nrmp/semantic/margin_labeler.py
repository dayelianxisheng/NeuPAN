"""Bounded semantic-margin labels over one observable LiDAR point set."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SemanticMarginResult:
    semantic_margin: np.ndarray
    d_geo: np.ndarray
    effective_clearance: np.ndarray
    winning_point_index: np.ndarray
    winning_class_id: np.ndarray
    winning_instance_id: np.ndarray
    winning_point_distance: np.ndarray
    winning_configured_margin: np.ndarray
    max_visible_class_margin: float


def _rectangle_point_distances(queries,points,length,width):
    queries=np.asarray(queries,float); points=np.asarray(points,float).reshape((-1,2)); delta=points[None,:,:]-queries[:,None,:2]; c=np.cos(queries[:,2,None]); s=np.sin(queries[:,2,None]); local=np.stack((c*delta[...,0]+s*delta[...,1],-s*delta[...,0]+c*delta[...,1]),axis=-1); outside=np.maximum(np.abs(local)-np.array([length/2,width/2]),0.); return np.linalg.norm(outside,axis=-1)


def semantic_margin_ground_truth(queries,points_xy,class_ids,observable_mask,semantic_valid_mask,class_margin_by_id,length,width,truncation,instance_ids=None,tolerance=1e-9):
    """Compute m_sem using exactly the same observable points as d_geo.

    Every observable point participates in geometry. A semantic margin is applied
    only when its projection/reliability mask is valid; otherwise its margin is
    zero, so RGB can never remove or weaken LiDAR geometry.
    """
    queries=np.asarray(queries,float); points=np.asarray(points_xy,float).reshape((-1,2)); classes=np.asarray(class_ids,int).reshape(-1); observable=np.asarray(observable_mask,bool).reshape(-1); semantic_valid=np.asarray(semantic_valid_mask,bool).reshape(-1)
    if not (len(points)==len(classes)==len(observable)==len(semantic_valid)): raise ValueError("point metadata lengths differ")
    instances=np.full(len(points),-1,int) if instance_ids is None else np.asarray(instance_ids,int).reshape(-1)
    if len(instances)!=len(points): raise ValueError("instance_ids length differs")
    if not np.any(observable):
        count=len(queries); zeros=np.zeros(count); minus=np.full(count,-1,int); return SemanticMarginResult(zeros,np.full(count,truncation),np.full(count,truncation),minus,minus,minus,np.full(count,truncation),zeros,0.)
    distances=_rectangle_point_distances(queries,points,length,width); distances[:,~observable]=np.inf; raw_geo=np.min(distances,axis=1); d_geo=np.minimum(raw_geo,float(truncation))
    configured=np.asarray([float(class_margin_by_id.get(int(value),0.)) for value in classes]); configured=np.where(observable&semantic_valid,configured,0.); effective_matrix=distances-configured[None,:]; winner=np.argmin(effective_matrix,axis=1); effective=np.min(effective_matrix,axis=1); margin=np.maximum(0.,d_geo-effective)
    maximum=float(np.max(configured,initial=0.));
    if np.any(margin < -tolerance): raise AssertionError("semantic margin is negative")
    if np.any(margin > maximum+tolerance): raise AssertionError(f"semantic margin exceeds visible class bound: {margin.max()} > {maximum}")
    rows=np.arange(len(queries)); return SemanticMarginResult(margin,d_geo,effective,winner,classes[winner],instances[winner],distances[rows,winner],configured[winner],maximum)
