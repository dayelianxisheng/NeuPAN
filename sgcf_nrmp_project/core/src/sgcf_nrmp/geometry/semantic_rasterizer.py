"""Deterministic lightweight z-buffer rasterization of convex semantic prisms."""

import numpy as np
from matplotlib.path import Path as MplPath
from sgcf_nrmp.geometry.camera_projection import project_lidar_points,transform_points
from sgcf_nrmp.types.camera import CameraIntrinsics
from sgcf_nrmp.types.multimodal import OracleSemanticImages


def _prism_vertices(obstacle):
    xy=np.asarray(obstacle.footprint_world.exterior.coords)[:-1]; low=np.c_[xy,np.zeros(len(xy))]; high=np.c_[xy,np.full(len(xy),obstacle.height)]; return np.vstack((low,high))


def rasterize_semantic_prisms(obstacles,T_camera_world,intrinsics:CameraIntrinsics)->OracleSemanticImages:
    h,w=intrinsics.height,intrinsics.width; semantic=np.zeros((h,w),np.int32); instance=np.zeros((h,w),np.int32); depth=np.full((h,w),np.inf,np.float64); rgb=np.zeros((h,w,3),np.float32)
    yy,xx=np.mgrid[0:h,0:w]; pixels=np.c_[xx.ravel()+.5,yy.ravel()+.5]
    for obstacle in obstacles:
        vertices=_prism_vertices(obstacle); projected=project_lidar_points(vertices,np.ones(len(vertices),bool),T_camera_world,intrinsics); valid=projected.valid_mask
        if np.count_nonzero(valid)<3: continue
        uv=projected.uv[valid]; center=uv.mean(0); angles=np.arctan2(uv[:,1]-center[1],uv[:,0]-center[0]); hull=uv[np.argsort(angles)]; mask=MplPath(hull).contains_points(pixels).reshape(h,w)
        camera_vertices=transform_points(vertices,T_camera_world); object_depth=float(np.min(camera_vertices[camera_vertices[:,2]>intrinsics.minimum_depth,2])); replace=mask&(object_depth<depth)
        depth[replace]=object_depth; semantic[replace]=int(obstacle.semantic_class); instance[replace]=obstacle.instance_id; rgb[replace]=obstacle.visual_color
    return OracleSemanticImages(semantic,instance,np.where(np.isfinite(depth),depth,0.0),rgb)
