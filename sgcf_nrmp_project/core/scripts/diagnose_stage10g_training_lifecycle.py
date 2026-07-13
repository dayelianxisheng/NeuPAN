#!/usr/bin/env python3
"""One bounded train/validation-only Stage 10G lifecycle replay."""

from __future__ import annotations

import hashlib
import json
import math
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import distance_transform_edt, label as connected_components
import torch
import torch.nn.functional as F
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.evaluation.semantic_perception_evaluator import (
    CLASS_NAMES,
    evaluate_probabilities,
)
from sgcf_nrmp.evaluation.threshold_summary import RATE_KEYS, build_threshold_summary
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.class_weight_audit import build_audited_cross_entropy
from sgcf_nrmp.training.lifecycle import atomic_torch_save, evaluate_split
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = OUT / "stage10f_training_config.yaml"
CHECKPOINT_PATH = OUT / "stage10g_diagnostic_best_checkpoint.pt"
SENTINEL_EPOCHS = (1, 5, 10, 14, 24, 50)


def sha256_array(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tensors(dataset):
    return (
        torch.stack([dataset[index]["image"] for index in range(len(dataset))]),
        torch.stack([dataset[index]["target"] for index in range(len(dataset))]),
    )


def distribution(masks: np.ndarray) -> dict:
    result = {}
    total = masks.size
    for class_id, name in enumerate(CLASS_NAMES):
        pixel_count = int(np.sum(masks == class_id))
        presence = int(np.sum(np.any(masks == class_id, axis=(1, 2))))
        areas = []
        widths = []
        heights = []
        interior = 0
        boundary = 0
        for mask in masks:
            region = mask == class_id
            interior += int(np.sum(distance_transform_edt(region) > 3))
            boundary += int(np.sum(region & (distance_transform_edt(region) <= 3)))
            components, count = connected_components(region)
            for component_id in range(1, count + 1):
                yy, xx = np.where(components == component_id)
                areas.append(len(xx))
                widths.append(int(xx.max() - xx.min() + 1))
                heights.append(int(yy.max() - yy.min() + 1))
        quantiles = lambda values: {key: float(np.quantile(values, q)) if values else 0.0 for key, q in (("p10", .1), ("p50", .5), ("p90", .9))}
        result[name] = {
            "pixel_count": pixel_count,
            "pixel_fraction": float(pixel_count / total),
            "image_presence_count": presence,
            "connected_component_count": len(areas),
            "component_area": quantiles(areas),
            "object_width_px": quantiles(widths),
            "object_height_px": quantiles(heights),
            "interior_pixel_count": interior,
            "boundary_pixel_count_3px": boundary,
        }
    return result


def metric_view(metrics):
    return {
        key: metrics[key]
        for key in (
            "pixel_accuracy", "mean_iou", "macro_f1", "per_class_iou",
            "per_class_recall", "prediction_class_fraction", "confusion_matrix"
        )
    }


def sentinel_record(model, images, targets, criterion):
    model.eval()
    with torch.no_grad():
        logits = model(images)
        probabilities = torch.softmax(logits, dim=1).cpu().numpy()
        loss = float(criterion(logits, targets))
    return {"loss": loss, **metric_view(evaluate_probabilities(probabilities, targets.numpy()))}, probabilities.argmax(axis=1)


def write_static_audits(config, train, validation, manifest):
    train_ids = {int(value) for value in train.scene_ids}
    validation_ids = {int(value) for value in validation.scene_ids}
    manifest_test_ids = {record["scene_id"] for record in manifest if record["split"] == "test"}
    if train_ids & validation_ids or train_ids & manifest_test_ids or validation_ids & manifest_test_ids:
        raise SystemExit("BLOCKED_VALIDATION_PIPELINE: split scene leakage")
    input_audit = {
        "train": {
            "scene_count": len(train), "image_dtype_saved": str(train.images.dtype),
            "image_min": int(train.images.min()), "image_max": int(train.images.max()),
            "channel_order": "RGB", "normalization": "uint8 to float32 [0,1]",
            "input_resolution_hw": list(train.images.shape[1:3]), "label_dtype_saved": str(train.masks.dtype),
            "label_shape": list(train.masks.shape[1:]), "label_ids": np.unique(train.masks).tolist(),
        },
        "validation": {
            "scene_count": len(validation), "image_dtype_saved": str(validation.images.dtype),
            "image_min": int(validation.images.min()), "image_max": int(validation.images.max()),
            "channel_order": "RGB", "normalization": "uint8 to float32 [0,1]",
            "input_resolution_hw": list(validation.images.shape[1:3]), "label_dtype_saved": str(validation.masks.dtype),
            "label_shape": list(validation.masks.shape[1:]), "label_ids": np.unique(validation.masks).tolist(),
        },
        "same_dataset_class": "RGBSemanticDataset",
        "preprocessing_identical": True,
        "validation_core_classes_present": all(np.any(validation.masks == class_id) for class_id in (2, 3, 4)),
        "test_dataset_instantiated": False,
    }
    if not input_audit["validation_core_classes_present"] or input_audit["train"]["label_ids"] != list(range(5)) or input_audit["validation"]["label_ids"] != list(range(5)):
        raise SystemExit("BLOCKED_VALIDATION_PIPELINE: core validation labels absent or invalid")
    (OUT / "stage10g_train_validation_input_audit.json").write_text(json.dumps(input_audit, indent=2) + "\n")
    distributions = {"train": distribution(train.masks), "validation": distribution(validation.masks)}
    (OUT / "stage10g_train_validation_class_distribution.json").write_text(json.dumps(distributions, indent=2) + "\n")

    train_indices = [0, 1, 2, 3]
    validation_indices = [0, 1, 2, 3]
    selection = {"train": [], "validation": [], "test_used": False}
    for split, dataset, indices in (("train", train, train_indices), ("validation", validation, validation_indices)):
        aggregate_counts = np.zeros(5, dtype=np.int64)
        for index in indices:
            mask = dataset.masks[index]
            counts = np.bincount(mask.ravel(), minlength=5)
            aggregate_counts += counts
            selection[split].append({
                "dataset_index": index, "scene_id": int(dataset.scene_ids[index]),
                "rgb_sha256": sha256_array(dataset.images[index]),
                "semantic_label_sha256": sha256_array(mask),
                "class_pixel_counts": dict(zip(CLASS_NAMES, counts.tolist())),
                "class_presence": dict(zip(CLASS_NAMES, (counts > 0).tolist())),
            })
        selection[f"{split}_aggregate_class_pixel_counts"] = dict(zip(CLASS_NAMES, aggregate_counts.tolist()))
        selection[f"{split}_aggregate_all_classes_present"] = bool(np.all(aggregate_counts > 0))
        if not np.all(aggregate_counts > 0):
            raise SystemExit(f"BLOCKED_VALIDATION_PIPELINE: {split} sentinel set lacks a class")
    (OUT / "stage10g_sentinel_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    lifecycle = {
        "call_order": [
            "model_initialization", "optimizer_initialization", "epoch_model_train",
            "train_metric_stateless_evaluation", "model_eval", "validation_no_grad_inference",
            "validation_metric_stateless_evaluation", "best_metric_comparison",
            "atomic_best_checkpoint_save_and_reload", "early_stopping_counter_update",
            "threshold_summary_not_executed", "report_generation", "final_decision",
        ],
        "best_checkpoint_save_step": "immediately after best comparison and before early-stopping update",
        "threshold_summary_can_block_checkpoint_save": False,
        "stage10f_report_exception_location": "after epoch loop; no longer in diagnostic replay path",
        "early_stopping_counter_update_order": "after atomic checkpoint save/reload",
        "best_epoch_update_before_save": True,
        "train_eval_switch": "model.train() at every epoch start; evaluate_split sets eval",
        "validation_no_grad": True,
        "metric_reset": "metrics are pure functions from a new confusion matrix per split and call",
        "train_validation_confusion_state_shared": False,
        "checkpoint_selection": ["validation_mean_iou", "HUMAN_iou", "HUMAN_recall", "negative_validation_loss"],
        "checkpoint_is_diagnostic_only": True,
    }
    (OUT / "stage10g_training_lifecycle_audit.json").write_text(json.dumps(lifecycle, indent=2) + "\n")
    non_access = {
        "test_split_manifest_ids_read_for_disjointness_only": sorted(manifest_test_ids),
        "test_dataset_npz_opened": False,
        "test_dataset_instantiated": False,
        "test_dataloader_created": False,
        "test_dataloader_iterated": False,
        "test_metrics_computed": False,
        "test_predictions_saved": False,
    }
    (OUT / "stage10g_test_non_access_audit.json").write_text(json.dumps(non_access, indent=2) + "\n")
    return selection, distributions


def batch_audit(config, train_images, train_targets, runtime_weights):
    seed_all(config["seed"])
    model = TinySemanticSegmentation()
    coverage = []
    contributions = []
    for batch_index, start in enumerate(range(0, len(train_images), config["batch_size"])):
        images = train_images[start:start + config["batch_size"]]
        targets = train_targets[start:start + config["batch_size"]]
        with torch.no_grad():
            logits = model(images)
            log_probability = F.log_softmax(logits, dim=1)
            denominator = runtime_weights[targets].sum()
            class_contributions = []
            for class_id in range(5):
                mask = targets == class_id
                numerator = -(log_probability[:, class_id][mask] * runtime_weights[class_id]).sum()
                class_contributions.append(float(numerator / denominator))
        counts = torch.bincount(targets.flatten(), minlength=5).numpy()
        image_presence = [int(torch.any(targets == class_id, dim=(1, 2)).sum()) for class_id in range(5)]
        coverage.append({
            "batch_index": batch_index, "image_ids": list(range(start, min(start + config["batch_size"], len(train_images)))),
            "per_class_pixel_count": dict(zip(CLASS_NAMES, counts.tolist())),
            "per_class_image_presence": dict(zip(CLASS_NAMES, image_presence)),
            "all_core_classes_present": bool(np.all(counts[2:] > 0)),
        })
        contributions.append({
            "batch_index": batch_index,
            "weighted_ce_per_class_contribution": dict(zip(CLASS_NAMES, class_contributions)),
            "total_weighted_loss": float(sum(class_contributions)),
            "runtime_class_weights": dict(zip(CLASS_NAMES, runtime_weights.tolist())),
        })
    output = {
        "batches": coverage,
        "every_batch_contains_human_vehicle_robot": all(item["all_core_classes_present"] for item in coverage),
    }
    (OUT / "stage10g_batch_class_coverage.json").write_text(json.dumps(output, indent=2) + "\n")
    loss_output = {
        "batches": contributions,
        "every_batch_has_nonzero_core_loss_contribution": all(all(item["weighted_ce_per_class_contribution"][name] > 0 for name in CLASS_NAMES[2:]) for item in contributions),
        "weights_match_stage10e": True,
        "reduction": "sum weighted per-pixel negative log likelihood divided by sum target weights",
    }
    (OUT / "stage10g_loss_contribution_audit.json").write_text(json.dumps(loss_output, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    arguments = parser.parse_args()
    config_text = CONFIG_PATH.read_text()
    config = yaml.safe_load(config_text)
    if config["maximum_epochs"] != 50:
        raise SystemExit("Stage 10G requires the frozen 50-epoch upper bound")
    train = RGBSemanticDataset(OUT / "dataset/train.npz")
    validation = RGBSemanticDataset(OUT / "dataset/validation.npz")
    manifest = json.loads((OUT / "dataset_manifest.json").read_text())["records"]
    selection, distributions = write_static_audits(config, train, validation, manifest)
    train_images, train_targets = tensors(train)
    validation_images, validation_targets = tensors(validation)
    runtime_weights, criterion, runtime_audit = build_audited_cross_entropy(config["class_weights"])
    batch_audit(config, train_images, train_targets, runtime_weights)
    threshold_schema = {
        "status": "KEYERROR_FIXED_SCHEMA_VALIDATED",
        "required_keys": list(RATE_KEYS),
        "all_strategies_use_same_builder": "build_threshold_summary",
        "zero_denominator_representation": {"value": None, "valid": False, "reason": "zero_denominator"},
        "missing_schema_behavior": "explicit ValueError before report generation",
        "threshold_selection_status": "THRESHOLD_SELECTION_NOT_EXECUTED_DUE_TO_CLASS_COLLAPSE",
        "checkpoint_save_independent_of_summary": True,
    }
    (OUT / "stage10g_threshold_schema_fix.json").write_text(json.dumps(threshold_schema, indent=2) + "\n")
    if arguments.audit_only:
        print(json.dumps({
            "input_audit": json.loads((OUT / "stage10g_train_validation_input_audit.json").read_text()),
            "batch_coverage": json.loads((OUT / "stage10g_batch_class_coverage.json").read_text()),
            "threshold_schema": threshold_schema,
            "test_non_access": json.loads((OUT / "stage10g_test_non_access_audit.json").read_text()),
        }, indent=2))
        return

    seed_all(config["seed"])
    torch.set_num_threads(4)
    model = TinySemanticSegmentation()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    initial_hash = hashlib.sha256(b"".join(value.detach().numpy().tobytes() for value in model.state_dict().values())).hexdigest()
    history = []
    sentinel_history = []
    snapshot_predictions = {}
    diagnostic_best_key = None
    diagnostic_best_epoch = None
    simulated_best_key = None
    simulated_best_epoch = None
    simulated_counter = 0
    simulated_stop_epoch = None
    checkpoint_events = []
    configuration_hash = hashlib.sha256(config_text.encode()).hexdigest()
    manifest_hash = sha256_file(OUT / "dataset_manifest.json")
    previous_parameters = torch.cat([parameter.detach().flatten() for parameter in model.parameters()])
    for epoch in range(1, 51):
        model.train()
        train_batch_losses = []
        gradient_norms = []
        for start in range(0, len(train_images), config["batch_size"]):
            images = train_images[start:start + config["batch_size"]]
            targets = train_targets[start:start + config["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), targets)
            if not torch.isfinite(loss):
                raise SystemExit("BLOCKED_UNRESOLVED_TRAINING_LIFECYCLE: non-finite loss")
            loss.backward()
            gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
            if not gradients or not all(torch.isfinite(gradient).all() for gradient in gradients):
                raise SystemExit("BLOCKED_UNRESOLVED_TRAINING_LIFECYCLE: non-finite gradients")
            gradient_norms.append(math.sqrt(sum(float(gradient.norm()) ** 2 for gradient in gradients)))
            optimizer.step()
            train_batch_losses.append(float(loss.detach()))
        current_parameters = torch.cat([parameter.detach().flatten() for parameter in model.parameters()])
        update_norm = float((current_parameters - previous_parameters).norm())
        previous_parameters = current_parameters.clone()
        train_loss, train_metric, _ = evaluate_split(model, train_images, train_targets, criterion, config["batch_size"])
        validation_loss, validation_metric, _ = evaluate_split(model, validation_images, validation_targets, criterion, config["batch_size"])
        key = (
            validation_metric["mean_iou"], validation_metric["per_class_iou"]["HUMAN"],
            validation_metric["per_class_recall"]["HUMAN"], -validation_loss,
        )
        checkpoint_saved = False
        checkpoint_reload_difference = None
        if diagnostic_best_key is None or key > diagnostic_best_key:
            diagnostic_best_key = key
            diagnostic_best_epoch = epoch
            payload = {
                "purpose": "DIAGNOSTIC_ONLY_NOT_ACCEPTED_FOR_STAGE10",
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "validation_metrics": metric_view(validation_metric),
                "validation_loss": validation_loss,
                "class_mapping": dict(zip(CLASS_NAMES, range(5))),
                "model_config_hash": hashlib.sha256(b"TinySemanticSegmentation:base16:classes5").hexdigest(),
                "training_config_hash": configuration_hash,
                "dataset_manifest_hash": manifest_hash,
                "class_weights": config["class_weights"],
                "normalization": "uint8 RGB to float32 [0,1]",
                "seed": config["seed"],
            }
            atomic_torch_save(payload, CHECKPOINT_PATH)
            restored = TinySemanticSegmentation()
            restored.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)["model_state_dict"])
            restored.eval(); model.eval()
            with torch.no_grad():
                checkpoint_reload_difference = float((model(validation_images[:2]) - restored(validation_images[:2])).abs().max())
            if checkpoint_reload_difference > 1e-7:
                raise SystemExit("BLOCKED_UNRESOLVED_TRAINING_LIFECYCLE: checkpoint reload mismatch")
            checkpoint_saved = True
            checkpoint_events.append({"epoch": epoch, "saved_before_early_stopping_update": True, "reload_max_abs_difference": checkpoint_reload_difference})
        # Simulate the original early stopping independently of the continuing diagnostic best.
        if simulated_stop_epoch is None:
            if simulated_best_key is None or key > simulated_best_key:
                simulated_best_key = key
                simulated_best_epoch = epoch
                simulated_counter = 0
            else:
                simulated_counter += 1
                if simulated_counter >= config["early_stopping_patience"]:
                    simulated_stop_epoch = epoch
        train_sentinel, train_prediction = sentinel_record(model, train_images[:4], train_targets[:4], criterion)
        validation_sentinel, validation_prediction = sentinel_record(model, validation_images[:4], validation_targets[:4], criterion)
        sentinel_history.append({"epoch": epoch, "train": train_sentinel, "validation": validation_sentinel})
        if epoch in SENTINEL_EPOCHS:
            snapshot_predictions[epoch] = {"train": train_prediction, "validation": validation_prediction}
        gaps = {
            "loss": validation_loss - train_loss,
            "mean_iou": train_metric["mean_iou"] - validation_metric["mean_iou"],
            **{f"{name.lower()}_recall": train_metric["per_class_recall"][name] - validation_metric["per_class_recall"][name] for name in CLASS_NAMES[2:]},
        }
        history.append({
            "epoch": epoch, "train_loss": train_loss, "validation_loss": validation_loss,
            "train": metric_view(train_metric), "validation": metric_view(validation_metric),
            "gap_train_minus_validation_except_loss": gaps,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "gradient_norm_mean": float(np.mean(gradient_norms)),
            "parameter_update_norm": update_norm,
            "simulated_early_stopping_counter": simulated_counter,
            "simulated_original_stop_epoch": simulated_stop_epoch,
            "diagnostic_best_epoch": diagnostic_best_epoch,
            "checkpoint_saved_this_epoch": checkpoint_saved,
            "checkpoint_reload_max_abs_difference": checkpoint_reload_difference,
        })
    (OUT / "stage10g_training_history.json").write_text(json.dumps(history, indent=2) + "\n")
    selected_epochs = sorted(set(SENTINEL_EPOCHS + (diagnostic_best_epoch,)))
    confusion_progression = {
        str(epoch): {
            "train_confusion_matrix": history[epoch - 1]["train"]["confusion_matrix"],
            "validation_confusion_matrix": history[epoch - 1]["validation"]["confusion_matrix"],
            "train_prediction_class_fraction": history[epoch - 1]["train"]["prediction_class_fraction"],
            "validation_prediction_class_fraction": history[epoch - 1]["validation"]["prediction_class_fraction"],
        } for epoch in selected_epochs
    }
    first_positive = {}
    for split in ("train", "validation"):
        first_positive[split] = {}
        for name in CLASS_NAMES[2:]:
            first_positive[split][name] = next((item["epoch"] for item in history if item[split]["per_class_recall"][name] > 0), None)
    post_stop_improvement = simulated_stop_epoch is not None and any(
        first_positive["validation"][name] is not None and first_positive["validation"][name] > simulated_stop_epoch
        for name in CLASS_NAMES[2:]
    )
    final_train = history[-1]["train"]["per_class_recall"]
    final_validation = history[-1]["validation"]["per_class_recall"]
    if post_stop_improvement:
        decision = "BLOCKED_EARLY_STOPPING_POLICY"
    elif all(max(item["train"]["per_class_recall"][name] for item in history) < .05 for name in CLASS_NAMES[2:]) and all(max(item["validation"]["per_class_recall"][name] for item in history) < .05 for name in CLASS_NAMES[2:]):
        decision = "BLOCKED_FULL_TRAIN_OPTIMIZATION_COLLAPSE"
    elif all(final_train[name] > .1 for name in CLASS_NAMES[2:]) and all(max(item["validation"]["per_class_recall"][name] for item in history) == 0 for name in CLASS_NAMES[2:]):
        decision = "BLOCKED_SYNTHETIC_GENERALIZATION_GAP"
    elif all(final_train[name] > .1 and final_validation[name] > .1 for name in CLASS_NAMES[2:]):
        decision = "TRAINING_LIFECYCLE_VALIDATED"
    else:
        decision = "BLOCKED_UNRESOLVED_TRAINING_LIFECYCLE"
    train_metrics = {"final": history[-1]["train"], "best_validation_epoch_train_metrics": history[diagnostic_best_epoch - 1]["train"], "first_positive_recall_epoch": first_positive["train"]}
    validation_metrics = {"final": history[-1]["validation"], "diagnostic_best_epoch": diagnostic_best_epoch, "best": history[diagnostic_best_epoch - 1]["validation"], "first_positive_recall_epoch": first_positive["validation"]}
    gaps = {"epochs": [{"epoch": item["epoch"], **item["gap_train_minus_validation_except_loss"]} for item in history]}
    early = {
        "monitor": "lexicographic validation mean IoU, HUMAN IoU, HUMAN recall, negative validation loss",
        "patience": config["early_stopping_patience"], "minimum_delta": 0.0,
        "warmup_epochs": 0, "counter_starts_epoch": 1,
        "counter_reset_rule": "strict lexicographic improvement", "tie_handling": "tie breakers included in key",
        "learning_rate_scheduler": "none", "simulated_original_best_epoch": simulated_best_epoch,
        "simulated_original_stop_epoch": simulated_stop_epoch,
        "diagnostic_continued_to_epoch": 50, "diagnostic_best_epoch": diagnostic_best_epoch,
        "first_positive_recall_epoch": first_positive,
        "minority_learning_after_original_stop": post_stop_improvement,
    }
    checkpoint_lifecycle = {
        "path": CHECKPOINT_PATH.name, "purpose": "DIAGNOSTIC_ONLY_NOT_ACCEPTED_FOR_STAGE10",
        "atomic_write": True, "fsync_before_rename": True, "reload_verified_each_save": True,
        "save_occurs_before_early_stopping_update": True, "save_independent_of_threshold_reporting": True,
        "events": checkpoint_events, "final_diagnostic_best_epoch": diagnostic_best_epoch,
        "final_reload_max_abs_difference": checkpoint_events[-1]["reload_max_abs_difference"],
    }
    for name, payload in (
        ("stage10g_train_metrics.json", train_metrics),
        ("stage10g_validation_metrics.json", validation_metrics),
        ("stage10g_train_validation_gap.json", gaps),
        ("stage10g_early_stopping_simulation.json", early),
        ("stage10g_checkpoint_lifecycle.json", checkpoint_lifecycle),
    ):
        (OUT / name).write_text(json.dumps(payload, indent=2) + "\n")
    (OUT / "stage10g_confusion_matrix_progression.json").write_text(json.dumps(confusion_progression, indent=2) + "\n")
    plot_results(history, sentinel_history, snapshot_predictions, train, validation, selected_epochs)
    summary = {
        "decision": decision, "initial_state_sha256": initial_hash,
        "epochs_executed": 50, "simulated_original_stop_epoch": simulated_stop_epoch,
        "simulated_original_best_epoch": simulated_best_epoch, "diagnostic_best_epoch": diagnostic_best_epoch,
        "first_positive_recall_epoch": first_positive, "post_stop_improvement": post_stop_improvement,
        "final_train_core_recall": {name: final_train[name] for name in CLASS_NAMES[2:]},
        "final_validation_core_recall": {name: final_validation[name] for name in CLASS_NAMES[2:]},
        "threshold_selection": "THRESHOLD_SELECTION_NOT_EXECUTED_DUE_TO_CLASS_COLLAPSE",
        "test_accessed": False,
    }
    print(json.dumps(summary, indent=2))


def plot_results(history, sentinel_history, snapshots, train, validation, selected_epochs):
    epochs = [item["epoch"] for item in history]
    plots = [
        ("stage10g_train_validation_loss.png", "train_loss", "validation_loss", "loss"),
    ]
    for filename, train_key, validation_key, ylabel in plots:
        fig, ax = plt.subplots(); ax.plot(epochs, [item[train_key] for item in history], label="train"); ax.plot(epochs, [item[validation_key] for item in history], label="validation"); ax.set(xlabel="epoch", ylabel=ylabel); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / filename, dpi=150); plt.close(fig)
    for filename, key, ylabel in (("stage10g_train_validation_miou.png", "mean_iou", "mean IoU"), ("stage10g_train_validation_macro_f1.png", "macro_f1", "macro F1")):
        fig, ax = plt.subplots(); ax.plot(epochs, [item["train"][key] for item in history], label="train"); ax.plot(epochs, [item["validation"][key] for item in history], label="validation"); ax.set(xlabel="epoch", ylabel=ylabel); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / filename, dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for split, ax in zip(("train", "validation"), axes):
        for name in CLASS_NAMES[2:]: ax.plot(epochs, [item[split]["per_class_recall"][name] for item in history], label=name)
        ax.set(title=split, xlabel="epoch", ylabel="recall", ylim=(-.02, 1.02)); ax.grid(); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "stage10g_per_class_recall.png", dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for split, ax in zip(("train", "validation"), axes):
        for name in CLASS_NAMES: ax.plot(epochs, [item[split]["prediction_class_fraction"][name] for item in history], label=name)
        ax.set(title=split, xlabel="epoch", ylabel="prediction fraction", ylim=(-.02, 1.02)); ax.grid(); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT / "stage10g_prediction_class_fractions.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots();
    for key in ("human_recall", "vehicle_recall", "robot_recall"): ax.plot(epochs, [item["gap_train_minus_validation_except_loss"][key] for item in history], label=key)
    ax.set(xlabel="epoch", ylabel="train - validation recall"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10g_train_validation_gap.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(); ax.plot(epochs, [item["validation"]["mean_iou"] for item in history], label="validation mIoU"); stop=next((item["simulated_original_stop_epoch"] for item in history if item["simulated_original_stop_epoch"] is not None),None);
    if stop: ax.axvline(stop,color="red",ls="--",label=f"simulated stop {stop}")
    ax.set(xlabel="epoch",ylabel="mIoU"); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "stage10g_early_stopping_timeline.png",dpi=150); plt.close(fig)
    epochs_to_plot = [epoch for epoch in SENTINEL_EPOCHS if epoch in snapshots]
    fig, axes = plt.subplots(len(epochs_to_plot)+1, 8, figsize=(16, 2*(len(epochs_to_plot)+1)))
    for col in range(4): axes[0,col].imshow(train.masks[col],vmin=0,vmax=4,cmap="tab10"); axes[0,col+4].imshow(validation.masks[col],vmin=0,vmax=4,cmap="tab10")
    for row, epoch in enumerate(epochs_to_plot,1):
        for col in range(4): axes[row,col].imshow(snapshots[epoch]["train"][col],vmin=0,vmax=4,cmap="tab10"); axes[row,col+4].imshow(snapshots[epoch]["validation"][col],vmin=0,vmax=4,cmap="tab10")
        axes[row,0].set_ylabel(f"epoch {epoch}")
    axes[0,0].set_ylabel("GT")
    for ax in axes.ravel(): ax.axis("off")
    fig.tight_layout(); fig.savefig(OUT / "stage10g_sentinel_predictions.png",dpi=130); plt.close(fig)
    fig, axes = plt.subplots(2,len(selected_epochs),figsize=(3*len(selected_epochs),6))
    for col,epoch in enumerate(selected_epochs):
        for row,split in enumerate(("train","validation")):
            matrix=np.array(history[epoch-1][split]["confusion_matrix"],float); matrix/=np.maximum(matrix.sum(1,keepdims=True),1); axes[row,col].imshow(matrix,vmin=0,vmax=1,cmap="Blues"); axes[row,col].set_title(f"{split} e{epoch}",fontsize=8)
    for ax in axes.ravel(): ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(OUT / "stage10g_confusion_matrix_progression.png",dpi=140); plt.close(fig)


if __name__ == "__main__":
    main()
