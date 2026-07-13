#!/usr/bin/env python3
"""Run the single authorized Stage 10E 48-image overfit verification."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import distance_transform_edt
import torch
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = ROOT / "core/configs/train/stage_10e_48_image_overfit.yaml"
CLASS_NAMES = ["UNKNOWN", "STATIC_OBSTACLE", "HUMAN", "VEHICLE", "ROBOT"]


def sha256_array(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


def confusion_metrics(target: np.ndarray, prediction: np.ndarray) -> dict:
    matrix = np.bincount(
        (target.astype(np.int64) * 5 + prediction.astype(np.int64)).ravel(),
        minlength=25,
    ).reshape(5, 5)
    recall = np.diag(matrix) / np.maximum(matrix.sum(axis=1), 1)
    precision = np.diag(matrix) / np.maximum(matrix.sum(axis=0), 1)
    f1 = 2.0 * precision * recall / np.maximum(precision + recall, 1e-12)
    return {
        "pixel_accuracy": float(np.trace(matrix) / matrix.sum()),
        "macro_f1": float(f1.mean()),
        "per_class_recall": dict(zip(CLASS_NAMES, recall.tolist())),
        "prediction_class_fraction": dict(
            zip(CLASS_NAMES, (matrix.sum(axis=0) / matrix.sum()).tolist())
        ),
        "confusion_matrix": matrix.tolist(),
    }


@torch.no_grad()
def evaluate(model: torch.nn.Module, images: torch.Tensor, targets: torch.Tensor,
             criterion: torch.nn.Module, batch_size: int) -> tuple[float, np.ndarray, dict]:
    model.eval()
    losses = []
    predictions = []
    for start in range(0, len(images), batch_size):
        logits = model(images[start:start + batch_size])
        losses.append(float(criterion(logits, targets[start:start + batch_size])))
        predictions.append(logits.argmax(dim=1).cpu().numpy())
    prediction = np.concatenate(predictions)
    metrics = confusion_metrics(targets.cpu().numpy(), prediction)
    return float(np.mean(losses)), prediction, metrics


def region_metrics(target: np.ndarray, prediction: np.ndarray) -> dict:
    boundary = np.zeros_like(target, dtype=bool)
    interior = np.zeros_like(target, dtype=bool)
    for image_index, mask in enumerate(target):
        for class_id in range(5):
            region = mask == class_id
            distance = distance_transform_edt(region)
            boundary[image_index] |= region & (distance <= 2.0)
            interior[image_index] |= region & (distance > 2.0)
    return {
        "interior": confusion_metrics(target[interior], prediction[interior]),
        "boundary": confusion_metrics(target[boundary], prediction[boundary]),
        "interior_pixel_count": int(interior.sum()),
        "boundary_pixel_count": int(boundary.sum()),
    }


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    (OUT / "stage10e_training_config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False)
    )
    ids = config["selected_scene_ids"]
    if ids != list(range(48)):
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: scene IDs are not exactly 0-47")

    raw = np.load(OUT / "dataset/train.npz", allow_pickle=False)
    dataset = RGBSemanticDataset(OUT / "dataset/train.npz")
    manifest = json.loads((OUT / "dataset_manifest.json").read_text())["records"]
    manifest_by_scene = {record["scene_id"]: record for record in manifest}
    four_image = json.loads((OUT / "four_image_selection.json").read_text())
    authoritative_first_four = {record["scene_id"]: record for record in four_image["records"]}

    records = []
    all_counts = np.zeros(5, dtype=np.int64)
    for scene_id in ids:
        if int(dataset.scene_ids[scene_id]) != scene_id:
            raise SystemExit(f"BLOCKED_DATA_INCONSISTENCY: dataset index {scene_id} mismatch")
        meta = manifest_by_scene.get(scene_id)
        if meta is None or meta["split"] != "train":
            raise SystemExit(f"BLOCKED_DATA_INCONSISTENCY: scene {scene_id} is not train")
        image = raw["images"][scene_id]
        label = raw["semantic_masks"][scene_id]
        image_hash = sha256_array(image)
        label_hash = sha256_array(label)
        if scene_id in authoritative_first_four:
            expected = authoritative_first_four[scene_id]
            if image_hash != expected["rgb_sha256"] or label_hash != expected["semantic_label_sha256"]:
                raise SystemExit(f"BLOCKED_DATA_INCONSISTENCY: authoritative hash mismatch at {scene_id}")
        counts = np.bincount(label.ravel(), minlength=5)
        all_counts += counts
        records.append({
            "scene_id": scene_id,
            "image_id": scene_id,
            "geometry_seed": meta["geometry_seed"],
            "appearance_seed": meta["appearance_seed"],
            "camera_seed": meta["camera_seed"],
            "rgb_sha256": image_hash,
            "semantic_label_sha256": label_hash,
            "class_pixel_counts": dict(zip(CLASS_NAMES, counts.tolist())),
            "class_presence": dict(zip(CLASS_NAMES, (counts > 0).tolist())),
        })
    selection = {
        "split": "train",
        "selected_scene_ids": ids,
        "total_images": len(ids),
        "authoritative_hash_reference": "post-Stage-10A repaired dataset; scenes 0-3 cross-checked against four_image_selection.json",
        "all_classes_present_in_every_image": all(all(record["class_presence"].values()) for record in records),
        "records": records,
    }
    (OUT / "stage10e_48_image_selection.json").write_text(json.dumps(selection, indent=2) + "\n")

    stage10d_weights = json.loads((OUT / "stage10d_class_weight_audit.json").read_text())
    expected_weights = np.array(list(stage10d_weights["actual_normalized_weights"].values()))
    computed_weights = np.sqrt(all_counts.sum() / np.maximum(all_counts, 1))
    computed_weights /= computed_weights.mean()
    if not np.array_equal(all_counts, np.array(list(stage10d_weights["raw_pixel_count"].values()))):
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: class counts differ from Stage 10D")
    if not np.allclose(computed_weights, expected_weights, rtol=0.0, atol=1e-12):
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: class weights differ from Stage 10D")
    weight_confirmation = {
        "source": "Stage 10D fixed train scene IDs 0-47",
        "class_order": dict(zip(CLASS_NAMES, range(5))),
        "stage10d_weights": dict(zip(CLASS_NAMES, expected_weights.tolist())),
        "stage10e_recomputed_weights": dict(zip(CLASS_NAMES, computed_weights.tolist())),
        "maximum_absolute_difference": float(np.max(np.abs(computed_weights - expected_weights))),
        "exact_order_confirmed": True,
        "consistent_with_stage10d": True,
    }
    (OUT / "stage10e_class_weight_confirmation.json").write_text(
        json.dumps(weight_confirmation, indent=2) + "\n"
    )

    images = torch.stack([dataset[index]["image"] for index in ids])
    targets = torch.stack([dataset[index]["target"] for index in ids])
    static = {
        "logits_shape_expected": [config["batch_size"], 5, 120, 160],
        "target_shape_expected": [config["batch_size"], 120, 160],
        "target_dtype": str(targets.dtype),
        "label_min": int(targets.min()),
        "label_max": int(targets.max()),
        "label_ids": torch.unique(targets).tolist(),
        "cross_entropy_input": "raw_logits",
        "unknown_is_ignore_index": False,
        "inputs_finite": bool(torch.isfinite(images).all()),
        "labels_valid": bool(((targets >= 0) & (targets <= 4)).all()),
    }
    if static["target_dtype"] != "torch.int64" or static["label_ids"] != list(range(5)):
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: invalid target interface")

    seed_all(config["seed"])
    torch.set_num_threads(4)
    model = TinySemanticSegmentation()
    if model.parameter_count != config["model_parameter_count"]:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: model structure changed")
    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor(computed_weights, dtype=torch.float32))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    optimized = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}
    trainable = {id(parameter) for parameter in model.parameters() if parameter.requires_grad}
    if optimized != trainable:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: optimizer parameter coverage mismatch")
    with torch.no_grad():
        probe = model(images[:config["batch_size"]])
    static["logits_shape_actual"] = list(probe.shape)
    static["target_shape_actual"] = list(targets[:config["batch_size"]].shape)
    static["model_parameter_count"] = model.parameter_count
    static["optimizer_covers_all_trainable_parameters"] = optimized == trainable
    if static["logits_shape_actual"] != static["logits_shape_expected"]:
        raise SystemExit("BLOCKED_DATA_INCONSISTENCY: logits shape mismatch")

    history = []
    snapshots = {}
    maximum_steps = config["maximum_optimizer_steps"]
    batch_size = config["batch_size"]
    initial_loss, initial_prediction, initial_metrics = evaluate(
        model, images, targets, criterion, batch_size
    )
    initial_state_hash = hashlib.sha256(
        b"".join(value.detach().cpu().numpy().tobytes() for value in model.state_dict().values())
    ).hexdigest()
    snapshots[0] = initial_prediction
    last_gradient_norm = 0.0
    for step in range(maximum_steps + 1):
        if step % config["record_interval_steps"] == 0:
            loss, prediction, metrics = evaluate(model, images, targets, criterion, batch_size)
            history.append({
                "step": step,
                "total_loss": loss,
                "relative_loss": loss / initial_loss,
                "gradient_norm": last_gradient_norm,
                "learning_rate": optimizer.param_groups[0]["lr"],
                **metrics,
            })
            if step in (0, maximum_steps // 2, maximum_steps):
                snapshots[step] = prediction
            if not math.isfinite(loss):
                raise SystemExit("BLOCKED_UNRESOLVED_PIPELINE: non-finite training loss")
        if step == maximum_steps:
            break
        batch_index = step % (len(ids) // batch_size)
        start = batch_index * batch_size
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(images[start:start + batch_size])
        loss = criterion(logits, targets[start:start + batch_size])
        loss.backward()
        gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
        if not gradients or not all(torch.isfinite(gradient).all() for gradient in gradients):
            raise SystemExit("BLOCKED_UNRESOLVED_PIPELINE: invalid gradients")
        last_gradient_norm = math.sqrt(sum(float(gradient.norm()) ** 2 for gradient in gradients))
        optimizer.step()

    final_loss, final_prediction, final_metrics = evaluate(model, images, targets, criterion, batch_size)
    targets_numpy = targets.numpy()
    regions = region_metrics(targets_numpy, final_prediction)
    final_metrics.update(regions)
    confusion = {
        "class_order": dict(zip(CLASS_NAMES, range(5))),
        "matrix_rows_gt_columns_prediction": final_metrics["confusion_matrix"],
        "selected_errors": {
            "HUMAN_to_UNKNOWN": final_metrics["confusion_matrix"][2][0],
            "HUMAN_to_STATIC": final_metrics["confusion_matrix"][2][1],
            "HUMAN_to_ROBOT": final_metrics["confusion_matrix"][2][4],
            "VEHICLE_to_UNKNOWN": final_metrics["confusion_matrix"][3][0],
            "VEHICLE_to_STATIC": final_metrics["confusion_matrix"][3][1],
            "ROBOT_to_UNKNOWN": final_metrics["confusion_matrix"][4][0],
            "ROBOT_to_STATIC": final_metrics["confusion_matrix"][4][1],
            "ROBOT_to_HUMAN": final_metrics["confusion_matrix"][4][2],
        },
        "all_pixel": {key: final_metrics[key] for key in ("pixel_accuracy", "macro_f1", "per_class_recall", "prediction_class_fraction")},
        "interior": regions["interior"],
        "boundary": regions["boundary"],
    }
    (OUT / "stage10e_confusion_matrix.json").write_text(json.dumps(confusion, indent=2) + "\n")

    losses = np.array([record["total_loss"] for record in history])
    steps = np.array([record["step"] for record in history], dtype=float)
    tail_count = max(3, int(math.ceil(len(history) * 0.2)))
    slope = float(np.polyfit(steps[-tail_count:], losses[-tail_count:], 1)[0])
    best_index = int(np.argmin(losses))
    relative_loss = final_loss / initial_loss
    core_recalls = final_metrics["per_class_recall"]
    no_severe_collapse = (
        min(core_recalls[name] for name in CLASS_NAMES[2:]) > 0.0
        and sum(value > 0.95 for value in final_metrics["prediction_class_fraction"].values()) == 0
    )
    passed = relative_loss < 0.55 and no_severe_collapse
    tail_range = float(losses[-tail_count:].max() - losses[-tail_count:].min())
    if passed:
        trend = (
            "passed_gate_with_low_loss_oscillation"
            if tail_range > 0.01
            else "passed_gate_with_stable_low_loss"
        )
        decision = ["48_IMAGE_OVERFIT_GATE_PASSED", "READY_FOR_FULL_STAGE10_TRAINING"]
    else:
        trend = "still_clearly_decreasing" if slope < -1e-5 else "plateau_or_oscillation"
        if not no_severe_collapse:
            decision = ["BLOCKED_CLASS_COLLAPSE"]
        elif slope < -1e-5:
            decision = ["BLOCKED_OPTIMIZATION_CONVERGENCE"]
        else:
            decision = ["BLOCKED_MODEL_CAPACITY"]
    convergence = {
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "relative_loss": relative_loss,
        "best_loss": float(losses[best_index]),
        "best_step": int(history[best_index]["step"]),
        "last_20_percent_record_count": tail_count,
        "last_20_percent_loss_slope_per_optimizer_step": slope,
        "classification": trend,
        "oscillation_range_last_20_percent": tail_range,
    }
    metrics_output = {
        **static,
        "initial_state_sha256": initial_state_hash,
        "optimizer_steps": maximum_steps,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "relative_loss": relative_loss,
        "required_relative_loss_strictly_below": 0.55,
        **final_metrics,
        "no_severe_prediction_collapse": no_severe_collapse,
        "pass": passed,
        "decision": decision,
    }
    (OUT / "stage10e_training_history.json").write_text(json.dumps(history, indent=2) + "\n")
    (OUT / "stage10e_overfit_metrics.json").write_text(json.dumps(metrics_output, indent=2) + "\n")
    (OUT / "stage10e_convergence_analysis.json").write_text(json.dumps(convergence, indent=2) + "\n")

    checkpoint_path = OUT / "stage10e_48_image_overfit_checkpoint.pt"
    torch.save({
        "purpose": config["checkpoint_purpose"],
        "model_state_dict": model.state_dict(),
        "config": config,
        "decision": decision,
    }, checkpoint_path)
    probe_input = images[:2]
    model.eval()
    with torch.no_grad():
        logits_before = model(probe_input)
    restored = TinySemanticSegmentation()
    restored.load_state_dict(torch.load(checkpoint_path, map_location="cpu", weights_only=True)["model_state_dict"])
    restored.eval()
    with torch.no_grad():
        logits_after = restored(probe_input)
    reload_difference = float((logits_before - logits_after).abs().max())
    reload_report = {
        "checkpoint": checkpoint_path.name,
        "purpose": config["checkpoint_purpose"],
        "probe_scene_ids": [0, 1],
        "logits_max_absolute_difference": reload_difference,
        "floating_point_tolerance": 1e-7,
        "pass": reload_difference <= 1e-7,
    }
    (OUT / "stage10e_checkpoint_reload.json").write_text(json.dumps(reload_report, indent=2) + "\n")

    plot_history(history)
    plot_confusion(np.array(final_metrics["confusion_matrix"]))
    plot_predictions(raw["images"][ids], targets_numpy, snapshots, final_prediction)
    plot_boundary_errors(raw["images"][ids], targets_numpy, final_prediction)
    print(json.dumps({"metrics": metrics_output, "convergence": convergence, "checkpoint": reload_report}, indent=2))


def plot_history(history: list[dict]) -> None:
    steps = [record["step"] for record in history]
    plots = [
        ("stage10e_loss_curve.png", "total_loss", "weighted CE loss"),
        ("stage10e_relative_loss_curve.png", "relative_loss", "relative loss"),
        ("stage10e_macro_f1_curve.png", "macro_f1", "macro F1"),
    ]
    for filename, key, ylabel in plots:
        figure, axis = plt.subplots(figsize=(7, 4))
        axis.plot(steps, [record[key] for record in history])
        if key == "relative_loss":
            axis.axhline(0.55, color="red", linestyle="--", label="gate")
            axis.legend()
        axis.set(xlabel="optimizer step", ylabel=ylabel)
        axis.grid(True)
        figure.tight_layout()
        figure.savefig(OUT / filename, dpi=150)
        plt.close(figure)
    figure, axis = plt.subplots(figsize=(8, 5))
    for name in CLASS_NAMES:
        axis.plot(steps, [record["per_class_recall"][name] for record in history], label=name)
    axis.set(xlabel="optimizer step", ylabel="recall", ylim=(-0.02, 1.02))
    axis.grid(True)
    axis.legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(OUT / "stage10e_per_class_recall_curve.png", dpi=150)
    plt.close(figure)
    figure, axis = plt.subplots(figsize=(8, 5))
    for name in CLASS_NAMES:
        axis.plot(steps, [record["prediction_class_fraction"][name] for record in history], label=name)
    axis.set(xlabel="optimizer step", ylabel="predicted pixel fraction", ylim=(-0.02, 1.02))
    axis.grid(True)
    axis.legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(OUT / "stage10e_prediction_class_fraction.png", dpi=150)
    plt.close(figure)


def plot_confusion(matrix: np.ndarray) -> None:
    normalized = matrix / np.maximum(matrix.sum(axis=1, keepdims=True), 1)
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(normalized, vmin=0, vmax=1, cmap="Blues")
    axis.set_xticks(range(5), CLASS_NAMES, rotation=35, ha="right")
    axis.set_yticks(range(5), CLASS_NAMES)
    axis.set(xlabel="prediction", ylabel="ground truth")
    for row in range(5):
        for column in range(5):
            axis.text(column, row, f"{normalized[row, column]:.3f}", ha="center", va="center", fontsize=7)
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(OUT / "stage10e_confusion_matrix.png", dpi=150)
    plt.close(figure)


def plot_predictions(images: np.ndarray, targets: np.ndarray, snapshots: dict, final: np.ndarray) -> None:
    selected = [0, 12, 24, 36, 47]
    figure, axes = plt.subplots(3, len(selected), figsize=(13, 7))
    for column, scene_id in enumerate(selected):
        axes[0, column].imshow(images[scene_id])
        axes[1, column].imshow(targets[scene_id], vmin=0, vmax=4, cmap="tab10")
        axes[2, column].imshow(final[scene_id], vmin=0, vmax=4, cmap="tab10")
        axes[0, column].set_title(f"scene {scene_id}")
    for axis in axes.ravel():
        axis.axis("off")
    axes[0, 0].set_ylabel("RGB")
    axes[1, 0].set_ylabel("GT")
    axes[2, 0].set_ylabel("prediction")
    figure.tight_layout()
    figure.savefig(OUT / "stage10e_prediction_examples.png", dpi=150)
    plt.close(figure)


def plot_boundary_errors(images: np.ndarray, targets: np.ndarray, prediction: np.ndarray) -> None:
    selected = [0, 12, 24, 36, 47]
    figure, axes = plt.subplots(2, len(selected), figsize=(13, 5))
    for column, scene_id in enumerate(selected):
        error = prediction[scene_id] != targets[scene_id]
        boundary = np.zeros_like(error)
        for class_id in range(5):
            region = targets[scene_id] == class_id
            boundary |= region & (distance_transform_edt(region) <= 2.0)
        axes[0, column].imshow(images[scene_id])
        axes[0, column].imshow(np.ma.masked_where(~error, error), cmap="Reds", alpha=0.75)
        axes[1, column].imshow(boundary, cmap="gray")
        axes[1, column].imshow(np.ma.masked_where(~error, error), cmap="Reds", alpha=0.75)
        axes[0, column].set_title(f"scene {scene_id}")
    for axis in axes.ravel():
        axis.axis("off")
    axes[0, 0].set_ylabel("all errors")
    axes[1, 0].set_ylabel("boundary/errors")
    figure.tight_layout()
    figure.savefig(OUT / "stage10e_boundary_error_examples.png", dpi=150)
    plt.close(figure)


if __name__ == "__main__":
    main()
