"""Angle wrapping and reference unwrapping."""

import numpy as np


def wrap_angle(angle):
    return (np.asarray(angle) + np.pi) % (2 * np.pi) - np.pi


def unwrap_reference(reference: np.ndarray, nominal: np.ndarray) -> np.ndarray:
    result=np.array(reference,dtype=float,copy=True)
    result[:,2]=nominal[:,2]+wrap_angle(result[:,2]-nominal[:,2])
    return result
