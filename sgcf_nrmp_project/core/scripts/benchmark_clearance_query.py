#!/usr/bin/env python3
"""Compare batched neural queries with exact geometry and finite differences."""

from __future__ import annotations

import json, time
from pathlib import Path

import numpy as np
import torch
import yaml

from sgcf_nrmp.data.datasets.geometry_dataset import GeometryClearanceDataset
from sgcf_nrmp.data.procedural.dataset_generator import make_scene
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.models.field import LidarClearanceField
from sgcf_nrmp.training.checkpoint import load_checkpoint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig
from sgcf_nrmp.evaluation.oracle_benchmark import latency_summary


def main():
    output=Path("sgcf_nrmp_project/artifacts/stages/stage_04_lidar_clearance_field"); config=yaml.safe_load((output/"training_config.yaml").read_text()); eval_config=yaml.safe_load(Path("sgcf_nrmp_project/core/configs/eval/lidar_clearance.yaml").read_text()); data_config=yaml.safe_load(Path("sgcf_nrmp_project/artifacts/datasets/geometry_v1/config_snapshot.yaml").read_text())
    dataset=GeometryClearanceDataset(config["dataset"],"test"); model=LidarClearanceField(config["model"]); load_checkpoint(output/"best_model.pt",model); model.eval(); footprint=rectangular_footprint(data_config["footprint"]["length"],data_config["footprint"]["width"]); lidar=LidarConfig(**data_config["lidar"]); trunc=float(data_config["labels"]["observable_truncation"])
    cache={}
    def oracle_sample(sample):
        scene_id=int(sample["scene_id"].item()); seed=int(sample["seed"].item())
        if scene_id not in cache:
            rng=np.random.default_rng(seed); scene=make_scene(scene_id,data_config,rng); scan=scene.scan(Pose2D(0,0,0),lidar,rng); cache[scene_id]=(scene,scan)
        scene,scan=cache[scene_id]; q=sample["query_pose"].numpy(); pose=Pose2D(float(q[0]),float(q[1]),float(np.arctan2(q[2],q[3]))); return scene.label(footprint,pose,scan,trunc).observable_clearance,scene,scan,pose
    report={"device":"cpu","notes":["Exact geometry is a Python/Shapely oracle.","Small batches may favor exact geometry; neural batching is the intended comparison.","Autograd and finite differences add gradient cost."],"batches":{}}
    for batch_size in (1,10,32,128):
        samples=[dataset[i] for i in range(batch_size)]; points=torch.stack([s["points_xy"] for s in samples]); ranges=torch.stack([s["ranges"] for s in samples]); masks=torch.stack([s["point_valid_mask"] for s in samples]); queries=torch.stack([s["query_pose"] for s in samples])
        with torch.no_grad(): model(points,ranges,masks,queries)
        model_times=[]; oracle_times=[]; autograd_times=[]
        repeats=int(eval_config["benchmark_repeats"])
        for _ in range(repeats):
            start=time.perf_counter();
            with torch.no_grad(): model(points,ranges,masks,queries)
            model_times.append((time.perf_counter()-start)*1000)
            start=time.perf_counter(); [oracle_sample(sample)[0] for sample in samples]; oracle_times.append((time.perf_counter()-start)*1000)
            query_grad=queries.clone().requires_grad_(True); start=time.perf_counter(); prediction=model(points,ranges,masks,query_grad).observable_clearance; torch.autograd.grad(prediction.sum(),query_grad); autograd_times.append((time.perf_counter()-start)*1000)
        # Exact finite differences are expensive; time three repetitions.
        finite_times=[]
        for _ in range(3):
            start=time.perf_counter()
            for sample in samples:
                _,scene,scan,pose=oracle_sample(sample); scene.gradient(footprint,pose,scan,trunc,"observable_clearance",.04,.04)
            finite_times.append((time.perf_counter()-start)*1000)
        report["batches"][str(batch_size)]={"meaning":"full_horizon" if batch_size==10 else "query_batch","model_forward":latency_summary(model_times,batch_size),"model_forward_autograd":latency_summary(autograd_times,batch_size),"exact_geometry":latency_summary(oracle_times,batch_size),"exact_geometry_finite_difference":latency_summary(finite_times,batch_size)}
    (output/"oracle_benchmark.json").write_text(json.dumps(report,indent=2)+"\n"); print(json.dumps(report,indent=2))


if __name__=="__main__": main()
