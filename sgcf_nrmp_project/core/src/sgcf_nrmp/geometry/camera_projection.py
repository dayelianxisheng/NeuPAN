"""Vectorized pinhole projection for LiDAR points."""

import numpy as np
from sgcf_nrmp.types.camera import CameraIntrinsics,ProjectionResult


def invert_transform(T_target_source:np.ndarray)->np.ndarray:
    T=np.asarray(T_target_source,float); result=np.eye(4); result[:3,:3]=T[:3,:3].T; result[:3,3]=-result[:3,:3]@T[:3,3]; return result


def transform_points(points_source:np.ndarray,T_target_source:np.ndarray)->np.ndarray:
    points=np.asarray(points_source,float); T=np.asarray(T_target_source,float)
    if points.ndim!=2 or points.shape[1]!=3 or T.shape!=(4,4): raise ValueError("points [N,3], transform [4,4] required")
    return (np.c_[points,np.ones(len(points))]@T.T)[:,:3]


def project_lidar_points(points_lidar:np.ndarray,valid_lidar:np.ndarray,T_camera_lidar:np.ndarray,intrinsics:CameraIntrinsics)->ProjectionResult:
    points=transform_points(points_lidar,T_camera_lidar); valid=np.asarray(valid_lidar,bool).reshape(-1)
    if len(valid)!=len(points): raise ValueError("valid mask length differs")
    z=points[:,2]; safe=np.where(np.abs(z)>1e-15,z,1.); u=intrinsics.fx*points[:,0]/safe+intrinsics.cx; v=intrinsics.fy*points[:,1]/safe+intrinsics.cy; uv=np.c_[u,v]
    inside=(z>intrinsics.minimum_depth)&(u>=0)&(u<intrinsics.width)&(v>=0)&(v<intrinsics.height); projected=valid&inside&np.isfinite(uv).all(1)
    border=np.minimum.reduce((u,v,intrinsics.width-1-u,intrinsics.height-1-v)); border=np.where(projected,np.maximum(border,0.),0.)
    return ProjectionResult(uv,z,projected,border)
