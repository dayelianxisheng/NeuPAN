#!/usr/bin/env python3
"""Evaluate test distance, collision, false-safe and autograd gradients."""

from __future__ import annotations

import argparse, json
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader

from sgcf_nrmp.data.datasets.geometry_dataset import GeometryClearanceDataset
from sgcf_nrmp.evaluation.clearance_metrics import clearance_metrics
from sgcf_nrmp.evaluation.gradient_metrics import gradient_metrics
from sgcf_nrmp.models.field import LidarClearanceField
from sgcf_nrmp.models.lidar.query_transform import query_gradient_to_xyyaw
from sgcf_nrmp.training.checkpoint import load_checkpoint


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--output",default="sgcf_nrmp_project/artifacts/stages/stage_04_lidar_clearance_field"); args=parser.parse_args(); output=Path(args.output)
    config=yaml.safe_load((output/"training_config.yaml").read_text()); evaluation=yaml.safe_load(Path("sgcf_nrmp_project/core/configs/eval/lidar_clearance.yaml").read_text())
    dataset=GeometryClearanceDataset(config["dataset"],"test"); loader=DataLoader(dataset,batch_size=evaluation["batch_size"],shuffle=False)
    model=LidarClearanceField(config["model"]); load_checkpoint(output/"best_model.pt",model); model.eval()
    collected={key:[] for key in ("prediction","collision_logit","observable","observable_collision","world_collision","world","gradient_prediction","gradient_target","gradient_valid","linearity","points_xy","point_valid_mask","query_pose","scene_id","seed")}
    for batch in loader:
        query=batch["query_pose"].clone().requires_grad_(True); result=model(batch["points_xy"],batch["ranges"],batch["point_valid_mask"],query); raw_gradient=torch.autograd.grad(result.observable_clearance.sum(),query,create_graph=False)[0]; physical=query_gradient_to_xyyaw(raw_gradient,query)
        delta=torch.tensor([0.01,-0.008,0.,0.],dtype=query.dtype).repeat(len(query),1); yaw_delta=.006; yaw=torch.atan2(query[:,2],query[:,3])+yaw_delta; perturbed=query.detach()+delta; perturbed[:,2]=torch.sin(yaw.detach()); perturbed[:,3]=torch.cos(yaw.detach())
        with torch.no_grad(): shifted=model(batch["points_xy"],batch["ranges"],batch["point_valid_mask"],perturbed).observable_clearance
        physical_delta=torch.tensor([.01,-.008,yaw_delta]); linear=result.observable_clearance.detach().reshape(-1)+(physical.detach()*physical_delta).sum(dim=1); linearity=torch.abs(shifted.reshape(-1)-linear)
        for key,value in (("prediction",result.observable_clearance),("observable",batch["observable_clearance"]),("observable_collision",batch["observable_collision"]),("world_collision",batch["world_collision"]),("world",batch["world_clearance"]),("gradient_prediction",physical),("gradient_target",batch["observable_gradient"]),("gradient_valid",batch["observable_gradient_valid"]),("linearity",linearity)):
            collected[key].append(value.detach().cpu().numpy())
        collected["collision_logit"].append(result.observable_collision_logit.detach().cpu().numpy())
        for key in ("points_xy","point_valid_mask","query_pose","scene_id","seed"):
            collected[key].append(batch[key].cpu().numpy())
    arrays={key:np.concatenate(value) for key,value in collected.items()}
    metrics,false_safe=clearance_metrics(arrays["prediction"],arrays["observable"],arrays["observable_collision"],arrays["world_collision"],float(evaluation["d_safe"]),float(evaluation["near_boundary_max_m"]),arrays["collision_logit"])
    gradients=gradient_metrics(arrays["gradient_prediction"],arrays["gradient_target"],arrays["gradient_valid"].reshape(-1).astype(bool),arrays["linearity"])
    (output/"test_metrics.json").write_text(json.dumps(metrics,indent=2)+"\n"); (output/"gradient_metrics.json").write_text(json.dumps(gradients,indent=2)+"\n"); (output/"false_safe_report.json").write_text(json.dumps(false_safe,indent=2)+"\n")
    np.savez_compressed(output/"test_predictions.npz",**arrays)
    print(json.dumps({"metrics":metrics,"gradient":gradients,"false_safe":{k:v for k,v in false_safe.items() if not k.endswith("indices")}},indent=2))


if __name__=="__main__": main()
