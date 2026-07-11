"""Finite-difference versus autograd vector visualization."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def plot_gradient_comparison(query_pose: np.ndarray,target: np.ndarray,prediction: np.ndarray,valid: np.ndarray,output: Path) -> None:
    valid=valid.astype(bool); selected=np.flatnonzero(valid)[:160]; invalid=np.flatnonzero(~valid)
    fig,axes=plt.subplots(1,2,figsize=(13,5.5),constrained_layout=True)
    for ax,gradient,title in ((axes[0],target,'GT finite-difference gradient'),(axes[1],prediction,'Model autograd gradient')):
        ax.quiver(query_pose[selected,0],query_pose[selected,1],gradient[selected,0],gradient[selected,1],angles='xy',scale_units='xy',scale=1.8,width=.004)
        if len(invalid): ax.scatter(query_pose[invalid,0],query_pose[invalid,1],c='red',marker='x',label='gradient invalid')
        ax.set(title=title,xlabel='query x [m]',ylabel='query y [m]',xlim=(-6,6),ylim=(-6,6)); ax.set_aspect('equal'); ax.legend(loc='upper right')
    fig.savefig(output/'gradient_comparison.png',dpi=150); plt.close(fig)
