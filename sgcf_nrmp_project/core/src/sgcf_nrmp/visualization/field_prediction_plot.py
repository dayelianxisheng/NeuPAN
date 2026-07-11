"""Reusable distance prediction plots."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def plot_prediction_summary(observable: np.ndarray, prediction: np.ndarray, output: Path) -> None:
    error=np.abs(prediction-observable)
    fig,ax=plt.subplots(figsize=(6,5)); ax.scatter(observable,prediction,s=8,alpha=.35); limit=max(observable.max(),prediction.max()); ax.plot([0,limit],[0,limit],'k--'); ax.set(xlabel='observable GT [m]',ylabel='model prediction [m]',title='Clearance prediction'); fig.tight_layout(); fig.savefig(output/'clearance_prediction_scatter.png',dpi=150); plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,4)); ax.hist(error,bins=40); ax.set(xlabel='absolute error [m]',ylabel='samples',title='Test clearance error'); fig.tight_layout(); fig.savefig(output/'clearance_error_distribution.png',dpi=150); plt.close(fig)
    order=np.argsort(observable); fig,ax=plt.subplots(figsize=(8,4)); ax.plot(observable[order],error[order],'.',ms=3,alpha=.5); ax.axvline(.6,color='r',ls='--',label='d_safe'); ax.set(xlabel='observable GT [m]',ylabel='absolute error [m]',title='Boundary-aware error'); ax.legend(); fig.tight_layout(); fig.savefig(output/'boundary_error_plot.png',dpi=150); plt.close(fig)


def plot_heatmap_comparison(x: np.ndarray,y: np.ndarray,observable: np.ndarray,prediction: np.ndarray,world: np.ndarray,output: Path) -> None:
    extent=[x.min(),x.max(),y.min(),y.max()]; panels=[(observable,'observable GT'),(prediction,'model prediction'),(np.abs(prediction-observable),'absolute error'),(world,'world clearance (reference only)')]
    fig,axes=plt.subplots(1,4,figsize=(19,4.5),constrained_layout=True)
    for ax,(values,title) in zip(axes,panels): image=ax.imshow(values,origin='lower',extent=extent,cmap='viridis'); ax.set(title=title,xlabel='x [m]',ylabel='y [m]'); fig.colorbar(image,ax=ax,shrink=.8)
    fig.savefig(output/'field_heatmap_comparison.png',dpi=150); plt.close(fig)
