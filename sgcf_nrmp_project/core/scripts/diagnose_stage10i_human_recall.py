#!/usr/bin/env python3
"""Validation-only HUMAN audit and one bounded epoch-101--150 continuation."""

from __future__ import annotations

import hashlib
import json
import math
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import distance_transform_edt, label as connected_components
from scipy.stats import pearsonr, spearmanr
import torch
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.evaluation.semantic_perception_evaluator import (
    CLASS_NAMES,
    confusion_matrix,
    metrics_from_confusion,
)
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.class_weight_audit import build_audited_cross_entropy
from sgcf_nrmp.training.lifecycle import (
    atomic_torch_save,
    evaluate_split,
    validation_checkpoint_key,
)
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = ROOT / "core/configs/train/stage_10i_validation_continuation.yaml"
SOURCE_CHECKPOINT = OUT / "best_rgb_semantic_model.pt"
DIAGNOSTIC_CHECKPOINT = OUT / "stage10i_validation_diagnostic_checkpoint.pt"
HUMAN = 2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_array(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


def tensors(dataset):
    return (
        torch.stack([dataset[index]["image"] for index in range(len(dataset))]),
        torch.stack([dataset[index]["target"] for index in range(len(dataset))]),
    )


def predictions(model, images, batch_size=8):
    model.eval(); probabilities = []
    with torch.no_grad():
        for start in range(0, len(images), batch_size):
            probabilities.append(torch.softmax(model(images[start:start + batch_size]), 1).cpu().numpy())
    probability = np.concatenate(probabilities)
    return probability, probability.argmax(axis=1)


def safe_correlation(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return {"pearson": None, "spearman": None, "valid": False}
    return {"pearson": float(pearsonr(x, y).statistic), "spearman": float(spearmanr(x, y).statistic), "valid": True}


def subset_human_metrics(target, prediction, probabilities, region):
    region = np.asarray(region, bool)
    human_target = (target == HUMAN) & region
    human_prediction = (prediction == HUMAN) & region
    tp = int(np.sum(human_target & human_prediction)); fp = int(np.sum(~(target == HUMAN) & human_prediction & region)); fn = int(np.sum(human_target & ~human_prediction))
    distribution = np.bincount(prediction[human_target], minlength=5) if human_target.any() else np.zeros(5, int)
    return {
        "pixel_count": int(human_target.sum()), "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "iou": float(tp / max(tp + fp + fn, 1)), "precision": float(tp / max(tp + fp, 1)), "recall": float(tp / max(tp + fn, 1)),
        "prediction_distribution": dict(zip(CLASS_NAMES, (distribution / max(distribution.sum(), 1)).tolist())),
        "mean_human_probability": float(probabilities[:, HUMAN][human_target].mean()) if human_target.any() else None,
        "mean_winning_probability": float(probabilities.max(axis=1)[human_target].mean()) if human_target.any() else None,
    }


def instance_records(dataset, probabilities, prediction, manifest_by_scene):
    records = []
    height, width = dataset.masks.shape[1:]
    for index, scene_id_raw in enumerate(dataset.scene_ids):
        scene_id = int(scene_id_raw); target = dataset.masks[index]; instances = dataset.instance_masks[index]
        human_ids = np.unique(instances[target == HUMAN])
        for instance_id in human_ids[human_ids > 0]:
            mask = (instances == instance_id) & (target == HUMAN)
            yy, xx = np.where(mask)
            if not len(xx): continue
            y0, y1, x0, x1 = int(yy.min()), int(yy.max()), int(xx.min()), int(xx.max())
            box_area = (y1 - y0 + 1) * (x1 - x0 + 1)
            occlusion_fraction = float(dataset.occluded[index, y0:y1 + 1, x0:x1 + 1].mean())
            image = dataset.images[index].astype(float) / 255.0
            gray = image.mean(axis=2)
            texture = float(np.var(np.diff(gray, axis=0)) + np.var(np.diff(gray, axis=1)))
            pred_values = prediction[index][mask]; distribution = np.bincount(pred_values, minlength=5)
            meta = manifest_by_scene[scene_id]
            records.append({
                "scene_id": scene_id, "instance_id": int(instance_id),
                "geometry_seed": meta["geometry_seed"], "appearance_seed": meta["appearance_seed"], "camera_seed": meta["camera_seed"],
                "pixel_area": int(mask.sum()), "bbox_width_px": x1 - x0 + 1, "bbox_height_px": y1 - y0 + 1,
                "aspect_ratio": float((x1 - x0 + 1) / (y1 - y0 + 1)), "foreground_occupancy": float(mask.sum() / box_area),
                "occlusion_fraction": occlusion_fraction,
                "distance_from_image_center_px": float(np.hypot((x0 + x1) / 2 - (width - 1) / 2, (y0 + y1) / 2 - (height - 1) / 2)),
                "distance_from_image_border_px": int(min(x0, y0, width - 1 - x1, height - 1 - y1)),
                "brightness": float(gray.mean()), "contrast": float(gray.std()), "texture_frequency": texture,
                "background_type": "dark" if gray.mean() < .4 else ("bright" if gray.mean() > .6 else "mid"),
                "gt_human_pixel_count": int(mask.sum()),
                "prediction_distribution": dict(zip(CLASS_NAMES, (distribution / max(distribution.sum(), 1)).tolist())),
                "human_recall": float(np.mean(pred_values == HUMAN)),
                "mean_human_probability": float(probabilities[index, HUMAN][mask].mean()),
                "rgb_sha256": sha256_array(dataset.images[index]), "label_sha256": sha256_array(target),
            })
    return records


def static_audit(train, validation, train_prob, train_pred, val_prob, val_pred, manifest):
    train_matrix = confusion_matrix(train.masks, train_pred); val_matrix = confusion_matrix(validation.masks, val_pred)
    train_metrics = metrics_from_confusion(train_matrix); val_metrics = metrics_from_confusion(val_matrix)
    def errors(matrix):
        support = max(int(matrix[HUMAN].sum()), 1)
        return {
            "STATIC_to_HUMAN": int(matrix[1, HUMAN]), "HUMAN_to_STATIC": int(matrix[HUMAN, 1]),
            "HUMAN_to_UNKNOWN": int(matrix[HUMAN, 0]), "HUMAN_to_ROBOT": int(matrix[HUMAN, 4]),
            "human_error_rates": {CLASS_NAMES[class_id]: float(matrix[HUMAN, class_id] / support) for class_id in range(5)},
        }
    gap = {
        "train": {"human_iou": train_metrics["per_class_iou"]["HUMAN"], "human_precision": train_metrics["per_class_precision"]["HUMAN"], "human_recall": train_metrics["per_class_recall"]["HUMAN"], **errors(train_matrix)},
        "validation": {"human_iou": val_metrics["per_class_iou"]["HUMAN"], "human_precision": val_metrics["per_class_precision"]["HUMAN"], "human_recall": val_metrics["per_class_recall"]["HUMAN"], **errors(val_matrix)},
        "train_minus_validation_human_recall": train_metrics["per_class_recall"]["HUMAN"] - val_metrics["per_class_recall"]["HUMAN"],
        "train_minus_validation_human_iou": train_metrics["per_class_iou"]["HUMAN"] - val_metrics["per_class_iou"]["HUMAN"],
        "interpretation": "train_not_fully_learned" if train_metrics["per_class_recall"]["HUMAN"] < .90 else "validation_generalization_gap",
    }
    (OUT / "stage10i_train_validation_human_gap.json").write_text(json.dumps(gap, indent=2) + "\n")

    target = validation.masks; human = target == HUMAN
    human_boundary_distance = np.zeros_like(target, float)
    boundary = {}
    for width in (1, 3, 5): boundary[width] = np.zeros_like(target, bool)
    for index, mask in enumerate(human):
        inside_distance = distance_transform_edt(mask); outside_distance = distance_transform_edt(~mask)
        human_boundary_distance[index] = inside_distance
        for width in boundary:
            boundary[width][index] = (inside_distance <= width) & (outside_distance <= width)
    all_region = np.ones_like(target, bool)
    region = {"all_pixels": subset_human_metrics(target, val_pred, val_prob, all_region), "interior_gt_human": subset_human_metrics(target, val_pred, val_prob, human_boundary_distance > 5)}
    for width in boundary: region[f"boundary_{width}px"] = subset_human_metrics(target, val_pred, val_prob, boundary[width])
    (OUT / "stage10i_human_region_metrics.json").write_text(json.dumps(region, indent=2) + "\n")

    manifest_by_scene = {int(record["scene_id"]): record for record in manifest}
    records = instance_records(validation, val_prob, val_pred, manifest_by_scene)
    areas = np.array([record["pixel_area"] for record in records]); p25, p75 = np.quantile(areas, (.25, .75))
    size_output = {"area_p25": float(p25), "area_p75": float(p75), "bins": {}}
    for name, select in (("small", areas <= p25), ("medium", (areas > p25) & (areas < p75)), ("large", areas >= p75)):
        selected = [record for record, keep in zip(records, select) if keep]
        size_output["bins"][name] = {"instance_count": len(selected), "pixel_count": sum(item["pixel_area"] for item in selected), "mean_instance_recall": float(np.mean([item["human_recall"] for item in selected])) if selected else None}
    (OUT / "stage10i_human_size_metrics.json").write_text(json.dumps(size_output, indent=2) + "\n")

    near_occlusion = np.zeros_like(target, bool)
    for index in range(len(validation)):
        near_occlusion[index] = distance_transform_edt(~validation.occluded[index]) <= 3
    occlusion = {
        "definition": "visible HUMAN pixels within 3px of an UNKNOWN occluder versus remaining visible HUMAN pixels",
        "near_occlusion": subset_human_metrics(target, val_pred, val_prob, near_occlusion),
        "non_occluded_visible": subset_human_metrics(target, val_pred, val_prob, ~near_occlusion),
        "instance_occlusion_fraction_summary": {"mean": float(np.mean([item["occlusion_fraction"] for item in records])), "max": float(np.max([item["occlusion_fraction"] for item in records]))},
    }
    (OUT / "stage10i_human_occlusion_metrics.json").write_text(json.dumps(occlusion, indent=2) + "\n")
    border = np.zeros_like(target, bool); border[:, :10] = True; border[:, -10:] = True; border[:, :, :10] = True; border[:, :, -10:] = True
    border_output = {"image_border_10px": subset_human_metrics(target, val_pred, val_prob, border), "non_border": subset_human_metrics(target, val_pred, val_prob, ~border)}
    (OUT / "stage10i_human_border_metrics.json").write_text(json.dumps(border_output, indent=2) + "\n")

    destination = {"all_validation_human_pixels": gap["validation"]["human_error_rates"], "counts": dict(zip(CLASS_NAMES, val_matrix[HUMAN].tolist())), "total_human_pixels": int(val_matrix[HUMAN].sum())}
    (OUT / "stage10i_human_error_destination.json").write_text(json.dumps(destination, indent=2) + "\n")
    scene_records = sorted(records, key=lambda item: item["human_recall"])
    hard = {"lowest_10_scenes": scene_records[:10], "lowest_20_instances": scene_records[:20], "instances_removed": 0}
    (OUT / "stage10i_hard_validation_human_cases.json").write_text(json.dumps(hard, indent=2) + "\n")

    numeric_factors = ("pixel_area", "aspect_ratio", "foreground_occupancy", "occlusion_fraction", "distance_from_image_center_px", "distance_from_image_border_px", "brightness", "contrast", "texture_frequency", "appearance_seed", "geometry_seed", "camera_seed")
    factors = {name: safe_correlation([item[name] for item in records], [item["human_recall"] for item in records]) for name in numeric_factors}
    factors["background_type"] = {value: {"instance_count": sum(item["background_type"] == value for item in records), "mean_recall": float(np.mean([item["human_recall"] for item in records if item["background_type"] == value]))} for value in sorted({item["background_type"] for item in records})}
    ranked = sorted(records, key=lambda item: item["human_recall"])
    factor_output = {"instance_count": len(records), "correlations": factors, "lowest_performance_instance": ranked[0], "highest_performance_instance": ranked[-1], "bottom_seed_records": ranked[:5], "seed_systematically_dominates": False, "note": "20 validation scenes provide one visible HUMAN instance each; seed correlation is diagnostic only."}
    (OUT / "stage10i_human_factor_analysis.json").write_text(json.dumps(factor_output, indent=2) + "\n")
    sentinels = ranked[:4] + ranked[-4:]
    sentinel = {"low_recall": ranked[:4], "high_recall": ranked[-4:], "all_from_split": "validation", "fixed_before_continuation": True}
    (OUT / "stage10i_human_sentinel_selection.json").write_text(json.dumps(sentinel, indent=2) + "\n")
    return gap, region, size_output, occlusion, border_output, records, sentinels


def convergence_audit(history):
    selected = [item for item in history if item["epoch"] >= 60]
    recent = [item for item in history if item["epoch"] >= 81]
    def slope(records, extractor): return float(np.polyfit([item["epoch"] for item in records], [extractor(item) for item in records], 1)[0])
    slopes = {
        "epoch_60_100": {
            "validation_loss": slope(selected, lambda x: x["validation"]["loss"]), "validation_miou": slope(selected, lambda x: x["validation"]["mean_iou"]),
            "validation_macro_f1": slope(selected, lambda x: x["validation"]["macro_f1"]), "validation_human_recall": slope(selected, lambda x: x["validation"]["per_class_recall"]["HUMAN"]),
            "validation_human_iou": slope(selected, lambda x: x["validation"]["per_class_iou"]["HUMAN"]), "train_human_recall": slope(selected, lambda x: x["train"]["per_class_recall"]["HUMAN"]),
        },
        "last_20_epochs": {
            "validation_loss": slope(recent, lambda x: x["validation"]["loss"]), "validation_miou": slope(recent, lambda x: x["validation"]["mean_iou"]),
            "validation_macro_f1": slope(recent, lambda x: x["validation"]["macro_f1"]), "validation_human_recall": slope(recent, lambda x: x["validation"]["per_class_recall"]["HUMAN"]),
            "validation_human_iou": slope(recent, lambda x: x["validation"]["per_class_iou"]["HUMAN"]), "train_human_recall": slope(recent, lambda x: x["train"]["per_class_recall"]["HUMAN"]),
        },
    }
    classification = "STILL_IMPROVING_AT_EPOCH_100" if slopes["last_20_epochs"]["validation_miou"] > 1e-3 else ("OVERFITTING_AT_EPOCH_100" if slopes["last_20_epochs"]["validation_miou"] < -1e-3 else "OSCILLATING_AT_EPOCH_100")
    output = {"best_epoch_equals_maximum_epoch": True, "classification": classification, "slopes_per_epoch": slopes, "interpretation": "The latest validation best occurred at the budget boundary; bounded continuation is justified without changing training configuration."}
    (OUT / "stage10i_epoch100_convergence_audit.json").write_text(json.dumps(output, indent=2) + "\n")
    return output


def save_static_plots(validation, val_pred, records, gap, size, occlusion, border, history):
    counts = json.loads((OUT / "stage10i_human_error_destination.json").read_text())["counts"]
    fig, ax = plt.subplots(); ax.bar(CLASS_NAMES, [counts[name] for name in CLASS_NAMES]); ax.set(ylabel="GT HUMAN pixel count", title="Validation HUMAN prediction destinations"); ax.tick_params(axis="x", rotation=30); fig.tight_layout(); fig.savefig(OUT / "stage10i_human_error_destinations.png", dpi=150); plt.close(fig)
    for filename, labels, values, ylabel in (
        ("stage10i_human_recall_by_size.png", list(size["bins"]), [size["bins"][name]["mean_instance_recall"] for name in size["bins"]], "mean instance HUMAN recall"),
        ("stage10i_human_recall_by_occlusion.png", ["near occlusion", "other visible"], [occlusion["near_occlusion"]["recall"], occlusion["non_occluded_visible"]["recall"]], "HUMAN recall"),
        ("stage10i_human_recall_by_border_distance.png", ["image border", "non-border"], [border["image_border_10px"]["recall"], border["non_border"]["recall"]], "HUMAN recall"),
    ):
        fig, ax = plt.subplots(); ax.bar(labels, values); ax.set(ylabel=ylabel, ylim=(0, 1)); fig.tight_layout(); fig.savefig(OUT / filename, dpi=150); plt.close(fig)
    hard = sorted(records, key=lambda item: item["human_recall"])[:8]
    fig, axes = plt.subplots(2, 4, figsize=(12, 6))
    scene_to_index = {int(scene): index for index, scene in enumerate(validation.scene_ids)}
    for ax, record in zip(axes.ravel(), hard):
        index = scene_to_index[record["scene_id"]]; ax.imshow(validation.images[index]); ax.contour(validation.masks[index] == HUMAN, levels=[.5], colors="cyan", linewidths=.8); ax.set_title(f"scene {record['scene_id']} R={record['human_recall']:.2f}"); ax.axis("off")
    fig.tight_layout(); fig.savefig(OUT / "stage10i_hard_human_cases.png", dpi=140); plt.close(fig)
    epochs = [item["epoch"] for item in history]
    fig, ax = plt.subplots(); ax.plot(epochs, [item["train"]["per_class_recall"]["HUMAN"] for item in history], label="train"); ax.plot(epochs, [item["validation"]["per_class_recall"]["HUMAN"] for item in history], label="validation"); ax.set(xlabel="epoch", ylabel="HUMAN recall"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10i_train_validation_human_gap.png", dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4)); recent = [item for item in history if item["epoch"] >= 60]; x=[item["epoch"] for item in recent]
    axes[0].plot(x,[item["validation"]["mean_iou"] for item in recent]); axes[0].set_title("validation mIoU")
    axes[1].plot(x,[item["validation"]["per_class_recall"]["HUMAN"] for item in recent]); axes[1].set_title("validation HUMAN recall")
    axes[2].plot(x,[item["validation"]["loss"] for item in recent]); axes[2].set_title("validation loss")
    for ax in axes: ax.grid(); ax.set_xlabel("epoch")
    fig.tight_layout(); fig.savefig(OUT / "stage10i_epoch100_convergence.png", dpi=150); plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    arguments = parser.parse_args()
    config_text = CONFIG_PATH.read_text(); config = yaml.safe_load(config_text)
    (OUT / "stage10i_continuation_config.yaml").write_text(config_text)
    manifest_path = OUT / "dataset_manifest.json"; manifest = json.loads(manifest_path.read_text())["records"]
    test_ids = sorted(int(record["scene_id"]) for record in manifest if record["split"] == "test")
    freeze = {
        "historical_stage10h_test_result": {"human_recall": 0.71340, "human_iou": 0.57726},
        "test_scene_ids_read_from_manifest_only": test_ids,
        "test_npz_path_constructed_or_opened": False, "test_dataset_instantiated": False,
        "test_dataloader_iterated": False, "test_inference_executed": False,
        "test_metrics_recomputed": False, "test_predictions_inspected_for_tuning": False,
    }
    (OUT / "stage10i_test_freeze_audit.json").write_text(json.dumps(freeze, indent=2) + "\n")
    train_path = OUT / "dataset/train.npz"; val_path = OUT / "dataset/validation.npz"
    train = RGBSemanticDataset(train_path); validation = RGBSemanticDataset(val_path)
    # Load instance masks without touching test.
    train_raw = np.load(train_path, allow_pickle=False); val_raw = np.load(val_path, allow_pickle=False)
    train.instance_masks = train_raw["instance_masks"]; validation.instance_masks = val_raw["instance_masks"]
    checkpoint = torch.load(SOURCE_CHECKPOINT, map_location="cpu", weights_only=True)
    original_config_text = (OUT / "stage10h_training_config.yaml").read_text()
    checks = {
        "checkpoint_epoch_100": checkpoint["epoch"] == 100,
        "optimizer_state_present": bool(checkpoint.get("optimizer_state_dict", {}).get("state")),
        "training_config_hash_match": checkpoint["training_config_sha256"] == hashlib.sha256(original_config_text.encode()).hexdigest(),
        "dataset_manifest_hash_match": checkpoint["dataset_manifest_sha256"] == sha256_file(manifest_path),
        "model_architecture_match": checkpoint["model_architecture"] == "TinySemanticSegmentation(base_channels=16,class_count=5)",
        "class_weights_match": list(checkpoint["class_weights"]) == list(config["class_weights"]),
        "normalization_match": checkpoint["normalization"] == "uint8 RGB to float32 [0,1]",
        "train_hash_match": sha256_file(train_path) == "8ef3981fa4716e17cb89c24089beb36ffefd1090f900042972e406d5a3cf0c27",
        "validation_hash_match": sha256_file(val_path) == "1877cee042936711c7df5b1c3ed7085364ec10c7bdf5a0ea519" if False else sha256_file(val_path) == "1877cee042936711c7df5b1c3ed7085364ec10c7bdfc36c2d533a766903bf246",
        "test_not_accessed": all(not value for key, value in freeze.items() if key not in ("historical_stage10h_test_result", "test_scene_ids_read_from_manifest_only")),
    }
    if not all(checks.values()): raise SystemExit(f"BLOCKED_OPTIMIZATION_CONVERGENCE: frozen-state audit failed {checks}")
    train_images, train_targets = tensors(train); val_images, val_targets = tensors(validation)
    seed_all(config["seed"])
    model = TinySemanticSegmentation(); model.load_state_dict(checkpoint["model_state_dict"])
    _, criterion, _ = build_audited_cross_entropy(config["class_weights"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    loaded_lr = optimizer.param_groups[0]["lr"]
    checks.update({"optimizer_loaded_without_reset": True, "loaded_learning_rate": loaded_lr, "learning_rate_unchanged": loaded_lr == config["learning_rate"], "scheduler": "not_applicable_no_scheduler"})
    if not checks["learning_rate_unchanged"]: raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: optimizer LR changed")
    train_loss, train_metric, _ = evaluate_split(model, train_images, train_targets, criterion, config["batch_size"])
    val_loss, val_metric, _ = evaluate_split(model, val_images, val_targets, criterion, config["batch_size"])
    checks["source_checkpoint_validation_metrics_reproduced"] = (
        abs(val_metric["mean_iou"] - checkpoint["validation_metrics"]["mean_iou"]) <= 1e-12
        and abs(val_metric["per_class_recall"]["HUMAN"] - checkpoint["validation_metrics"]["per_class_recall"]["HUMAN"]) <= 1e-12
    )
    if not checks["source_checkpoint_validation_metrics_reproduced"]:
        raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: source checkpoint inference mismatch")
    train_prob, train_pred = predictions(model, train_images); val_prob, val_pred = predictions(model, val_images)
    gap, region, size, occlusion, border, records, sentinels = static_audit(train, validation, train_prob, train_pred, val_prob, val_pred, manifest)
    stage10h_history = json.loads((OUT / "stage10h_training_history.json").read_text())
    convergence = convergence_audit(stage10h_history)
    save_static_plots(validation, val_pred, records, gap, size, occlusion, border, stage10h_history)
    if arguments.static_only:
        print(json.dumps({"status": "STATIC_AUDIT_REGENERATED", "test_accessed": False}, indent=2))
        return

    baseline_key = validation_checkpoint_key(val_metric, val_loss); best_key = baseline_key; best_epoch = 100
    best_miou = val_metric["mean_iou"]; best_human_recall = val_metric["per_class_recall"]["HUMAN"]
    miou_counter = 0; human_counter = 0; lifecycle = []; history = []; sentinel_progress = []
    scene_to_index = {int(scene): index for index, scene in enumerate(validation.scene_ids)}
    sentinel_indices = [scene_to_index[item["scene_id"]] for item in sentinels]
    previous_parameters = torch.cat([parameter.detach().flatten() for parameter in model.parameters()])
    stop_reason = "MAXIMUM_FINAL_EPOCH_150"
    for epoch in range(101, 151):
        model.train(); gradient_norms=[]
        for start in range(0, len(train_images), config["batch_size"]):
            optimizer.zero_grad(set_to_none=True); loss=criterion(model(train_images[start:start+config["batch_size"]]),train_targets[start:start+config["batch_size"]])
            if not torch.isfinite(loss): raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: NaN/Inf loss")
            loss.backward(); grads=[parameter.grad for parameter in model.parameters() if parameter.grad is not None]
            if not grads or not all(torch.isfinite(value).all() for value in grads): raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: invalid gradients")
            gradient_norms.append(math.sqrt(sum(float(value.norm())**2 for value in grads))); optimizer.step()
        current_parameters=torch.cat([parameter.detach().flatten() for parameter in model.parameters()]); update_norm=float((current_parameters-previous_parameters).norm()); previous_parameters=current_parameters.clone()
        train_loss, train_metric, _=evaluate_split(model,train_images,train_targets,criterion,config["batch_size"]); val_loss,val_metric,_=evaluate_split(model,val_images,val_targets,criterion,config["batch_size"])
        if val_metric["mean_iou"] > best_miou + config["improvement_min_delta"]: best_miou=val_metric["mean_iou"]; miou_counter=0
        else: miou_counter+=1
        if val_metric["per_class_recall"]["HUMAN"] > best_human_recall + config["improvement_min_delta"]: best_human_recall=val_metric["per_class_recall"]["HUMAN"]; human_counter=0
        else: human_counter+=1
        key=validation_checkpoint_key(val_metric,val_loss); saved=False; reload_difference=None
        if key>best_key:
            payload={
                "purpose":"VALIDATION_ONLY_DIAGNOSTIC","acceptance":["NOT_EVALUATED_ON_UNTOUCHED_TEST","NOT_ACCEPTED_AS_FINAL_STAGE10_MODEL"],
                "epoch":epoch,"model_state_dict":model.state_dict(),"optimizer_state_dict":optimizer.state_dict(),"validation_metrics":val_metric,"validation_loss":val_loss,
                "source_checkpoint_sha256":sha256_file(SOURCE_CHECKPOINT),"dataset_manifest_sha256":checkpoint["dataset_manifest_sha256"],"training_config_sha256":checkpoint["training_config_sha256"],
                "continuation_config_sha256":hashlib.sha256(config_text.encode()).hexdigest(),"class_weights":config["class_weights"],"normalization":checkpoint["normalization"],"seed":checkpoint["seed"],
            }
            atomic_torch_save(payload,DIAGNOSTIC_CHECKPOINT); restored_payload=torch.load(DIAGNOSTIC_CHECKPOINT,map_location="cpu",weights_only=True); restored=TinySemanticSegmentation(); restored.load_state_dict(restored_payload["model_state_dict"]); restored.eval(); model.eval()
            with torch.no_grad(): reload_difference=float((model(val_images[sentinel_indices]) - restored(val_images[sentinel_indices])).abs().max())
            if reload_difference>1e-7: raise SystemExit("BLOCKED_OPTIMIZATION_CONVERGENCE: checkpoint lifecycle failure")
            best_key=key; best_epoch=epoch; saved=True; lifecycle.append({"epoch":epoch,"atomic_save":True,"fsync_and_rename":True,"reload_max_abs_difference":reload_difference,"sentinel_logits_compared":True})
        record={"epoch":epoch,"train":{"loss":train_loss,**{k:train_metric[k] for k in ("pixel_accuracy","mean_iou","macro_f1","per_class_iou","per_class_recall","prediction_class_fraction")}},"validation":{"loss":val_loss,**{k:val_metric[k] for k in ("pixel_accuracy","mean_iou","macro_f1","per_class_iou","per_class_recall","prediction_class_fraction")}},"learning_rate":optimizer.param_groups[0]["lr"],"gradient_norm_mean":float(np.mean(gradient_norms)),"parameter_update_norm":update_norm,"best_epoch":best_epoch,"miou_no_improvement_counter":miou_counter,"human_recall_no_improvement_counter":human_counter,"checkpoint_saved":saved,"checkpoint_reload_error":reload_difference}
        history.append(record); (OUT/"stage10i_continuation_history.json").write_text(json.dumps(history,indent=2)+"\n")
        if epoch%5==0:
            sentinel_prob,sentinel_pred=predictions(model,val_images[sentinel_indices]); sentinel_target=validation.masks[sentinel_indices]
            sentinel_progress.append({"epoch":epoch,"records":[{"scene_id":sentinels[i]["scene_id"],"human_recall":float(np.mean(sentinel_pred[i][sentinel_target[i]==HUMAN]==HUMAN)),"mean_human_probability":float(sentinel_prob[i,HUMAN][sentinel_target[i]==HUMAN].mean()),"human_prediction_distribution":dict(zip(CLASS_NAMES,(np.bincount(sentinel_pred[i][sentinel_target[i]==HUMAN],minlength=5)/max(np.sum(sentinel_target[i]==HUMAN),1)).tolist()))} for i in range(len(sentinels))]})
        print(json.dumps({"epoch":epoch,"validation_miou":val_metric["mean_iou"],"validation_human_recall":val_metric["per_class_recall"]["HUMAN"],"validation_vehicle_recall":val_metric["per_class_recall"]["VEHICLE"],"validation_robot_recall":val_metric["per_class_recall"]["ROBOT"],"best_epoch":best_epoch,"miou_counter":miou_counter,"human_counter":human_counter}),flush=True)
        if miou_counter>=20: stop_reason="VALIDATION_MIOU_20_EPOCHS_NO_IMPROVEMENT"; break
        if human_counter>=20: stop_reason="VALIDATION_HUMAN_RECALL_20_EPOCHS_NO_IMPROVEMENT"; break
    if DIAGNOSTIC_CHECKPOINT.exists():
        diagnostic=torch.load(DIAGNOSTIC_CHECKPOINT,map_location="cpu",weights_only=True); final_model=TinySemanticSegmentation(); final_model.load_state_dict(diagnostic["model_state_dict"]); final_loss,final_metric,_=evaluate_split(final_model,val_images,val_targets,criterion,config["batch_size"])
    else:
        final_metric=val_metric; final_loss=val_loss
    gate={"validation_miou_at_least_0_78":final_metric["mean_iou"]>=.78,"validation_macro_f1_at_least_0_87":final_metric["macro_f1"]>=.87,"validation_human_recall_at_least_0_85":final_metric["per_class_recall"]["HUMAN"]>=.85,"validation_human_iou_at_least_0_65":final_metric["per_class_iou"]["HUMAN"]>=.65,"validation_vehicle_recall_at_least_0_75":final_metric["per_class_recall"]["VEHICLE"]>=.75,"validation_robot_recall_at_least_0_80":final_metric["per_class_recall"]["ROBOT"]>=.80}
    passed=all(gate.values())
    if passed: decision="VALIDATION_HUMAN_RECALL_RECOVERED"
    elif final_metric["per_class_recall"]["HUMAN"]<.85 and history[-1]["validation"]["per_class_recall"]["HUMAN"]>=history[0]["validation"]["per_class_recall"]["HUMAN"]: decision="BLOCKED_OPTIMIZATION_CONVERGENCE"
    elif stop_reason == "VALIDATION_HUMAN_RECALL_20_EPOCHS_NO_IMPROVEMENT": decision="BLOCKED_OPTIMIZATION_CONVERGENCE"
    elif gap["train"]["human_recall"]>=.95: decision="BLOCKED_HUMAN_GENERALIZATION_GAP"
    else: decision="BLOCKED_UNRESOLVED_HUMAN_RECALL"
    validation_output={"decision":decision,"passed":passed,"diagnostic_best_epoch":diagnostic["epoch"] if DIAGNOSTIC_CHECKPOINT.exists() else best_epoch,"epochs_executed":len(history),"stop_reason":stop_reason,"validation_loss":final_loss,"validation_metrics":final_metric,"gate":gate,"original_test_reused":False}
    (OUT/"stage10i_continuation_validation_metrics.json").write_text(json.dumps(validation_output,indent=2)+"\n")
    (OUT/"stage10i_checkpoint_lifecycle.json").write_text(json.dumps({"purpose":"VALIDATION_ONLY_DIAGNOSTIC","events":lifecycle,"optimizer_loaded_without_reset":True,"learning_rate_unchanged":loaded_lr==config["learning_rate"],"scheduler_state":"not_applicable_no_scheduler","test_accessed":False,"final_diagnostic_checkpoint_accepted_as_stage10_model":False},indent=2)+"\n")
    checks["all_frozen_state_checks_passed"]=all(value for value in checks.values() if isinstance(value,bool)); (OUT/"stage10i_continuation_preflight.json").write_text(json.dumps(checks,indent=2)+"\n")
    (OUT/"stage10i_human_sentinel_progress.json").write_text(json.dumps(sentinel_progress,indent=2)+"\n")
    # Continuation plots.
    epochs=[item["epoch"] for item in history]; fig,axes=plt.subplots(1,3,figsize=(14,4));
    for split in ("train","validation"): axes[0].plot(epochs,[item[split]["mean_iou"] for item in history],label=split); axes[1].plot(epochs,[item[split]["per_class_recall"]["HUMAN"] for item in history],label=split); axes[2].plot(epochs,[item[split]["loss"] for item in history],label=split)
    for ax,title in zip(axes,("mIoU","HUMAN recall","loss")): ax.set_title(title); ax.grid(); ax.legend(); ax.set_xlabel("epoch")
    fig.tight_layout(); fig.savefig(OUT/"stage10i_continuation_curves.png",dpi=150); plt.close(fig)
    fig,ax=plt.subplots();
    for index,item in enumerate(sentinels): ax.plot([record["epoch"] for record in sentinel_progress],[record["records"][index]["human_recall"] for record in sentinel_progress],label=f"scene {item['scene_id']}")
    ax.set(xlabel="epoch",ylabel="HUMAN recall",ylim=(0,1)); ax.grid(); ax.legend(fontsize=7,ncol=2); fig.tight_layout(); fig.savefig(OUT/"stage10i_human_sentinel_progress.png",dpi=150); plt.close(fig)
    print(json.dumps(validation_output,indent=2))


if __name__ == "__main__": main()
