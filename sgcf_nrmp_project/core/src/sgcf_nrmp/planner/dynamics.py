"""Differential-drive rollout and first-order discrete linearization."""

from __future__ import annotations

import numpy as np


def step(state: np.ndarray, control: np.ndarray, dt: float) -> np.ndarray:
    x,y,theta=state; v,omega=control
    return np.asarray([x+dt*v*np.cos(theta),y+dt*v*np.sin(theta),theta+dt*omega],dtype=float)


def rollout(initial_state: np.ndarray, controls: np.ndarray, dt: float) -> np.ndarray:
    states=np.empty((len(controls)+1,3),dtype=float); states[0]=initial_state
    for index,control in enumerate(controls): states[index+1]=step(states[index],control,dt)
    return states


def linearize(state_nominal: np.ndarray, control_nominal: np.ndarray, dt: float) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    theta=float(state_nominal[2]); v=float(control_nominal[0])
    A=np.eye(3); A[0,2]=-dt*v*np.sin(theta); A[1,2]=dt*v*np.cos(theta)
    B=np.asarray([[dt*np.cos(theta),0.],[dt*np.sin(theta),0.],[0.,dt]])
    nonlinear=step(state_nominal,control_nominal,dt); c=nonlinear-A@state_nominal-B@control_nominal
    return A,B,c
