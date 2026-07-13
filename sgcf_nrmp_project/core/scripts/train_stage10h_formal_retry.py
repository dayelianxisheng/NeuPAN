#!/usr/bin/env python3
"""Run the single authorized Stage 10H formal training retry."""

from __future__ import annotations

import hashlib
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
from sgcf_nrmp.training.class_weight_audit import (
    audit_source_class_weights,
    build_audited_cross_entropy,
)
from sgcf_nrmp.training.lifecycle import (
    WarmupEarlyStopping,
    atomic_torch_save,
    evaluate_split,
    validation_checkpoint_key,
    validation_readiness,
)
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = ROOT / "core/configs/train/stage_10h_formal_retry.yaml"
CHECKPOINT_PATH = OUT / "best_rgb_semantic_model.pt"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_array(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


def tensors(dataset: RGBSemanticDataset) -> tuple[torch.Tensor, torch.Tensor]:
    return (
        torch.stack([dataset[index]["image"] for index in range(len(dataset))]),
        torch.stack([dataset[index]["target"] for index in range(len(dataset))]),
    )


def metric_view(metrics: dict) -> dict:
    return {
        key: metrics[key]
        for key in (
            "pixel_accuracy", "mean_iou", "macro_f1", "per_class_iou",
            "per_class_recall", "prediction_class_fraction", "confusion_matrix",
        )
    }


def pretraining_audit(config: dict, config_text: str):
    manifest_path = OUT / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())["records"]
    split_ids = {
        split: {int(record["scene_id"]) for record in manifest if record["split"] == split}
        for split in ("train", "validation", "test")
    }
    seed_disjoint = {}
    for key in ("geometry_seed", "appearance_seed", "camera_seed"):
        values = {
            split: {record[key] for record in manifest if record["split"] == split}
            for split in split_ids
        }
        seed_disjoint[key] = not (
            values["train"] & values["validation"]
            or values["train"] & values["test"]
            or values["validation"] & values["test"]
        )
    train_path = OUT / "dataset/train.npz"
    validation_path = OUT / "dataset/validation.npz"
    train = RGBSemanticDataset(train_path)
    validation = RGBSemanticDataset(validation_path)
    selection = json.loads((OUT / "stage10e_48_image_selection.json").read_text())
    authoritative_hashes_match = True
    for record in selection["records"]:
        index = int(record["scene_id"])
        authoritative_hashes_match &= sha256_array(train.images[index]) == record["rgb_sha256"]
        authoritative_hashes_match &= sha256_array(train.masks[index]) == record["semantic_label_sha256"]
    stage10e_weights = json.loads((OUT / "stage10e_class_weight_confirmation.json").read_text())["stage10d_weights"]
    authoritative_order = list(stage10e_weights)
    authoritative_weights = list(stage10e_weights.values())
    source_audit = audit_source_class_weights(
        list(config["class_weights"]), authoritative_weights, list(CLASS_NAMES), authoritative_order
    )
    runtime_weights, criterion, runtime_audit = build_audited_cross_entropy(authoritative_weights)
    sample = train[0]
    seed_all(config["seed"])
    probe_model = TinySemanticSegmentation()
    with torch.no_grad():
        logits = probe_model(sample["image"].unsqueeze(0))
    scene_disjoint = not (
        split_ids["train"] & split_ids["validation"]
        or split_ids["train"] & split_ids["test"]
        or split_ids["validation"] & split_ids["test"]
    )
    audit = {
        "status": "PASSED",
        "split_counts": {split: len(values) for split, values in split_ids.items()},
        "scene_id_disjoint": scene_disjoint,
        "seed_disjoint": seed_disjoint,
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "dataset_file_sha256": {
            "train": sha256_file(train_path),
            "validation": sha256_file(validation_path),
            "test": "not_reopened_before_validation_readiness; authoritative Stage10F-A audit retained",
        },
        "authoritative_stage10e_hashes_match": bool(authoritative_hashes_match),
        "class_weight_source_audit": source_audit,
        "class_weight_runtime_cast_audit": runtime_audit,
        "class_order": dict(zip(CLASS_NAMES, range(5))),
        "cross_entropy_uses_audited_runtime_tensor": criterion.weight is runtime_weights,
        "train_label_ids": np.unique(train.masks).tolist(),
        "validation_label_ids": np.unique(validation.masks).tolist(),
        "unknown_is_ignore_index": False,
        "target_dtype_observed": str(sample["target"].dtype),
        "logits_shape_observed": list(logits.shape),
        "cross_entropy_input": "raw_logits",
        "train_validation_inputs_finite": bool(np.isfinite(train.images).all() and np.isfinite(validation.images).all()),
        "test_dataset_instantiated_for_evaluation": False,
        "test_images_or_labels_read": False,
        "training_config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
    }
    passed = all((
        scene_disjoint, all(seed_disjoint.values()), authoritative_hashes_match,
        source_audit["passed"], runtime_audit["passed"], criterion.weight is runtime_weights,
        audit["train_label_ids"] == list(range(5)), audit["validation_label_ids"] == list(range(5)),
        sample["target"].dtype == torch.long, logits.shape[1] == 5,
        audit["train_validation_inputs_finite"], bool(torch.isfinite(logits).all()),
    ))
    audit["status"] = "PASSED" if passed else "BLOCKED_DATA_INCONSISTENCY"
    (OUT / "stage10h_pretraining_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    if not passed:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: Stage 10H pretraining audit failed")
    return train, validation, runtime_weights, criterion, audit


def save_checkpoint(model, optimizer, epoch, validation_metrics, validation_loss, config, config_text, audit, validation_probe):
    payload = {
        "purpose": "Stage 10H formal validation-selected synthetic RGB semantic model",
        "epoch": epoch,
        "best_epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "validation_metrics": metric_view(validation_metrics),
        "validation_loss": validation_loss,
        "class_mapping": dict(zip(CLASS_NAMES, range(5))),
        "model_architecture": "TinySemanticSegmentation(base_channels=16,class_count=5)",
        "normalization": "uint8 RGB to float32 [0,1]",
        "input_resolution_hw": [config["input_height"], config["input_width"]],
        "class_weights": config["class_weights"],
        "dataset_manifest_sha256": audit["dataset_manifest_sha256"],
        "training_config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "seed": config["seed"],
        "early_stopping_policy": {
            "maximum_epochs": 100, "minimum_training_epochs": 60,
            "patience": 20, "min_delta": 1e-4, "monitor": "validation_mean_iou",
        },
        "confidence_policy": None,
        "probability_threshold": None,
        "entropy_threshold": None,
    }
    atomic_torch_save(payload, CHECKPOINT_PATH)
    restored_payload = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    restored = TinySemanticSegmentation()
    restored.load_state_dict(restored_payload["model_state_dict"])
    restored.eval(); model.eval()
    with torch.no_grad():
        difference = float((model(validation_probe) - restored(validation_probe)).abs().max())
    if difference > 1e-7:
        raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: checkpoint reload mismatch")
    return difference


def write_plots(history: list[dict]) -> None:
    epochs = [item["epoch"] for item in history]
    for filename, field, ylabel in (
        ("stage10h_train_validation_loss.png", "loss", "loss"),
        ("stage10h_train_validation_miou.png", "mean_iou", "mean IoU"),
        ("stage10h_train_validation_macro_f1.png", "macro_f1", "macro F1"),
    ):
        fig, ax = plt.subplots()
        ax.plot(epochs, [item["train"][field] for item in history], label="train")
        ax.plot(epochs, [item["validation"][field] for item in history], label="validation")
        ax.set(xlabel="epoch", ylabel=ylabel); ax.grid(); ax.legend(); fig.tight_layout()
        fig.savefig(OUT / filename, dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for split, ax in zip(("train", "validation"), axes):
        for name in CLASS_NAMES[2:]:
            ax.plot(epochs, [item[split]["per_class_recall"][name] for item in history], label=name)
        ax.set(title=split, xlabel="epoch", ylabel="recall", ylim=(-.02, 1.02)); ax.grid(); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "stage10h_per_class_recall.png", dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for split, ax in zip(("train", "validation"), axes):
        for name in CLASS_NAMES:
            ax.plot(epochs, [item[split]["prediction_class_fraction"][name] for item in history], label=name)
        ax.set(title=split, xlabel="epoch", ylabel="prediction fraction"); ax.grid(); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT / "stage10h_prediction_class_fractions.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots()
    ax.plot(epochs, [item["validation"]["mean_iou"] for item in history], label="validation mIoU")
    ax.axvline(60, color="orange", linestyle="--", label="warm-up end")
    stop = history[-1]["epoch"]
    ax.axvline(stop, color="red", linestyle=":", label=f"training end {stop}")
    ax.set(xlabel="epoch", ylabel="mIoU"); ax.grid(); ax.legend(); fig.tight_layout()
    fig.savefig(OUT / "stage10h_early_stopping_timeline.png", dpi=150); plt.close(fig)


def main() -> None:
    config_text = CONFIG_PATH.read_text()
    config = yaml.safe_load(config_text)
    (OUT / "stage10h_training_config.yaml").write_text(config_text)
    train, validation, _, criterion, audit = pretraining_audit(config, config_text)
    train_images, train_targets = tensors(train)
    validation_images, validation_targets = tensors(validation)
    seed_all(config["seed"])
    torch.set_num_threads(4)
    model = TinySemanticSegmentation()
    if model.parameter_count != config["model_parameter_count"]:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: frozen model changed")
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    policy = WarmupEarlyStopping(60, 20, 1e-4)
    history = []
    checkpoint_events = []
    best_key = None
    best_epoch = None
    previous_parameters = torch.cat([parameter.detach().flatten() for parameter in model.parameters()])
    collapse_counter = 0
    actual_stop_reason = "MAXIMUM_EPOCHS"
    for epoch in range(1, config["maximum_epochs"] + 1):
        model.train()
        gradient_norms = []
        for start in range(0, len(train_images), config["batch_size"]):
            images = train_images[start:start + config["batch_size"]]
            targets = train_targets[start:start + config["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), targets)
            if not torch.isfinite(loss):
                raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: non-finite loss")
            loss.backward()
            gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
            if not gradients or not all(torch.isfinite(value).all() for value in gradients):
                raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: invalid gradients")
            gradient_norms.append(math.sqrt(sum(float(value.norm()) ** 2 for value in gradients)))
            optimizer.step()
        current_parameters = torch.cat([parameter.detach().flatten() for parameter in model.parameters()])
        update_norm = float((current_parameters - previous_parameters).norm())
        previous_parameters = current_parameters.clone()
        train_loss, train_metrics, _ = evaluate_split(model, train_images, train_targets, criterion, config["batch_size"])
        validation_loss, validation_metrics, _ = evaluate_split(model, validation_images, validation_targets, criterion, config["batch_size"])
        checkpoint_saved = False
        reload_difference = None
        key = validation_checkpoint_key(validation_metrics, validation_loss)
        if best_key is None or key > best_key:
            reload_difference = save_checkpoint(
                model, optimizer, epoch, validation_metrics, validation_loss,
                config, config_text, audit, validation_images[:2],
            )
            checkpoint_saved = True
            best_key = key
            best_epoch = epoch
            checkpoint_events.append({
                "epoch": epoch, "atomic_save": True, "saved_before_early_stopping_update": True,
                "reload_max_abs_difference": reload_difference,
            })
        early = policy.update(epoch, validation_metrics["mean_iou"])
        core_recall = validation_metrics["per_class_recall"]
        if epoch > 60 and all(core_recall[name] == 0 for name in CLASS_NAMES[2:]):
            collapse_counter += 1
        else:
            collapse_counter = 0
        history.append({
            "epoch": epoch,
            "train": {"loss": train_loss, **metric_view(train_metrics)},
            "validation": {"loss": validation_loss, **metric_view(validation_metrics)},
            "learning_rate": optimizer.param_groups[0]["lr"],
            "gradient_norm_mean": float(np.mean(gradient_norms)),
            "parameter_update_norm": update_norm,
            "best_metric": policy.best_metric,
            "best_epoch": best_epoch,
            "simulated_early_stopping_counter": early["counter"],
            "actual_early_stopping_counter": early["counter"],
            "warmup_active": early["warmup"],
            "checkpoint_saved_this_epoch": checkpoint_saved,
            "checkpoint_reload_max_abs_difference": reload_difference,
            "all_core_zero_recall_counter_after_warmup": collapse_counter,
        })
        (OUT / "stage10h_training_history.json").write_text(json.dumps(history, indent=2) + "\n")
        print(json.dumps({
            "epoch": epoch, "train_miou": train_metrics["mean_iou"],
            "validation_miou": validation_metrics["mean_iou"],
            "validation_macro_f1": validation_metrics["macro_f1"],
            "validation_core_recall": {name: core_recall[name] for name in CLASS_NAMES[2:]},
            "best_epoch": best_epoch, "early_counter": early["counter"],
        }), flush=True)
        if collapse_counter >= 5:
            actual_stop_reason = "BLOCKED_CLASS_COLLAPSE"
            break
        if early["stop"]:
            actual_stop_reason = "EARLY_STOPPING_PATIENCE"
            break
    if not CHECKPOINT_PATH.exists():
        raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: no formal checkpoint")
    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    best_model = TinySemanticSegmentation(); best_model.load_state_dict(checkpoint["model_state_dict"])
    best_validation_loss, best_validation_metrics, _ = evaluate_split(
        best_model, validation_images, validation_targets, criterion, config["batch_size"]
    )
    readiness = validation_readiness(best_validation_metrics)
    readiness.update({
        "status": "VALIDATION_READY_FOR_TEST" if readiness["passed"] else "VALIDATION_READINESS_FAILED",
        "best_epoch": checkpoint["epoch"], "epochs_executed": len(history),
        "best_validation_loss": best_validation_loss, "best_validation_metrics": metric_view(best_validation_metrics),
        "test_accessed": False,
    })
    (OUT / "stage10h_validation_metrics.json").write_text(json.dumps(readiness["best_validation_metrics"], indent=2) + "\n")
    (OUT / "stage10h_validation_readiness.json").write_text(json.dumps(readiness, indent=2) + "\n")
    first_positive = {
        split: {name: next((item["epoch"] for item in history if item[split]["per_class_recall"][name] > 0), None) for name in CLASS_NAMES[2:]}
        for split in ("train", "validation")
    }
    early_history = {
        "policy": {"maximum_epochs": 100, "minimum_training_epochs": 60, "patience": 20, "min_delta": 1e-4, "monitor": "validation_mean_iou"},
        "warmup_prevents_actual_stop_through_epoch_60": True,
        "actual_stop_reason": actual_stop_reason,
        "epochs_executed": len(history), "best_epoch": checkpoint["epoch"],
        "first_positive_recall_epoch": first_positive,
        "history": [{"epoch": item["epoch"], "counter": item["actual_early_stopping_counter"], "warmup": item["warmup_active"]} for item in history],
    }
    lifecycle = {
        "checkpoint_path": CHECKPOINT_PATH.name, "formal_checkpoint": True,
        "atomic_write": True, "fsync_before_rename": True, "reload_verified_each_save": True,
        "save_occurs_before_early_stopping_update": True,
        "reporting_and_threshold_summary_cannot_block_save": True,
        "events": checkpoint_events, "final_best_epoch": checkpoint["epoch"],
        "final_reload_max_abs_difference": checkpoint_events[-1]["reload_max_abs_difference"],
    }
    (OUT / "stage10h_early_stopping_history.json").write_text(json.dumps(early_history, indent=2) + "\n")
    (OUT / "stage10h_checkpoint_lifecycle.json").write_text(json.dumps(lifecycle, indent=2) + "\n")
    metadata = {key: value for key, value in checkpoint.items() if key not in ("model_state_dict", "optimizer_state_dict")}
    metadata.update({"checkpoint_file": CHECKPOINT_PATH.name, "validation_readiness_passed": readiness["passed"]})
    (OUT / "stage10h_checkpoint_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (OUT / "stage10h_checkpoint_reload.json").write_text(json.dumps({
        "events": checkpoint_events, "final_max_abs_difference": checkpoint_events[-1]["reload_max_abs_difference"],
        "tolerance": 1e-7, "passed": checkpoint_events[-1]["reload_max_abs_difference"] <= 1e-7,
    }, indent=2) + "\n")
    write_plots(history)
    if not readiness["passed"]:
        recalls = best_validation_metrics["per_class_recall"]
        if actual_stop_reason == "BLOCKED_CLASS_COLLAPSE": decision = "BLOCKED_CLASS_COLLAPSE"
        elif recalls["HUMAN"] < .75: decision = "BLOCKED_HUMAN_RECALL"
        elif recalls["VEHICLE"] < .50: decision = "BLOCKED_VEHICLE_RECALL"
        elif recalls["ROBOT"] < .50: decision = "BLOCKED_ROBOT_RECALL"
        elif best_validation_metrics["mean_iou"] < .50 or best_validation_metrics["macro_f1"] < .60: decision = "BLOCKED_GENERALIZATION"
        else: decision = "BLOCKED_OPTIMIZATION_CONVERGENCE"
        placeholder = {"status": "NOT_EXECUTED_DUE_TO_VALIDATION_READINESS_FAILURE", "test_accessed": False}
        for filename in (
            "stage10h_validation_freeze.json", "stage10h_threshold_selection.json", "stage10h_test_pixel_metrics.json",
            "stage10h_per_class_metrics.json", "stage10h_boundary_metrics.json", "stage10h_confusion_matrix.json",
            "stage10h_predicted_pointpainting_metrics.json", "stage10h_semantic_margin_gap.json",
            "stage10h_robustness_metrics.json", "stage10h_perception_latency.json",
        ):
            (OUT / filename).write_text(json.dumps(placeholder, indent=2) + "\n")
        (OUT / "stage_10h_decision.md").write_text(f"# Stage 10H Decision\n\n`{decision}`\n\nValidation readiness failed; test and all downstream evaluation were not executed.\n")
    print(json.dumps({"readiness": readiness, "first_positive": first_positive, "stop_reason": actual_stop_reason}, indent=2))


if __name__ == "__main__":
    main()
