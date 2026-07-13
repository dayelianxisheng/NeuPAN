#!/usr/bin/env python3
"""Run the single fixed epoch-146--195 Stage 10J low-LR continuation."""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.evaluation.semantic_perception_evaluator import CLASS_NAMES
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.class_weight_audit import build_audited_cross_entropy
from sgcf_nrmp.training.lifecycle import (
    atomic_torch_save,
    evaluate_split,
    feasible_checkpoint_key,
    validation_hard_feasibility,
)
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = ROOT / "core/configs/train/stage_10j_low_lr_stabilization.yaml"
SOURCE_PATH = OUT / "stage10i_validation_diagnostic_checkpoint.pt"
FEASIBLE_PATH = OUT / "stage10j_validation_feasible_checkpoint.pt"
BEST_HUMAN_PATH = OUT / "stage10j_best_human_recall_checkpoint.pt"
BEST_MIOU_PATH = OUT / "stage10j_best_miou_checkpoint.pt"
HUMAN = 2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tensors(dataset):
    return (
        torch.stack([dataset[index]["image"] for index in range(len(dataset))]),
        torch.stack([dataset[index]["target"] for index in range(len(dataset))]),
    )


def hash_value(hasher, value) -> None:
    if torch.is_tensor(value):
        array = value.detach().cpu().contiguous().numpy()
        hasher.update(str(array.dtype).encode()); hasher.update(str(array.shape).encode()); hasher.update(array.tobytes())
    elif isinstance(value, dict):
        for key in sorted(value, key=str): hasher.update(str(key).encode()); hash_value(hasher, value[key])
    elif isinstance(value, (list, tuple)):
        for item in value: hash_value(hasher, item)
    else: hasher.update(repr(value).encode())


def object_hash(value) -> str:
    hasher = hashlib.sha256(); hash_value(hasher, value); return hasher.hexdigest()


def optimizer_hashes(state_dict: dict) -> dict:
    groups_without_lr = [{key: value for key, value in group.items() if key != "lr"} for group in state_dict["param_groups"]]
    moment_norm_sq = 0.0
    for state in state_dict["state"].values():
        for key, value in state.items():
            if key in ("exp_avg", "exp_avg_sq", "max_exp_avg_sq") and torch.is_tensor(value): moment_norm_sq += float(value.norm()) ** 2
    return {
        "full_optimizer_state_hash": object_hash(state_dict),
        "moment_state_hash": object_hash(state_dict["state"]),
        "non_lr_parameter_groups_hash": object_hash(groups_without_lr),
        "optimizer_moment_norm": math.sqrt(moment_norm_sq),
    }


def model_schema_hash(model) -> str:
    schema = [(name, tuple(value.shape), str(value.dtype)) for name, value in model.state_dict().items()]
    return object_hash(schema)


def metric_view(metrics):
    return {key: metrics[key] for key in (
        "pixel_accuracy", "mean_iou", "macro_f1", "per_class_iou",
        "per_class_precision", "per_class_recall", "prediction_class_fraction", "confusion_matrix",
    )}


def human_errors(metrics):
    matrix = np.asarray(metrics["confusion_matrix"], int); support = max(int(matrix[HUMAN].sum()), 1)
    return {f"HUMAN_to_{CLASS_NAMES[class_id]}": {"count": int(matrix[HUMAN, class_id]), "rate": float(matrix[HUMAN, class_id] / support)} for class_id in (0, 1, 3, 4)}


def make_payload(role, epoch, model, optimizer, metrics, loss, feasibility, config, source, optimizer_hash):
    return {
        "purpose": role,
        "acceptance": (["VALIDATION_SELECTED_CANDIDATE", "NOT_EVALUATED_ON_NEW_UNTOUCHED_AUDIT_SPLIT", "NOT_YET_ACCEPTED_AS_FINAL_STAGE10_MODEL"] if role == "VALIDATION_SELECTED_CANDIDATE" else ["DIAGNOSTIC_ONLY"]),
        "epoch": epoch, "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(),
        "validation_metrics": metrics, "validation_loss": loss, "validation_feasibility": feasibility,
        "class_mapping": dict(zip(CLASS_NAMES, range(5))), "normalization": source["normalization"], "input_resolution_hw": [120, 160],
        "class_weights": config["class_weights"], "dataset_manifest_sha256": source["dataset_manifest_sha256"],
        "training_config_sha256": source["training_config_sha256"], "stage10j_config_sha256": sha256_file(CONFIG_PATH),
        "optimizer_state_hash": optimizer_hash, "learning_rate": config["learning_rate"], "seed": config["seed"],
        "prediction_strategy": "U0_argmax_always",
    }


def save_and_verify(path, payload, model, sentinel, lifecycle, role):
    atomic_torch_save(payload, path)
    restored_payload = torch.load(path, map_location="cpu", weights_only=True)
    restored = TinySemanticSegmentation(); restored.load_state_dict(restored_payload["model_state_dict"]); restored.eval(); model.eval()
    with torch.no_grad(): difference = float((model(sentinel) - restored(sentinel)).abs().max())
    if difference > 1e-7: raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: checkpoint reload mismatch")
    lifecycle.append({"epoch": payload["epoch"], "role": role, "path": path.name, "atomic_save": True, "fsync_and_rename": True, "reload_max_abs_difference": difference, "sentinel_logits_compared": True})
    return difference


def pareto_front(history):
    fields = lambda item: np.array([
        item["validation"]["mean_iou"], item["validation"]["macro_f1"],
        item["validation"]["per_class_recall"]["HUMAN"], item["validation"]["per_class_iou"]["HUMAN"],
        item["validation"]["per_class_recall"]["VEHICLE"], item["validation"]["per_class_recall"]["ROBOT"],
    ])
    vectors = [fields(item) for item in history]; front = []
    for index, vector in enumerate(vectors):
        dominated = any(np.all(other >= vector) and np.any(other > vector) for other_index, other in enumerate(vectors) if other_index != index)
        if not dominated: front.append(history[index]["epoch"])
    return front


def summary_record(record):
    metrics = record["validation"]
    return {"epoch": record["epoch"], "validation_loss": metrics["loss"], "mean_iou": metrics["mean_iou"], "macro_f1": metrics["macro_f1"], "human_iou": metrics["per_class_iou"]["HUMAN"], "human_recall": metrics["per_class_recall"]["HUMAN"], "vehicle_recall": metrics["per_class_recall"]["VEHICLE"], "robot_recall": metrics["per_class_recall"]["ROBOT"], "human_errors": record["human_errors"], "feasible": record["feasibility"]["passed"]}


def stage10i_record(epoch):
    history = json.loads((OUT / "stage10i_continuation_history.json").read_text())
    record = next(item for item in history if item["epoch"] == epoch)
    metrics = record["validation"]
    return {"epoch": epoch, "mean_iou": metrics["mean_iou"], "macro_f1": metrics["macro_f1"], "human_iou": metrics["per_class_iou"]["HUMAN"], "human_recall": metrics["per_class_recall"]["HUMAN"], "vehicle_recall": metrics["per_class_recall"]["VEHICLE"], "robot_recall": metrics["per_class_recall"]["ROBOT"], "human_errors": {"status": "NOT_AVAILABLE_CHECKPOINT_NOT_RETAINED" if epoch == 126 else "available_in_stage10i_checkpoint"}}


def plots(history, comparison):
    epochs = [item["epoch"] for item in history]
    for filename, extractor, ylabel in (
        ("stage10j_train_validation_loss.png", lambda x, split: x[split]["loss"], "loss"),
    ):
        fig, ax = plt.subplots();
        for split in ("train", "validation"): ax.plot(epochs, [extractor(item, split) for item in history], label=split)
        ax.set(xlabel="epoch", ylabel=ylabel); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / filename, dpi=150); plt.close(fig)
    for filename, key, ylabel in (("stage10j_validation_miou.png", "mean_iou", "validation mIoU"), ("stage10j_validation_macro_f1.png", "macro_f1", "validation macro F1")):
        fig, ax = plt.subplots(); ax.plot(epochs, [item["validation"][key] for item in history]); ax.set(xlabel="epoch", ylabel=ylabel); ax.grid(); fig.tight_layout(); fig.savefig(OUT / filename, dpi=150); plt.close(fig)
    fig, ax = plt.subplots();
    for name in CLASS_NAMES[2:]: ax.plot(epochs, [item["validation"]["per_class_recall"][name] for item in history], label=name)
    ax.set(xlabel="epoch", ylabel="validation recall", ylim=(0, 1)); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10j_per_class_recall.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(); ax.plot(epochs, [item["validation"]["per_class_iou"]["HUMAN"] for item in history], label="HUMAN IoU"); ax.plot(epochs, [item["validation"]["per_class_recall"]["HUMAN"] for item in history], label="HUMAN recall"); ax.axhline(.65, color="gray", ls="--"); ax.axhline(.85, color="gray", ls=":"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10j_human_iou_recall.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots();
    for destination in ("UNKNOWN", "STATIC_OBSTACLE", "VEHICLE", "ROBOT"): ax.plot(epochs, [item["human_errors"][f"HUMAN_to_{destination}"]["rate"] for item in history], label=destination)
    ax.set(xlabel="epoch", ylabel="GT HUMAN destination rate"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10j_human_error_destinations.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(); scatter = ax.scatter([item["validation"]["mean_iou"] for item in history], [item["validation"]["per_class_recall"]["HUMAN"] for item in history], c=epochs, cmap="viridis"); ax.set(xlabel="validation mIoU", ylabel="HUMAN recall"); fig.colorbar(scatter, ax=ax, label="epoch"); fig.tight_layout(); fig.savefig(OUT / "stage10j_validation_pareto.png", dpi=150); plt.close(fig)
    window = 5; names=("HUMAN","VEHICLE","ROBOT"); fig, ax = plt.subplots();
    for name in names:
        values=np.array([item["validation"]["per_class_recall"][name] for item in history]); rolling=[float(np.std(values[max(0,index-window+1):index+1])) for index in range(len(values))]; ax.plot(epochs,rolling,label=name)
    ax.set(xlabel="epoch",ylabel="rolling 5-epoch recall std"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10j_metric_stability.png",dpi=150); plt.close(fig)
    labels=list(comparison); x=np.arange(len(labels)); fig,ax=plt.subplots(figsize=(11,5));
    for offset,key in enumerate(("mean_iou","human_recall","vehicle_recall","robot_recall")): ax.bar(x+(offset-1.5)*.18,[comparison[label][key] for label in labels],.18,label=key)
    ax.set_xticks(x,labels,rotation=25,ha="right"); ax.set_ylim(0,1); ax.legend(); fig.tight_layout(); fig.savefig(OUT/"stage10j_stage10i_comparison.png",dpi=150); plt.close(fig)


def main():
    config_text = CONFIG_PATH.read_text(); config = yaml.safe_load(config_text)
    (OUT / "stage10j_training_config.yaml").write_text(config_text)
    manifest_path = OUT / "dataset_manifest.json"; manifest = json.loads(manifest_path.read_text())["records"]
    test_scene_ids = sorted(record["scene_id"] for record in manifest if record["split"] == "test")
    test_freeze = {"test_scene_ids_read_from_manifest_only": test_scene_ids, "test_dataset_instantiated_for_evaluation": False, "test_dataloader_iterated": False, "test_images_loaded": False, "test_labels_loaded": False, "test_inference_executed": False, "test_metrics_recomputed": False, "test_predictions_used_for_selection": False}
    (OUT / "stage10j_test_freeze_audit.json").write_text(json.dumps(test_freeze, indent=2) + "\n")
    new_audit = {"new_audit_split_generated": False, "new_audit_images_read": False, "new_audit_labels_read": False, "new_audit_metrics_computed": False, "reason": "model and validation checkpoint were not frozen before Stage 10J"}
    (OUT / "stage10j_new_audit_non_access.json").write_text(json.dumps(new_audit, indent=2) + "\n")
    source = torch.load(SOURCE_PATH, map_location="cpu", weights_only=True)
    train_path = OUT / "dataset/train.npz"; validation_path = OUT / "dataset/validation.npz"
    train = RGBSemanticDataset(train_path); validation = RGBSemanticDataset(validation_path); train_images, train_targets=tensors(train); val_images,val_targets=tensors(validation)
    seed_all(config["seed"]); model=TinySemanticSegmentation(); current_schema_hash=model_schema_hash(model); model.load_state_dict(source["model_state_dict"])
    stage10h_config=(OUT/"stage10h_training_config.yaml").read_text(); stage10i_config=(OUT/"stage10i_continuation_config.yaml").read_text()
    split_ids={split:{record["scene_id"] for record in manifest if record["split"]==split} for split in ("train","validation","test")}
    input_audit={
        "checkpoint_epoch":source.get("epoch"),"checkpoint_epoch_145":source.get("epoch")==145,"checkpoint_purpose":source.get("purpose"),"optimizer_state_present":bool(source.get("optimizer_state_dict",{}).get("state")),
        "model_state_schema_hash":object_hash([(name,tuple(value.shape),str(value.dtype)) for name,value in source["model_state_dict"].items()]),"current_model_schema_hash":current_schema_hash,
        "model_architecture_hash_match":object_hash([(name,tuple(value.shape),str(value.dtype)) for name,value in source["model_state_dict"].items()])==current_schema_hash,
        "training_config_hash_match":source["training_config_sha256"]==hashlib.sha256(stage10h_config.encode()).hexdigest(),"stage10i_config_hash_match":source["continuation_config_sha256"]==hashlib.sha256(stage10i_config.encode()).hexdigest(),
        "dataset_manifest_hash_match":source["dataset_manifest_sha256"]==sha256_file(manifest_path),"class_weights_match":source["class_weights"]==config["class_weights"],"normalization_match":source["normalization"]=="uint8 RGB to float32 [0,1]",
        "train_hash_match":sha256_file(train_path)=="8ef3981fa4716e17cb89c24089beb36ffefd1090f900042972e406d5a3cf0c27","validation_hash_match":sha256_file(validation_path)=="1877cee042936711c7df5b1c3ed7085364ec10c7bdfc36c2d533a766903bf246",
        "scene_split_disjoint":not(split_ids["train"]&split_ids["validation"] or split_ids["train"]&split_ids["test"] or split_ids["validation"]&split_ids["test"]),"prediction_strategy":"U0_argmax_always","test_accessed":False,"new_audit_accessed":False,
    }
    required_true = (
        "checkpoint_epoch_145", "optimizer_state_present", "model_architecture_hash_match",
        "training_config_hash_match", "stage10i_config_hash_match", "dataset_manifest_hash_match",
        "class_weights_match", "normalization_match", "train_hash_match",
        "validation_hash_match", "scene_split_disjoint",
    )
    positive_checks_passed = all(input_audit[key] for key in required_true)
    non_access_checks_passed = not input_audit["test_accessed"] and not input_audit["new_audit_accessed"]
    input_audit.update({
        "required_positive_checks": list(required_true),
        "positive_checks_passed": positive_checks_passed,
        "non_access_checks_passed": non_access_checks_passed,
        "passed": positive_checks_passed and non_access_checks_passed,
        "superseded_initial_false_positive": {
            "condition": "expected-false non-access flags were incorrectly included in all(bool_values)",
            "optimizer_steps_before_fix": 0,
            "actual_checkpoint_or_metadata_mismatch": False,
        },
    })
    if not input_audit["passed"]: (OUT/"stage10j_checkpoint_input_audit.json").write_text(json.dumps(input_audit,indent=2)+"\n"); raise SystemExit("BLOCKED_CHECKPOINT_STATE")
    _,criterion,_=build_audited_cross_entropy(config["class_weights"]); optimizer=torch.optim.AdamW(model.parameters(),lr=config["old_learning_rate"],weight_decay=config["weight_decay"]); optimizer.load_state_dict(source["optimizer_state_dict"])
    before=optimizer.state_dict(); hashes_before=optimizer_hashes(before); old_lrs=[group["lr"] for group in optimizer.param_groups]
    if old_lrs != [config["old_learning_rate"]]: raise SystemExit("BLOCKED_CHECKPOINT_STATE: source LR mismatch")
    for group in optimizer.param_groups: group["lr"]=config["learning_rate"]
    after=optimizer.state_dict(); hashes_after=optimizer_hashes(after); new_lrs=[group["lr"] for group in optimizer.param_groups]
    optimizer_audit={"optimizer_type":"AdamW","parameter_group_count":len(optimizer.param_groups),"old_learning_rates":old_lrs,"new_learning_rates":new_lrs,"expected_new_learning_rate":config["learning_rate"],"before":hashes_before,"after_lr_change_before_any_step":hashes_after,"moments_unchanged":hashes_before["moment_state_hash"]==hashes_after["moment_state_hash"],"non_lr_parameter_groups_unchanged":hashes_before["non_lr_parameter_groups_hash"]==hashes_after["non_lr_parameter_groups_hash"],"full_state_hash_changed_only_due_to_lr":hashes_before["full_optimizer_state_hash"]!=hashes_after["full_optimizer_state_hash"],"optimizer_reinitialized_after_state_load":False,"single_lr_authorized":new_lrs==[.0002]}
    if not all(optimizer_audit[key] for key in ("moments_unchanged","non_lr_parameter_groups_unchanged","full_state_hash_changed_only_due_to_lr","single_lr_authorized")): raise SystemExit("BLOCKED_CHECKPOINT_STATE: optimizer state audit failed")
    (OUT/"stage10j_checkpoint_input_audit.json").write_text(json.dumps(input_audit,indent=2)+"\n"); (OUT/"stage10j_optimizer_state_audit.json").write_text(json.dumps(optimizer_audit,indent=2)+"\n")
    # Reproduce source validation before any step.
    source_loss,source_metric,_=evaluate_split(model,val_images,val_targets,criterion,config["batch_size"])
    if abs(source_metric["mean_iou"]-source["validation_metrics"]["mean_iou"])>1e-12: raise SystemExit("BLOCKED_CHECKPOINT_STATE: source inference mismatch")
    sentinel_scene_ids=[item["scene_id"] for item in json.loads((OUT/"stage10i_human_sentinel_selection.json").read_text())["low_recall"][:2]+json.loads((OUT/"stage10i_human_sentinel_selection.json").read_text())["high_recall"][:2]]
    scene_to_index={int(scene):index for index,scene in enumerate(validation.scene_ids)}; sentinel=val_images[[scene_to_index[scene] for scene in sentinel_scene_ids]]
    history=[]; lifecycle=[]; feasible_epochs=[]; feasible_key=None; best_human_key=None; best_miou_key=None; best_feasible_record=None; best_human_record=None; best_miou_record=None
    previous_parameters=torch.cat([parameter.detach().flatten() for parameter in model.parameters()])
    for epoch in range(146,196):
        model.train(); gradient_norms=[]
        for start in range(0,len(train_images),config["batch_size"]):
            optimizer.zero_grad(set_to_none=True); loss=criterion(model(train_images[start:start+config["batch_size"]]),train_targets[start:start+config["batch_size"]])
            if not torch.isfinite(loss): raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: NaN/Inf loss")
            loss.backward(); gradients=[parameter.grad for parameter in model.parameters() if parameter.grad is not None]
            if not gradients or not all(torch.isfinite(value).all() for value in gradients): raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: invalid gradients")
            gradient_norms.append(math.sqrt(sum(float(value.norm())**2 for value in gradients))); optimizer.step()
        current_parameters=torch.cat([parameter.detach().flatten() for parameter in model.parameters()]); update_norm=float((current_parameters-previous_parameters).norm()); previous_parameters=current_parameters.clone()
        train_loss,train_metric,_=evaluate_split(model,train_images,train_targets,criterion,config["batch_size"]); val_loss,val_metric,_=evaluate_split(model,val_images,val_targets,criterion,config["batch_size"])
        feasibility=validation_hard_feasibility(val_metric); errors=human_errors(val_metric); saved_roles=[]; reload_errors={}; state_hash=optimizer_hashes(optimizer.state_dict())["full_optimizer_state_hash"]
        human_key=(val_metric["per_class_recall"]["HUMAN"],val_metric["mean_iou"],val_metric["macro_f1"])
        miou_key=(val_metric["mean_iou"],val_metric["macro_f1"],val_metric["per_class_recall"]["HUMAN"])
        base_record={"epoch":epoch,"train":{"loss":train_loss,**metric_view(train_metric)},"validation":{"loss":val_loss,**metric_view(val_metric)},"human_errors":errors,"feasibility":feasibility,"learning_rate":optimizer.param_groups[0]["lr"],"gradient_norm_mean":float(np.mean(gradient_norms)),"parameter_update_norm":update_norm,"optimizer_moment_norm":optimizer_hashes(optimizer.state_dict())["optimizer_moment_norm"]}
        if best_human_key is None or human_key>best_human_key:
            payload=make_payload("DIAGNOSTIC_ONLY_BEST_HUMAN",epoch,model,optimizer,val_metric,val_loss,feasibility,config,source,state_hash); reload_errors["best_human"]=save_and_verify(BEST_HUMAN_PATH,payload,model,sentinel,lifecycle,"best_human"); best_human_key=human_key; best_human_record=base_record; saved_roles.append("best_human")
        if best_miou_key is None or miou_key>best_miou_key:
            payload=make_payload("DIAGNOSTIC_ONLY_BEST_MIOU",epoch,model,optimizer,val_metric,val_loss,feasibility,config,source,state_hash); reload_errors["best_miou"]=save_and_verify(BEST_MIOU_PATH,payload,model,sentinel,lifecycle,"best_miou"); best_miou_key=miou_key; best_miou_record=base_record; saved_roles.append("best_miou")
        if feasibility["passed"]:
            feasible_epochs.append(epoch); key=feasible_checkpoint_key(val_metric,val_loss)
            if feasible_key is None or key>feasible_key:
                payload=make_payload("VALIDATION_SELECTED_CANDIDATE",epoch,model,optimizer,val_metric,val_loss,feasibility,config,source,state_hash); reload_errors["feasible"]=save_and_verify(FEASIBLE_PATH,payload,model,sentinel,lifecycle,"feasible"); feasible_key=key; best_feasible_record=base_record; saved_roles.append("feasible")
        base_record.update({"checkpoint_roles_saved":saved_roles,"checkpoint_reload_max_errors":reload_errors}); history.append(base_record); (OUT/"stage10j_training_history.json").write_text(json.dumps(history,indent=2)+"\n")
        print(json.dumps({"epoch":epoch,"mIoU":val_metric["mean_iou"],"macro_f1":val_metric["macro_f1"],"human_iou":val_metric["per_class_iou"]["HUMAN"],"human_recall":val_metric["per_class_recall"]["HUMAN"],"vehicle_recall":val_metric["per_class_recall"]["VEHICLE"],"robot_recall":val_metric["per_class_recall"]["ROBOT"],"feasible":feasibility["passed"]}),flush=True)
    front=pareto_front(history); runs=[]; current=[]
    for epoch in feasible_epochs:
        if current and epoch!=current[-1]+1: runs.append(current); current=[]
        current.append(epoch)
    if current:runs.append(current)
    stability={"feasible_epoch_count":len(feasible_epochs),"feasible_epochs":feasible_epochs,"consecutive_feasible_runs":runs,"stable_feasible_runs_at_least_3_epochs":[run for run in runs if len(run)>=3],"stable_feasible_interval_exists":any(len(run)>=3 for run in runs)}
    pareto={"objectives":["mIoU","macro_f1","HUMAN_recall","HUMAN_IoU","VEHICLE_recall","ROBOT_recall"],"pareto_front_epochs":front,"records":[summary_record(item) for item in history if item["epoch"] in front]}
    bests={"best_human":summary_record(best_human_record),"best_miou":summary_record(best_miou_record),"best_feasible":summary_record(best_feasible_record) if best_feasible_record else None}
    comparison={"stage10i_epoch126":stage10i_record(126),"stage10i_epoch145":stage10i_record(145),"stage10j_best_human":bests["best_human"],"stage10j_best_miou":bests["best_miou"]}
    if bests["best_feasible"]: comparison["stage10j_best_feasible"]=bests["best_feasible"]
    comparison_output={"records":comparison,"low_lr_effect":"assessed from validation only","human_robot_competition": "reduced" if bests["best_human"]["robot_recall"]>=.8 else "persists", "human_vehicle_time_offset":abs(bests["best_human"]["epoch"]-bests["best_miou"]["epoch"]),"stage10i_epoch126_human_errors":"NOT_AVAILABLE_CHECKPOINT_NOT_RETAINED"}
    if best_feasible_record: decision="VALIDATION_MULTI_OBJECTIVE_RECOVERED"
    elif best_human_record["validation"]["per_class_recall"]["HUMAN"]>=.85: decision="BLOCKED_CLASS_TRADEOFF"
    elif best_miou_record["validation"]["mean_iou"]<source_metric["mean_iou"]-.02: decision="BLOCKED_LOW_LR_STABILIZATION"
    else: decision="BLOCKED_OPTIMIZATION_CONVERGENCE"
    validation_summary={"decision":decision,"epochs_executed":50,"epoch_range":[146,195],"learning_rate":.0002,"source_epoch":145,"source_validation_metrics":metric_view(source_metric),"best_records":bests,"feasibility":stability,"original_test_accessed":False,"new_audit_accessed":False}
    (OUT/"stage10j_validation_metrics.json").write_text(json.dumps(validation_summary,indent=2)+"\n"); (OUT/"stage10j_validation_feasibility.json").write_text(json.dumps({"hard_gate_logic":"AND","thresholds":{"mIoU":.78,"macro_f1":.87,"HUMAN_IoU":.65,"HUMAN_recall":.85,"VEHICLE_recall":.75,"ROBOT_recall":.80},**stability,"best_feasible":bests["best_feasible"]},indent=2)+"\n"); (OUT/"stage10j_validation_pareto.json").write_text(json.dumps(pareto,indent=2)+"\n"); (OUT/"stage10j_metric_stability.json").write_text(json.dumps(stability,indent=2)+"\n"); (OUT/"stage10j_stage10i_comparison.json").write_text(json.dumps(comparison_output,indent=2)+"\n"); (OUT/"stage10j_checkpoint_lifecycle.json").write_text(json.dumps({"events":lifecycle,"all_atomic":True,"all_reload_differences_within_1e-7":all(item["reload_max_abs_difference"]<=1e-7 for item in lifecycle),"selection_split":"validation_only","test_accessed":False,"new_audit_accessed":False},indent=2)+"\n")
    plots(history,comparison)
    print(json.dumps(validation_summary,indent=2))


if __name__ == "__main__": main()
