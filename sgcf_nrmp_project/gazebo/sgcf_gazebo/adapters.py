"""Pure-Python Gazebo adapters that preserve the frozen SGCF information boundary."""

from __future__ import annotations

import math
import numpy as np

from .contracts import (
    GazeboCameraInfo, GazeboImageFrame, GazeboOracleSemanticFrame, GazeboRobotState,
    GazeboScanFrame, GazeboTransformSnapshot, PlannerInputFrame, PlannerOutputFrame,
)


class GazeboLidarAdapter:
    """Convert ordered ranges to base-frame points without deleting samples."""

    def scan_to_observable_points(self,scan:GazeboScanFrame,transform:GazeboTransformSnapshot)->PlannerInputFrame:
        ranges=np.asarray(scan.ranges,dtype=np.float64).reshape(-1); indices=np.arange(len(ranges)); angles=scan.angle_min_rad+indices*scan.angle_increment_rad
        valid=bool(scan.valid and transform.valid) & np.isfinite(ranges) & (ranges>=scan.range_min_m) & (ranges<scan.range_max_m)
        points_lidar=np.c_[ranges*np.cos(angles),ranges*np.sin(angles),np.zeros(len(ranges))]
        points_lidar[~valid]=0.; T=np.asarray(transform.T_target_source,float)
        if T.shape!=(4,4) or transform.target_frame!="base_link" or transform.source_frame!=scan.frame_id: raise ValueError("T_base_link_lidar_link required")
        points=(np.c_[points_lidar,np.ones(len(points_lidar))]@T.T)[:,:2]; points[~valid]=0.
        return PlannerInputFrame(scan.timestamp_s,"base_link",scan.sequence_id,bool(scan.valid and transform.valid),"GAZEBO_LIDAR",points,valid,ranges.copy())


class GazeboCameraAdapter:
    """Validate RGB and Stage-07 intrinsics; projection remains in Stage 07."""

    def image_to_stage07_input(self,image:GazeboImageFrame,camera_info:GazeboCameraInfo,transform:GazeboTransformSnapshot)->dict:
        rgb=np.asarray(image.image_rgb)
        if rgb.shape!=(camera_info.height,camera_info.width,3): raise ValueError("RGB/image-info shape mismatch")
        if image.frame_id!="camera_optical_frame" or camera_info.frame_id!="camera_optical_frame": raise ValueError("camera optical frame required")
        if transform.target_frame!="camera_optical_frame" or transform.source_frame!="lidar_link": raise ValueError("T_camera_optical_frame_lidar_link required")
        return {"image_rgb":rgb.copy(),"intrinsics":{"fx":camera_info.fx,"fy":camera_info.fy,"cx":camera_info.cx,"cy":camera_info.cy,"width":camera_info.width,"height":camera_info.height,"minimum_depth":.05},"T_camera_lidar":np.asarray(transform.T_target_source,float).copy(),"timestamp_s":image.timestamp_s,"valid":bool(image.valid and camera_info.valid and transform.valid)}


class GazeboRobotStateAdapter:
    def pose_twist_to_planner_state(self,state:GazeboRobotState)->dict:
        q=np.asarray(state.orientation_xyzw,float); norm=np.linalg.norm(q)
        if q.shape!=(4,) or norm<=0 or not np.isfinite(q).all(): raise ValueError("finite xyzw quaternion required")
        x,y,z,w=q/norm; yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        return {"timestamp_s":state.timestamp_s,"state_xyyaw":np.asarray([state.position_xyz[0],state.position_xyz[1],yaw]),"control_vw":np.asarray(state.twist_vw,float).copy(),"valid":state.valid}


class GazeboOracleSemanticAdapter:
    """Simulation-only class transport; never alters LiDAR coordinates or mask."""

    def semantic_input_for_stage07(self,planner_input:PlannerInputFrame,semantic:GazeboOracleSemanticFrame)->PlannerInputFrame:
        classes=np.asarray(semantic.class_ids,dtype=np.int64).reshape(-1)
        if not semantic.simulation_only or not semantic.ground_truth_only: raise ValueError("Oracle sidecar must be simulation ground truth")
        if len(classes)!=len(planner_input.points_xy) or np.any((classes<0)|(classes>4)): raise ValueError("one valid semantic ID per LiDAR sample required")
        return PlannerInputFrame(planner_input.timestamp_s,planner_input.frame_id,planner_input.sequence_id,bool(planner_input.valid and semantic.valid),"GAZEBO_ORACLE_SEMANTIC_SIDECAR",planner_input.points_xy.copy(),planner_input.point_valid_mask.copy(),planner_input.ranges.copy(),classes.copy())


def r1_semantic_enabled(*,image_present:bool,image_age_s:float,projection_valid:bool,unknown:bool,max_image_age_s:float=.1)->bool:
    return bool(image_present and image_age_s<=max_image_age_s and projection_valid and not unknown)


def safe_command_for_status(output:PlannerOutputFrame,now_s:float,maximum_command_age_s:float=.2)->tuple[float,float,str]:
    motion_allowed_status={"SUCCESS","SEMANTIC_DEGRADED_TO_GEOMETRY","EXPLICIT_FAILURE_GEOMETRY_FALLBACK"}
    stale=now_s-output.timestamp_s>maximum_command_age_s; finite=np.isfinite([output.linear_velocity_mps,output.angular_velocity_radps]).all()
    if not output.valid or stale or not finite or output.planner_status not in motion_allowed_status: return 0.,0.,"ZERO_VELOCITY_FALLBACK"
    return float(output.linear_velocity_mps),float(output.angular_velocity_radps),"COMMAND_ACCEPTED"
