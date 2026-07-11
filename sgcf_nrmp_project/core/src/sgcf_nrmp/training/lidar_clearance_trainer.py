"""Deterministic CPU/GPU smoke trainer with early stopping."""

from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from sgcf_nrmp.training.checkpoint import save_checkpoint
from sgcf_nrmp.training.metrics import AverageMeter


def set_deterministic_seed(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def _inputs(batch: dict[str, torch.Tensor], device: torch.device) -> tuple[torch.Tensor, ...]:
    return tuple(batch[key].to(device) for key in ("points_xy", "ranges", "point_valid_mask", "query_pose"))


def train_epoch(model, loader, loss_fn, optimizer, device, gradient_clip_norm: float) -> dict[str, float]:
    model.train(); meters={key:AverageMeter() for key in ("total","distance","collision")}
    for batch in loader:
        optimizer.zero_grad(set_to_none=True)
        output=model(*_inputs(batch,device))
        losses=loss_fn(output,batch["observable_clearance"].to(device),batch["observable_collision"].to(device),batch["query_category"].to(device))
        losses["total"].backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),gradient_clip_norm); optimizer.step()
        count=batch["points_xy"].shape[0]
        for key,meter in meters.items(): meter.update(float(losses[key].detach()),count)
    return {key:meter.average for key,meter in meters.items()}


@torch.no_grad()
def validate_epoch(model, loader, loss_fn, device) -> dict[str, float]:
    model.eval(); meters={key:AverageMeter() for key in ("total","distance","collision")}
    for batch in loader:
        output=model(*_inputs(batch,device)); losses=loss_fn(output,batch["observable_clearance"].to(device),batch["observable_collision"].to(device),batch["query_category"].to(device)); count=batch["points_xy"].shape[0]
        for key,meter in meters.items(): meter.update(float(losses[key]),count)
    return {key:meter.average for key,meter in meters.items()}


def overfit_subset(model, dataset, loss_fn, training_config: dict, device: torch.device) -> dict[str, float]:
    count=min(int(training_config["sample_count"]),len(dataset)); subset=Subset(dataset,list(range(count)))
    loader=DataLoader(subset,batch_size=count,shuffle=False); optimizer=torch.optim.Adam(model.parameters(),lr=0.003)
    batch=next(iter(loader)); initial=None; final=None
    for _ in range(int(training_config["steps"])):
        optimizer.zero_grad(set_to_none=True); output=model(*_inputs(batch,device)); losses=loss_fn(output,batch["observable_clearance"].to(device),batch["observable_collision"].to(device),batch["query_category"].to(device)); losses["total"].backward(); optimizer.step()
        if initial is None: initial=float(losses["total"].detach())
        final=float(losses["total"].detach())
    assert initial is not None and final is not None
    return {"initial_loss":initial,"final_loss":final,"loss_ratio":final/initial}


def fit(model, train_dataset, validation_dataset, loss_fn, config: dict, device: torch.device, output_dir: Path) -> list[dict[str,float]]:
    training=config["training"]; generator=torch.Generator().manual_seed(int(training["seed"]))
    train_loader=DataLoader(train_dataset,batch_size=int(training["batch_size"]),shuffle=True,generator=generator,num_workers=0)
    validation_loader=DataLoader(validation_dataset,batch_size=int(training["batch_size"]),shuffle=False,num_workers=0)
    optimizer=torch.optim.AdamW(model.parameters(),lr=float(training["learning_rate"]),weight_decay=float(training["weight_decay"]))
    history=[]; best=float("inf"); stale=0; checkpoint=output_dir/"best_model.pt"
    for epoch in range(1,int(training["max_epochs"])+1):
        train=train_epoch(model,train_loader,loss_fn,optimizer,device,float(training["gradient_clip_norm"])); validation=validate_epoch(model,validation_loader,loss_fn,device)
        row={"epoch":epoch,**{f"train_{k}":v for k,v in train.items()},**{f"validation_{k}":v for k,v in validation.items()}}; history.append(row)
        if validation["total"] < best:
            best=validation["total"]; stale=0; save_checkpoint(checkpoint,model,optimizer,epoch,{"validation_loss":best,"config":config})
        else:
            stale+=1
            if stale>=int(training["early_stopping_patience"]): break
    with (output_dir/"training_history.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(history[0])); writer.writeheader(); writer.writerows(history)
    return history
