#!/usr/bin/env python3
"""Freeze validation policy, then run the one authorized Stage 10H test evaluation."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter
import torch
import torch.nn.functional as F
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.evaluation.oracle_to_prediction_gap import (
    evaluate_margin_gap,
    evaluate_painting,
    observable_points_for_image,
)
from sgcf_nrmp.evaluation.semantic_perception_evaluator import (
    CLASS_NAMES,
    collect_probabilities,
    evaluate_probabilities,
    region_evaluation,
)
from sgcf_nrmp.evaluation.threshold_summary import build_threshold_summary
from sgcf_nrmp.fusion.pointpainting import paint_points
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.perception.semantic_confidence import confidence_classes
from sgcf_nrmp.semantic.explicit_failure_gate import explicit_failure_reliability
from sgcf_nrmp.semantic.margin_labeler import semantic_margin_ground_truth
from sgcf_nrmp.training.lifecycle import atomic_torch_save, evaluate_split


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"
CONFIG_PATH = ROOT / "core/configs/train/stage_10h_formal_retry.yaml"
CHECKPOINT_PATH = OUT / "best_rgb_semantic_model.pt"
CLASS_MARGINS = {0: 0.0, 1: 0.0, 2: 0.35, 3: 0.20, 4: 0.15}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tensors(dataset):
    return (
        torch.stack([dataset[index]["image"] for index in range(len(dataset))]),
        torch.stack([dataset[index]["target"] for index in range(len(dataset))]),
    )


def predict(probabilities: np.ndarray, probability=None, entropy=None) -> np.ndarray:
    return confidence_classes(torch.from_numpy(probabilities), probability, entropy)[0].numpy()


def threshold_metrics(probabilities: np.ndarray, target: np.ndarray, probability=None, entropy=None) -> dict:
    prediction = predict(probabilities, probability, entropy)
    metrics = evaluate_probabilities(probabilities, target, prediction)
    summary = build_threshold_summary(target, prediction)
    margins = np.array([0.0, 0.0, 0.35, 0.20, 0.15])
    oracle = margins[target]; estimated = margins[prediction]
    positive = oracle > 0
    under = float(np.mean(estimated[positive] + .05 < oracle[positive])) if positive.any() else 0.0
    values = {name: entry["value"] for name, entry in summary.items()}
    recall = metrics["per_class_recall"]
    score = (
        metrics["macro_f1"] + recall["HUMAN"] + recall["VEHICLE"] + recall["ROBOT"]
        - (values["static_to_human_rate"] or 0.0)
        - (values["human_to_static_rate"] or 0.0)
        - (values["human_to_unknown_rate"] or 0.0) - under
    )
    return {
        "probability_threshold": probability, "entropy_threshold": entropy,
        "metrics": metrics, "threshold_summary": summary,
        "semantic_margin_underestimation_proxy": under, "selection_score": float(score),
    }


def freeze_validation_policy(model, checkpoint, config, validation_images, validation_targets, criterion):
    _, validation_metrics, probabilities = evaluate_split(model, validation_images, validation_targets, criterion, config["batch_size"])
    target = validation_targets.numpy()
    candidates = [{"strategy": "U0_argmax_always", **threshold_metrics(probabilities, target)}]
    for threshold in config["threshold_candidates"]["probability"]:
        candidates.append({"strategy": "U1_max_probability", **threshold_metrics(probabilities, target, threshold)})
    for probability in config["threshold_candidates"]["probability"]:
        for entropy in config["threshold_candidates"]["entropy"]:
            candidates.append({"strategy": "U2_probability_and_entropy", **threshold_metrics(probabilities, target, probability, entropy)})
    selected = max(candidates, key=lambda item: (
        item["selection_score"], item["metrics"]["per_class_recall"]["HUMAN"],
        item["metrics"]["macro_f1"], -item["metrics"]["unknown_rate"],
    ))
    selection = {
        "selection_split": "validation_only", "selection_objective": "macro F1 + HUMAN/VEHICLE/ROBOT recall - explicit dangerous/confidence errors",
        "candidates": candidates, "selected": selected, "test_accessed": False,
    }
    (OUT / "stage10h_threshold_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    checkpoint["confidence_policy"] = selected["strategy"]
    checkpoint["probability_threshold"] = selected["probability_threshold"]
    checkpoint["entropy_threshold"] = selected["entropy_threshold"]
    atomic_torch_save(checkpoint, CHECKPOINT_PATH)
    restored = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    restored_model = TinySemanticSegmentation(); restored_model.load_state_dict(restored["model_state_dict"]); restored_model.eval(); model.eval()
    with torch.no_grad(): difference = float((model(validation_images[:2]) - restored_model(validation_images[:2])).abs().max())
    if difference > 1e-7: raise SystemExit("BLOCKED_MODEL_OR_DATA_PIPELINE: threshold checkpoint reload failed")
    freeze = {
        "status": "VALIDATION_FROZEN_BEFORE_TEST", "best_checkpoint_sha256": sha256_file(CHECKPOINT_PATH),
        "best_epoch": checkpoint["epoch"], "validation_metrics": validation_metrics,
        "threshold_strategy": selected["strategy"], "probability_threshold": selected["probability_threshold"],
        "entropy_threshold": selected["entropy_threshold"], "training_config_sha256": checkpoint["training_config_sha256"],
        "dataset_manifest_sha256": checkpoint["dataset_manifest_sha256"], "checkpoint_reload_max_abs_difference": difference,
    }
    (OUT / "stage10h_validation_freeze.json").write_text(json.dumps(freeze, indent=2) + "\n")
    return selected, freeze


def save_test_plots(images, targets, predictions, metrics, probabilities, regions):
    count = min(6, len(images))
    fig, axes = plt.subplots(count, 3, figsize=(10, 3 * count))
    for row in range(count):
        axes[row, 0].imshow(images[row]); axes[row, 0].set_title("RGB")
        axes[row, 1].imshow(targets[row], vmin=0, vmax=4, cmap="tab10"); axes[row, 1].set_title("GT")
        axes[row, 2].imshow(predictions[row], vmin=0, vmax=4, cmap="tab10"); axes[row, 2].set_title("prediction")
    for ax in axes.ravel(): ax.axis("off")
    fig.tight_layout(); fig.savefig(OUT / "stage10h_test_predictions.png", dpi=140); plt.close(fig)
    matrix = np.asarray(metrics["confusion_matrix"], float); matrix /= np.maximum(matrix.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(6, 5)); image = ax.imshow(matrix, vmin=0, vmax=1, cmap="Blues");
    ax.set_xticks(range(5), CLASS_NAMES, rotation=35, ha="right"); ax.set_yticks(range(5), CLASS_NAMES); fig.colorbar(image, ax=ax); fig.tight_layout(); fig.savefig(OUT / "stage10h_confusion_matrix.png", dpi=150); plt.close(fig)
    fig, axes = plt.subplots(2, 4, figsize=(12, 6))
    boundary = regions["boundary_3px"]
    for index, ax in enumerate(axes.ravel()):
        if index >= len(targets): ax.axis("off"); continue
        error = predictions[index] != targets[index]
        ax.imshow(error, cmap="Reds"); ax.contour(boundary[index], levels=[.5], colors="cyan", linewidths=.4); ax.axis("off")
    fig.tight_layout(); fig.savefig(OUT / "stage10h_boundary_errors.png", dpi=140); plt.close(fig)
    curve = metrics["calibration_curve"]
    fig, ax = plt.subplots(); ax.plot([item["confidence"] for item in curve], [item["accuracy"] for item in curve], "o-"); ax.plot([0, 1], [0, 1], "--"); ax.set(xlabel="confidence", ylabel="accuracy"); ax.grid(); fig.tight_layout(); fig.savefig(OUT / "stage10h_confidence_calibration.png", dpi=150); plt.close(fig)


def robustness(model, images, targets, selected):
    rng = np.random.default_rng(10)
    source = images[:20].clone()
    conditions = {
        "normal": source,
        "brightness": torch.clamp(source * .65, 0, 1),
        "contrast": torch.clamp((source - .5) * .55 + .5, 0, 1),
        "gaussian_noise": torch.clamp(source + torch.from_numpy(rng.normal(0, .05, source.shape)).float(), 0, 1),
        "motion_blur": F.avg_pool2d(F.pad(source, (4, 4, 0, 0), mode="replicate"), (1, 9), stride=1),
        "defocus_blur": F.avg_pool2d(F.pad(source, (3, 3, 3, 3), mode="reflect"), 7, stride=1),
        "low_resolution": F.interpolate(F.interpolate(source, size=(60, 80), mode="bilinear", align_corners=False), size=(120, 160), mode="bilinear", align_corners=False),
        "partial_occlusion": source.clone(),
        "image_border": source.clone(),
    }
    conditions["partial_occlusion"][:, :, 40:80, 55:105] = 0
    conditions["image_border"][:, :, :10] = 0; conditions["image_border"][:, :, -10:] = 0; conditions["image_border"][:, :, :, :10] = 0; conditions["image_border"][:, :, :, -10:] = 0
    result = {}
    for name, value in conditions.items():
        probabilities = collect_probabilities(model, value, 8)
        prediction = predict(probabilities, selected["probability_threshold"], selected["entropy_threshold"])
        metrics = evaluate_probabilities(probabilities, targets[:20].numpy(), prediction)
        result[name] = {key: metrics[key] for key in ("mean_iou", "macro_f1", "per_class_recall", "unknown_rate", "mean_confidence", "ece")}
    dummy = np.array([[1, 0, 0, 0, 0]], float)
    result["rgb_dropout"] = {"r1_semantic_contribution": float(explicit_failure_reliability(dummy, np.array([True]), False, 0.0).sum()), "model_called": False}
    result["outdated_image"] = {"r1_semantic_contribution": float(explicit_failure_reliability(dummy, np.array([True]), True, .2).sum()), "model_called": False}
    return result


def quantiles(values):
    values = np.asarray(values, float)
    return {"mean_ms": float(values.mean()), "p50_ms": float(np.quantile(values, .5)), "p95_ms": float(np.quantile(values, .95)), "p99_ms": float(np.quantile(values, .99))}


def benchmark(model, selected, oracle_mask):
    torch.set_num_threads(4); model.eval()
    output = {"device": "CPU", "thread_count": 4, "resolutions": {}}
    for height, width in ((120, 160), (240, 320)):
        rng = np.random.default_rng(height + width)
        image_uint8 = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
        timings = {name: [] for name in ("preprocess", "model_forward", "softmax", "unknown_threshold", "hard_pointpainting", "point_semantic_margin", "query_semantic_margin", "total")}
        first = None
        for iteration in range(31):
            start_total = time.perf_counter(); start = start_total
            tensor = torch.from_numpy(image_uint8.transpose(2, 0, 1).copy()).float().unsqueeze(0) / 255
            times = {"preprocess": (time.perf_counter() - start) * 1000}; start = time.perf_counter()
            with torch.no_grad(): logits = model(tensor)
            times["model_forward"] = (time.perf_counter() - start) * 1000; start = time.perf_counter()
            probabilities = torch.softmax(logits, 1)
            times["softmax"] = (time.perf_counter() - start) * 1000; start = time.perf_counter()
            semantic = confidence_classes(probabilities, selected["probability_threshold"], selected["entropy_threshold"])[0][0].numpy()
            times["unknown_threshold"] = (time.perf_counter() - start) * 1000; start = time.perf_counter()
            points_xy, ranges, _, projection = observable_points_for_image(np.where(oracle_mask > 0, oracle_mask, 1))
            painted = paint_points(points_xy, ranges, projection, semantic, 0.0)
            times["hard_pointpainting"] = (time.perf_counter() - start) * 1000; start = time.perf_counter()
            _ = np.array([CLASS_MARGINS[int(value)] for value in painted.class_ids])
            times["point_semantic_margin"] = (time.perf_counter() - start) * 1000; start = time.perf_counter()
            if len(points_xy):
                queries = np.c_[points_xy[:64, 0] - .55, points_xy[:64, 1], np.zeros(min(64, len(points_xy)))]
                semantic_margin_ground_truth(queries, points_xy, painted.class_ids, np.ones(len(points_xy), bool), painted.projection_valid, CLASS_MARGINS, .8, .5, 8.0)
            times["query_semantic_margin"] = (time.perf_counter() - start) * 1000
            times["total"] = (time.perf_counter() - start_total) * 1000
            if iteration == 0: first = times
            else:
                for name, value in times.items(): timings[name].append(value)
        output["resolutions"][f"{width}x{height}"] = {"first_inference_ms": first, "steady_state": {name: quantiles(values) for name, values in timings.items()}}
    model_p95 = output["resolutions"]["160x120"]["steady_state"]["model_forward"]["p95_ms"]
    total_p95 = output["resolutions"]["160x120"]["steady_state"]["total"]["p95_ms"]
    output["acceptance"] = {"model_p95_below_50ms": model_p95 < 50, "total_pipeline_p95_below_70ms": total_p95 < 70, "passed": model_p95 < 50 and total_p95 < 70}
    return output


def main():
    config = yaml.safe_load(CONFIG_PATH.read_text())
    readiness = json.loads((OUT / "stage10h_validation_readiness.json").read_text())
    if not readiness["passed"]: raise SystemExit("validation readiness failed; test access forbidden")
    validation = RGBSemanticDataset(OUT / "dataset/validation.npz")
    validation_images, validation_targets = tensors(validation)
    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    model = TinySemanticSegmentation(); model.load_state_dict(checkpoint["model_state_dict"]); model.eval()
    runtime_weights = torch.tensor(config["class_weights"], dtype=torch.float32)
    criterion = torch.nn.CrossEntropyLoss(weight=runtime_weights)
    selected, freeze = freeze_validation_policy(model, checkpoint, config, validation_images, validation_targets, criterion)

    # This is the single authorized test dataset construction and evaluation.
    test = RGBSemanticDataset(OUT / "dataset/test.npz")
    test_images, test_targets = tensors(test)
    probabilities = collect_probabilities(model, test_images, config["batch_size"])
    prediction = predict(probabilities, selected["probability_threshold"], selected["entropy_threshold"])
    metrics = evaluate_probabilities(probabilities, test_targets.numpy(), prediction)
    regions = region_evaluation(test_targets.numpy(), prediction, test.occluded)
    pixel_output = {"test_access_count": 1, "threshold_strategy": selected["strategy"], **metrics}
    (OUT / "stage10h_test_pixel_metrics.json").write_text(json.dumps(pixel_output, indent=2) + "\n")
    (OUT / "stage10h_per_class_metrics.json").write_text(json.dumps({key: metrics[key] for key in ("per_class_iou", "per_class_precision", "per_class_recall")}, indent=2) + "\n")
    (OUT / "stage10h_boundary_metrics.json").write_text(json.dumps(regions, indent=2) + "\n")
    (OUT / "stage10h_confusion_matrix.json").write_text(json.dumps({"class_order": list(CLASS_NAMES), "matrix": metrics["confusion_matrix"]}, indent=2) + "\n")
    if metrics["per_class_recall"]["HUMAN"] < .80:
        raise SystemExit("BLOCKED_HUMAN_RECALL: test HUMAN recall below 0.80")
    save_test_plots(test.images, test.masks, prediction, metrics, probabilities, __import__("sgcf_nrmp.evaluation.semantic_perception_evaluator", fromlist=["semantic_regions"]).semantic_regions(test.masks, test.occluded))

    painting, records = evaluate_painting(test.masks, prediction)
    (OUT / "stage10h_predicted_pointpainting_metrics.json").write_text(json.dumps(painting, indent=2) + "\n")
    if painting["pixel_accuracy"] < .85:
        raise SystemExit("BLOCKED_POINTPAINTING_GAP: painted-point accuracy below 0.85")
    margin = evaluate_margin_gap(records)
    (OUT / "stage10h_semantic_margin_gap.json").write_text(json.dumps(margin, indent=2) + "\n")
    if margin["margin_mae_m"] > .05 or margin["negative_violations"] or margin["upper_bound_violations"]:
        raise SystemExit("BLOCKED_SEMANTIC_MARGIN_GAP")
    robust = robustness(model, test_images, test_targets, selected)
    (OUT / "stage10h_robustness_metrics.json").write_text(json.dumps(robust, indent=2) + "\n")
    latency = benchmark(model, selected, test.masks[0])
    (OUT / "stage10h_perception_latency.json").write_text(json.dumps(latency, indent=2) + "\n")
    if not latency["acceptance"]["passed"]:
        raise SystemExit("BLOCKED_CPU_LATENCY")
    print(json.dumps({"validation_freeze": freeze, "test": {"mean_iou": metrics["mean_iou"], "human_iou": metrics["per_class_iou"]["HUMAN"], "human_recall": metrics["per_class_recall"]["HUMAN"]}, "painting_accuracy": painting["pixel_accuracy"], "margin_mae": margin["margin_mae_m"], "latency_acceptance": latency["acceptance"]}, indent=2))


if __name__ == "__main__":
    main()
