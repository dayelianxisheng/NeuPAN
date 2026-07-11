#!/usr/bin/env python3
"""Generate all required stage-04 model, field, gradient and risk plots."""

from __future__ import annotations

import csv,json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import torch,yaml
from matplotlib.patches import Polygon as PolygonPatch

matplotlib.use('Agg')

from sgcf_nrmp.data.procedural.dataset_generator import make_scene
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.models.field import LidarClearanceField
from sgcf_nrmp.training.checkpoint import load_checkpoint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig
from sgcf_nrmp.visualization.field_prediction_plot import plot_heatmap_comparison,plot_prediction_summary
from sgcf_nrmp.visualization.gradient_comparison_plot import plot_gradient_comparison


def main():
    output=Path('sgcf_nrmp_project/artifacts/stages/stage_04_lidar_clearance_field'); arrays=dict(np.load(output/'test_predictions.npz')); prediction=arrays['prediction'].reshape(-1); observable=arrays['observable'].reshape(-1)
    rows=list(csv.DictReader((output/'training_history.csv').open())); epochs=np.asarray([int(row['epoch']) for row in rows]); train=np.asarray([float(row['train_total']) for row in rows]); validation=np.asarray([float(row['validation_total']) for row in rows]); fig,ax=plt.subplots(figsize=(7,4)); ax.plot(epochs,train,label='train'); ax.plot(epochs,validation,label='validation'); ax.set(xlabel='epoch',ylabel='loss',title='Smoke training history'); ax.legend(); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(output/'loss_curve.png',dpi=150); plt.close(fig)
    plot_prediction_summary(observable,prediction,output); plot_gradient_comparison(arrays['query_pose'],arrays['gradient_target'],arrays['gradient_prediction'],arrays['gradient_valid'].reshape(-1),output)

    # False-safe cases: model errors first, then partial-observation world risks.
    report=json.loads((output/'false_safe_report.json').read_text()); indices=(report['model_false_safe_indices']+report['world_risk_partial_observation_indices'])[:8]; indices=list(dict.fromkeys(indices))
    if not indices: indices=[int(np.argmax(prediction-observable))]
    fig,axes=plt.subplots(2,4,figsize=(14,7)); footprint_local=np.asarray([[-.4,-.25],[.4,-.25],[.4,.25],[-.4,.25]])
    for ax in axes.flat: ax.axis('off')
    for ax,index in zip(axes.flat,indices):
        mask=arrays['point_valid_mask'][index]; points=arrays['points_xy'][index][mask]; query=arrays['query_pose'][index]; yaw=np.arctan2(query[2],query[3]); c,s=np.cos(yaw),np.sin(yaw); polygon=footprint_local@np.asarray([[c,-s],[s,c]]).T+query[:2]; ax.axis('on'); ax.scatter(points[:,0],points[:,1],s=5,c='black'); ax.add_patch(PolygonPatch(polygon,facecolor='tab:blue',alpha=.4)); hidden=bool(arrays['world_collision'][index] and observable[index]>=.6); ax.set(xlim=(-6,6),ylim=(-6,6),aspect='equal'); ax.set_title(f"GT={observable[index]:.2f} pred={prediction[index]:.2f}\nworld={arrays['world'][index].item():.2f} hidden={hidden}",fontsize=8)
    fig.suptitle('Most severe model false-safe and hidden-world-risk cases'); fig.tight_layout(); fig.savefig(output/'false_safe_cases.png',dpi=150); plt.close(fig)

    # Continuous field for the first test scene at yaw=0.
    data_config=yaml.safe_load(Path('sgcf_nrmp_project/artifacts/datasets/geometry_v1/config_snapshot.yaml').read_text()); training=yaml.safe_load((output/'training_config.yaml').read_text()); model=LidarClearanceField(training['model']); load_checkpoint(output/'best_model.pt',model); model.eval(); scene_id=int(arrays['scene_id'][0].item()); seed=int(arrays['seed'][0].item()); rng=np.random.default_rng(seed); scene=make_scene(scene_id,data_config,rng); scan=scene.scan(Pose2D(0,0,0),LidarConfig(**data_config['lidar']),rng); footprint=rectangular_footprint(data_config['footprint']['length'],data_config['footprint']['width']); x=np.linspace(-6,6,35); y=np.linspace(-6,6,35); poses=[Pose2D(float(xx),float(yy),0.) for yy in y for xx in x]; queries=torch.tensor([[p.x,p.y,0.,1.] for p in poses]); count=len(poses); base_points=torch.from_numpy(arrays['points_xy'][0]).repeat(count,1,1); base_ranges=torch.from_numpy(np.linalg.norm(arrays['points_xy'][0],axis=1).astype(np.float32)).repeat(count,1); base_mask=torch.from_numpy(arrays['point_valid_mask'][0]).repeat(count,1)
    with torch.no_grad(): model_grid=model(base_points,base_ranges,base_mask,queries).observable_clearance.numpy().reshape(len(y),len(x))
    labels=[scene.label(footprint,pose,scan,float(data_config['labels']['observable_truncation'])) for pose in poses]; obs=np.asarray([label.observable_clearance for label in labels]).reshape(len(y),len(x)); world=np.asarray([label.world_clearance for label in labels]).reshape(len(y),len(x)); plot_heatmap_comparison(x,y,obs,model_grid,world,output)

    benchmark=json.loads((output/'oracle_benchmark.json').read_text()); sizes=np.asarray([int(key) for key in benchmark['batches']]); model_ms=np.asarray([benchmark['batches'][str(size)]['model_forward']['mean_ms'] for size in sizes]); oracle_ms=np.asarray([benchmark['batches'][str(size)]['exact_geometry']['mean_ms'] for size in sizes]); fig,ax=plt.subplots(figsize=(7,4)); ax.plot(sizes,model_ms,'o-',label='model batch forward'); ax.plot(sizes,oracle_ms,'o-',label='exact geometry'); ax.set(xlabel='query batch size',ylabel='latency [ms]',title='Oracle versus neural proxy on CPU'); ax.legend(); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(output/'oracle_vs_model_latency.png',dpi=150); plt.close(fig)


if __name__=='__main__': main()
