"""Exact observable Oracle queries and complete-world evaluation checks."""

from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarScan


class ExactGeometryChecker:
    def __init__(self,scene:ProceduralScene,scan:LidarScan,footprint:Polygon,truncation:float,spatial_step:float=.02,angular_step:float=.02):
        self.scene,self.scan,self.footprint,self.truncation=scene,scan,footprint,truncation; self.spatial_step,self.angular_step=spatial_step,angular_step

    def linearization(self,states:np.ndarray)->tuple[np.ndarray,np.ndarray,np.ndarray]:
        distances=[]; gradients=[]; valid=[]
        for state in states:
            pose=Pose2D(*map(float,state)); label=self.scene.label(self.footprint,pose,self.scan,self.truncation); gradient=self.scene.gradient(self.footprint,pose,self.scan,self.truncation,"observable_clearance",self.spatial_step,self.angular_step)
            distances.append(label.observable_clearance); gradients.append(gradient.as_array()); valid.append(gradient.gradient_valid and label.observable_available)
        return np.asarray(distances),np.asarray(gradients),np.asarray(valid,dtype=bool)

    def recheck(self,states:np.ndarray,d_safe:float)->dict[str,object]:
        observable=[]; world=[]; world_collision=[]
        for state in states:
            label=self.scene.label(self.footprint,Pose2D(*map(float,state)),self.scan,self.truncation); observable.append(label.observable_clearance); world.append(label.world_clearance); world_collision.append(label.world_collision)
        observable=np.asarray(observable); world=np.asarray(world); world_collision=np.asarray(world_collision)
        return {"observable":observable,"world":world,"min_observable":float(observable.min()),"min_world":float(world.min()),"violated_points":int(np.sum(observable<d_safe-1e-4)),"partial_observation_world_risk":bool(np.any(world_collision & (observable>=d_safe)))}
