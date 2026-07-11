#!/usr/bin/env python3
"""Gate and run the bounded stage-04 LiDAR-only smoke training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import yaml

from sgcf_nrmp.data.datasets.geometry_dataset import GeometryClearanceDataset
from sgcf_nrmp.models.field import LidarClearanceField
from sgcf_nrmp.training.checkpoint import load_checkpoint
from sgcf_nrmp.training.lidar_clearance_trainer import fit, overfit_subset, set_deterministic_seed
from sgcf_nrmp.training.losses import ClearanceLoss


def load_config(model_path: Path, training_path: Path) -> dict:
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))["model"]
    training = yaml.safe_load(training_path.read_text(encoding="utf-8"))
    return {"model": model, **training}


def make_loss(config: dict) -> ClearanceLoss:
    training = config["training"]
    return ClearanceLoss(
        float(config["model"]["clearance_clip_m"]), list(training["category_weights"]),
        float(training["distance_loss_weight"]), float(training["collision_loss_weight"]),
    )


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--model-config",default="sgcf_nrmp_project/core/configs/model/lidar_clearance_field.yaml")
    parser.add_argument("--train-config",default="sgcf_nrmp_project/core/configs/train/lidar_clearance_smoke.yaml")
    parser.add_argument("--output",default="sgcf_nrmp_project/artifacts/stages/stage_04_lidar_clearance_field")
    args=parser.parse_args(); output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    config=load_config(Path(args.model_config),Path(args.train_config)); device=torch.device(config["device"])
    Path(output/"training_config.yaml").write_text(yaml.safe_dump(config,sort_keys=False),encoding="utf-8")
    dataset_root=Path(config["dataset"]); train=GeometryClearanceDataset(dataset_root,"train"); validation=GeometryClearanceDataset(dataset_root,"validation")

    seed=int(config["training"]["seed"]); set_deterministic_seed(seed)
    gate_model=LidarClearanceField(config["model"]).to(device); loss_fn=make_loss(config)
    sample=train[0]; query=sample["query_pose"].unsqueeze(0).to(device).requires_grad_(True)
    gate_output=gate_model(sample["points_xy"].unsqueeze(0).to(device),sample["ranges"].unsqueeze(0).to(device),sample["point_valid_mask"].unsqueeze(0).to(device),query)
    gate_gradient=torch.autograd.grad(gate_output.observable_clearance.sum(),query)[0]
    if not torch.isfinite(gate_output.observable_clearance).all() or float(torch.linalg.norm(gate_gradient).detach())==0.0:
        raise RuntimeError("single-batch differentiability gate failed")
    overfit=overfit_subset(gate_model,train,loss_fn,config["overfit"],device)
    if overfit["loss_ratio"] > float(config["overfit"]["required_loss_ratio"]):
        raise RuntimeError(f"overfit gate failed: {overfit}")
    (output/"overfit_gate.json").write_text(json.dumps(overfit,indent=2)+"\n",encoding="utf-8")

    set_deterministic_seed(seed); model=LidarClearanceField(config["model"]).to(device)
    history=fit(model,train,validation,make_loss(config),config,device,output)
    optimizer=torch.optim.AdamW(model.parameters()); state=load_checkpoint(output/"best_model.pt",model,optimizer)
    metadata={"best_epoch":state["epoch"],"best_validation_loss":state["metadata"]["validation_loss"],"parameter_count":sum(p.numel() for p in model.parameters()),"device":str(device),"torch_version":torch.__version__,"overfit_gate":overfit,"epochs_ran":len(history)}
    (output/"best_checkpoint_metadata.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    lines=[str(model),f"parameters: {metadata['parameter_count']}",f"device: {device}",f"torch: {torch.__version__}"]
    (output/"model_summary.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(metadata,indent=2))


if __name__=="__main__": main()
