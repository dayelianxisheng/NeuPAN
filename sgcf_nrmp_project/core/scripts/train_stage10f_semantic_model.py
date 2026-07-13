#!/usr/bin/env python3
"""Train once on train, select checkpoint and confidence policy on validation."""

from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path

import numpy as np
import torch
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.evaluation.semantic_perception_evaluator import (
    collect_probabilities,
    evaluate_probabilities,
)
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.perception.semantic_confidence import confidence_classes, semantic_entropy
from sgcf_nrmp.evaluation.threshold_summary import build_threshold_summary
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all
from sgcf_nrmp.training.class_weight_audit import (
    audit_source_class_weights,
    build_audited_cross_entropy,
)


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = ROOT / "core/configs/train/stage_10f_full_training.yaml"
CLASS_NAMES = ("UNKNOWN", "STATIC_OBSTACLE", "HUMAN", "VEHICLE", "ROBOT")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


def load_tensors(dataset: RGBSemanticDataset) -> tuple[torch.Tensor, torch.Tensor]:
    images = torch.stack([dataset[index]["image"] for index in range(len(dataset))])
    targets = torch.stack([dataset[index]["target"] for index in range(len(dataset))])
    return images, targets


@torch.no_grad()
def split_metrics(model, images, targets, criterion, batch_size):
    model.eval()
    probabilities = collect_probabilities(model, images, batch_size)
    losses = []
    for start in range(0, len(images), batch_size):
        losses.append(float(criterion(model(images[start:start + batch_size]), targets[start:start + batch_size])))
    return float(np.mean(losses)), evaluate_probabilities(probabilities, targets.numpy()), probabilities


def confidence_prediction(probabilities: np.ndarray, probability_threshold=None, entropy_threshold=None) -> np.ndarray:
    tensor = torch.from_numpy(probabilities)
    return confidence_classes(tensor, probability_threshold, entropy_threshold)[0].numpy()


def policy_metrics(probabilities: np.ndarray, targets: np.ndarray, probability_threshold=None, entropy_threshold=None):
    prediction = confidence_prediction(probabilities, probability_threshold, entropy_threshold)
    metrics = evaluate_probabilities(probabilities, targets, prediction)
    margins = np.array([0.0, 0.0, 0.35, 0.20, 0.15])
    oracle_margin = margins[targets]
    predicted_margin = margins[prediction]
    positive = oracle_margin > 0
    threshold_summary = build_threshold_summary(targets, prediction)
    static_to_human = threshold_summary["static_to_human_rate"]
    human_recall = threshold_summary["human_recall"]
    margin_underestimation = float(np.mean(predicted_margin[positive] + 0.05 < oracle_margin[positive])) if positive.any() else 0.0
    metrics.update({
        "probability_threshold": probability_threshold,
        "entropy_threshold": entropy_threshold,
        "threshold_summary": threshold_summary,
        "human_recall": human_recall["value"],
        "static_to_human_rate": static_to_human["value"],
        "pixel_margin_underestimation_rate": margin_underestimation,
    })
    if not human_recall["valid"] or not static_to_human["valid"]:
        raise ValueError("threshold selection metrics have a zero denominator")
    metrics["selection_score"] = float(
        metrics["macro_f1"] + human_recall["value"]
        - static_to_human["value"] - margin_underestimation
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    arguments = parser.parse_args()
    config_text = CONFIG_PATH.read_text()
    config = yaml.safe_load(config_text)
    (OUT / "stage10f_training_config.yaml").write_text(config_text)
    train_path = OUT / "dataset/train.npz"
    validation_path = OUT / "dataset/validation.npz"
    test_path = OUT / "dataset/test.npz"
    train = RGBSemanticDataset(train_path)
    validation = RGBSemanticDataset(validation_path)

    # Test is opened only for static IDs/dtype/hash auditing; no test inference or metric is computed.
    test_raw = np.load(test_path, allow_pickle=False)
    manifest_path = OUT / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())["records"]
    split_ids = {split: {record["scene_id"] for record in manifest if record["split"] == split} for split in ("train", "validation", "test")}
    seed_keys = ("geometry_seed", "appearance_seed", "camera_seed")
    seed_disjoint = {}
    for key in seed_keys:
        sets = {split: {record[key] for record in manifest if record["split"] == split} for split in split_ids}
        seed_disjoint[key] = not (sets["train"] & sets["validation"] or sets["train"] & sets["test"] or sets["validation"] & sets["test"])
    selection = json.loads((OUT / "stage10e_48_image_selection.json").read_text())
    for record in selection["records"]:
        index = record["scene_id"]
        if array_sha256(train.images[index]) != record["rgb_sha256"] or array_sha256(train.masks[index]) != record["semantic_label_sha256"]:
            raise SystemExit(f"BLOCKED_DATA_INCONSISTENCY: authoritative Stage 10E hash mismatch at {index}")
    yaml_weights = list(config["class_weights"])
    stage10e_weights = json.loads((OUT / "stage10e_class_weight_confirmation.json").read_text())["stage10d_weights"]
    authoritative_order = list(stage10e_weights.keys())
    authoritative_weights = list(stage10e_weights.values())
    source_weight_audit = audit_source_class_weights(
        yaml_weights,
        authoritative_weights,
        list(CLASS_NAMES),
        authoritative_order,
    )
    if not source_weight_audit["passed"]:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: float64 source class weights changed")
    runtime_weights, criterion, runtime_weight_audit = build_audited_cross_entropy(authoritative_weights)
    audit = {
        "split_counts": {name: len(ids) for name, ids in split_ids.items()},
        "scene_id_disjoint": not (split_ids["train"] & split_ids["validation"] or split_ids["train"] & split_ids["test"] or split_ids["validation"] & split_ids["test"]),
        "seed_disjoint": seed_disjoint,
        "dataset_file_sha256": {"train": file_sha256(train_path), "validation": file_sha256(validation_path), "test": file_sha256(test_path)},
        "manifest_sha256": file_sha256(manifest_path),
        "authoritative_stage10e_hashes_match": True,
        "train_label_ids": np.unique(train.masks).tolist(),
        "validation_label_ids": np.unique(validation.masks).tolist(),
        "test_label_ids_static_audit_only": np.unique(test_raw["semantic_masks"]).tolist(),
        "target_dtype": "torch.int64",
        "logits_channels": 5,
        "unknown_is_ignore_index": False,
        "class_order": dict(zip(CLASS_NAMES, range(5))),
        "class_weights": dict(zip(CLASS_NAMES, authoritative_weights)),
        "weighted_ce_order_matches": True,
        "class_weight_source_audit": source_weight_audit,
        "class_weight_runtime_cast_audit": runtime_weight_audit,
        "cross_entropy_uses_audited_runtime_tensor": criterion.weight is runtime_weights,
        "all_inputs_finite": bool(np.isfinite(train.images).all() and np.isfinite(validation.images).all() and np.isfinite(test_raw["images"]).all()),
        "all_labels_valid": bool(all(np.array_equal(np.unique(mask), np.arange(5)) for mask in (train.masks, validation.masks, test_raw["semantic_masks"]))),
        "model_input_fields": ["current_rgb_image"],
        "test_metrics_read_before_checkpoint_freeze": False,
    }
    sample = train[0]
    audit_model = TinySemanticSegmentation()
    with torch.no_grad():
        audit_logits = audit_model(sample["image"].unsqueeze(0))
    audit.update({
        "target_dtype_observed": str(sample["target"].dtype),
        "logits_shape_observed": list(audit_logits.shape),
        "logits_channels_observed": int(audit_logits.shape[1]),
        "logits_finite": bool(torch.isfinite(audit_logits).all()),
    })
    if not audit["scene_id_disjoint"] or not all(seed_disjoint.values()) or not audit["all_labels_valid"]:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: pretraining audit failed")
    (OUT / "stage10f_pretraining_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    precision_audit = {
        "status": "PASSED",
        "class_weight_source_audit": source_weight_audit,
        "class_weight_runtime_cast_audit": runtime_weight_audit,
        "cross_entropy_uses_audited_runtime_tensor": criterion.weight is runtime_weights,
        "optimizer_steps_before_fix": 0,
        "frozen_weight_values_modified": False,
    }
    (OUT / "stage10f_weight_precision_audit.json").write_text(json.dumps(precision_audit, indent=2) + "\n")
    if arguments.audit_only:
        print(json.dumps({"audit": audit, "weight_precision": precision_audit}, indent=2))
        return

    train_images, train_targets = load_tensors(train)
    validation_images, validation_targets = load_tensors(validation)
    seed_all(config["seed"])
    torch.set_num_threads(4)
    model = TinySemanticSegmentation()
    if model.parameter_count != config["model_parameter_count"]:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: model architecture changed")
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=0.0)
    history = []
    best_key = None
    best_state = None
    best_epoch = None
    epochs_without_improvement = 0
    collapse_epochs = 0
    human_zero_epochs_after_grace = 0
    for epoch in range(1, config["maximum_epochs"] + 1):
        model.train()
        batch_losses = []
        for start in range(0, len(train_images), config["batch_size"]):
            images = train_images[start:start + config["batch_size"]]
            targets = train_targets[start:start + config["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, targets)
            if not torch.isfinite(loss):
                raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: non-finite training loss")
            loss.backward()
            if not all(torch.isfinite(parameter.grad).all() for parameter in model.parameters() if parameter.grad is not None):
                raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: non-finite gradients")
            optimizer.step()
            batch_losses.append(float(loss.detach()))
        train_loss, train_metrics, _ = split_metrics(model, train_images, train_targets, criterion, config["batch_size"])
        validation_loss, validation_metrics, _ = split_metrics(model, validation_images, validation_targets, criterion, config["batch_size"])
        record = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "train_loss": train_loss,
            "validation_loss": validation_loss,
            "train_pixel_accuracy": train_metrics["pixel_accuracy"],
            "validation_pixel_accuracy": validation_metrics["pixel_accuracy"],
            "validation_macro_f1": validation_metrics["macro_f1"],
            "validation_mean_iou": validation_metrics["mean_iou"],
            "validation_per_class_iou": validation_metrics["per_class_iou"],
            "validation_per_class_recall": validation_metrics["per_class_recall"],
            "validation_prediction_class_fraction": validation_metrics["prediction_class_fraction"],
        }
        history.append(record)
        fractions = validation_metrics["prediction_class_fraction"]
        if epoch > 20 and all(fractions[name] == 0.0 for name in ("HUMAN", "VEHICLE", "ROBOT")):
            collapse_epochs += 1
        else:
            collapse_epochs = 0
        if collapse_epochs >= 5:
            (OUT / "stage10f_training_history.json").write_text(json.dumps(history, indent=2) + "\n")
            raise SystemExit("BLOCKED_CLASS_COLLAPSE: three core prediction fractions zero for five epochs")
        if epoch > 20 and validation_metrics["per_class_recall"]["HUMAN"] == 0.0:
            human_zero_epochs_after_grace += 1
        else:
            human_zero_epochs_after_grace = 0
        if human_zero_epochs_after_grace >= 10:
            (OUT / "stage10f_training_history.json").write_text(json.dumps(history, indent=2) + "\n")
            raise SystemExit("BLOCKED_CLASS_COLLAPSE: validation HUMAN recall remained zero after warm-up")
        key = (
            validation_metrics["mean_iou"],
            validation_metrics["per_class_iou"]["HUMAN"],
            validation_metrics["per_class_recall"]["HUMAN"],
            -validation_loss,
        )
        if best_key is None or key > best_key:
            best_key = key
            best_epoch = epoch
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        if epochs_without_improvement >= config["early_stopping_patience"]:
            break
    (OUT / "stage10f_training_history.json").write_text(json.dumps(history, indent=2) + "\n")
    if best_state is None:
        raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: no validation checkpoint")
    model.load_state_dict(best_state)
    validation_loss, validation_argmax_metrics, validation_probabilities = split_metrics(model, validation_images, validation_targets, criterion, config["batch_size"])
    validation_targets_numpy = validation_targets.numpy()

    candidates = []
    candidates.append({"policy": "U0_argmax_always", **policy_metrics(validation_probabilities, validation_targets_numpy)})
    for threshold in config["threshold_candidates"]["probability"]:
        candidates.append({"policy": "U1_max_probability", **policy_metrics(validation_probabilities, validation_targets_numpy, threshold)})
    for probability_threshold in config["threshold_candidates"]["probability"]:
        for entropy_threshold in config["threshold_candidates"]["entropy"]:
            candidates.append({"policy": "U2_probability_and_entropy", **policy_metrics(validation_probabilities, validation_targets_numpy, probability_threshold, entropy_threshold)})
    selected = max(candidates, key=lambda item: (item["selection_score"], item["human_recall"], item["macro_f1"], -item["unknown_rate"]))
    threshold_selection = {
        "selection_split": "validation_only",
        "selection_objective": "macro_f1 + HUMAN_recall - STATIC_to_HUMAN_rate - pixel_margin_underestimation_rate",
        "candidates": candidates,
        "selected_policy": selected["policy"],
        "selected_probability_threshold": selected["probability_threshold"],
        "selected_entropy_threshold": selected["entropy_threshold"],
        "selected_metrics": selected,
        "test_accessed_for_selection": False,
    }
    (OUT / "stage10f_threshold_selection.json").write_text(json.dumps(threshold_selection, indent=2) + "\n")
    validation_output = {
        "best_epoch": best_epoch,
        "epochs_executed": len(history),
        "early_stopped": len(history) < config["maximum_epochs"],
        "checkpoint_selection_order": ["validation_mean_iou", "HUMAN_iou", "HUMAN_recall", "negative_validation_loss"],
        "validation_loss": validation_loss,
        "argmax_metrics": validation_argmax_metrics,
        "selected_confidence_policy_metrics": selected,
    }
    (OUT / "stage10f_validation_metrics.json").write_text(json.dumps(validation_output, indent=2) + "\n")

    config_hash = hashlib.sha256(config_text.encode()).hexdigest()
    checkpoint = {
        "purpose": "Stage 10F validation-selected synthetic RGB semantic model",
        "model_state_dict": best_state,
        "model_architecture": "TinySemanticSegmentation(base_channels=16,class_count=5)",
        "class_mapping": dict(zip(CLASS_NAMES, range(5))),
        "normalization": "uint8 RGB to float32 [0,1]",
        "input_resolution_hw": [120, 160],
        "probability_threshold": selected["probability_threshold"],
        "entropy_threshold": selected["entropy_threshold"],
        "confidence_policy": selected["policy"],
        "training_config_sha256": config_hash,
        "dataset_manifest_sha256": audit["manifest_sha256"],
        "seed": config["seed"],
        "best_epoch": best_epoch,
        "validation_mean_iou": validation_argmax_metrics["mean_iou"],
    }
    checkpoint_path = OUT / "best_rgb_semantic_model.pt"
    torch.save(checkpoint, checkpoint_path)
    metadata = {key: value for key, value in checkpoint.items() if key != "model_state_dict"}
    metadata["checkpoint_file"] = checkpoint_path.name
    metadata["test_evaluation_completed"] = False
    (OUT / "stage10f_checkpoint_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    probe = validation_images[:2]
    model.eval()
    with torch.no_grad():
        before = model(probe)
    restored_checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    restored = TinySemanticSegmentation()
    restored.load_state_dict(restored_checkpoint["model_state_dict"])
    restored.eval()
    with torch.no_grad():
        after = restored(probe)
    reload_report = {
        "probe_split": "validation",
        "probe_scene_ids": validation.scene_ids[:2].tolist(),
        "logits_max_absolute_difference": float((before - after).abs().max()),
        "tolerance": 1e-7,
        "pass": bool(torch.equal(before, after)),
    }
    (OUT / "stage10f_checkpoint_reload.json").write_text(json.dumps(reload_report, indent=2) + "\n")
    print(json.dumps({"audit": audit, "validation": validation_output, "threshold": threshold_selection, "reload": reload_report}, indent=2))


if __name__ == "__main__":
    main()
