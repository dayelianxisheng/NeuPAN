"""Reference construction from a polyline path."""

import numpy as np


def polyline_path(waypoints: list[tuple[float,float]],spacing: float=.08) -> np.ndarray:
    points=[]
    for start,end in zip(waypoints[:-1],waypoints[1:]):
        a,b=np.asarray(start,float),np.asarray(end,float); distance=np.linalg.norm(b-a); count=max(2,int(np.ceil(distance/spacing))+1)
        segment=np.linspace(a,b,count)
        if points: segment=segment[1:]
        points.extend(segment)
    xy=np.asarray(points); delta=np.diff(xy,axis=0,append=xy[-1:]); yaw=np.arctan2(delta[:,1],delta[:,0]);
    if len(yaw)>1: yaw[-1]=yaw[-2]
    return np.column_stack((xy,yaw))


def local_reference(state: np.ndarray,path: np.ndarray,horizon: int,step_distance: float) -> np.ndarray:
    distances=np.linalg.norm(path[:,:2]-state[:2],axis=1); index=int(np.argmin(distances)); reference=[]; accumulated=0.; cursor=index
    for _ in range(horizon+1):
        reference.append(path[cursor])
        target=accumulated+step_distance
        while cursor<len(path)-1 and accumulated<target:
            accumulated+=float(np.linalg.norm(path[cursor+1,:2]-path[cursor,:2])); cursor+=1
    return np.asarray(reference)
