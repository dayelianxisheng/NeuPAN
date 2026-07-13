"""Dtype-aware frozen class-weight audits for Stage 10F."""

from __future__ import annotations

import numpy as np
import torch


def audit_source_class_weights(
    yaml_weights: list[float],
    authoritative_weights: list[float],
    yaml_class_order: list[str],
    authoritative_class_order: list[str],
    *,
    atol: float = 1e-12,
    rtol: float = 1e-12,
) -> dict:
    """Compare authoritative definitions before any runtime dtype conversion."""
    yaml_values = np.asarray(yaml_weights, dtype=np.float64)
    authoritative_values = np.asarray(authoritative_weights, dtype=np.float64)
    order_match = list(yaml_class_order) == list(authoritative_class_order)
    same_shape = yaml_values.shape == authoritative_values.shape
    differences = (
        np.abs(yaml_values - authoritative_values)
        if same_shape
        else np.asarray([np.inf], dtype=np.float64)
    )
    passed = bool(
        order_match
        and same_shape
        and np.allclose(yaml_values, authoritative_values, atol=atol, rtol=rtol)
    )
    return {
        "yaml_dtype": "float64",
        "authoritative_dtype": "float64",
        "yaml_class_order": list(yaml_class_order),
        "authoritative_class_order": list(authoritative_class_order),
        "class_order_match": order_match,
        "source_elementwise_differences": differences.tolist(),
        "source_max_abs_difference": float(differences.max(initial=0.0)),
        "atol": atol,
        "rtol": rtol,
        "passed": passed,
    }


def audit_runtime_weight_cast(
    authoritative_weights: list[float],
    runtime_tensor: torch.Tensor,
    *,
    atol: float = 1e-7,
    rtol: float = 1e-7,
) -> dict:
    """Validate expected float32 rounding after source equality has passed."""
    authoritative_values = np.asarray(authoritative_weights, dtype=np.float64)
    runtime_values = runtime_tensor.detach().cpu().numpy().astype(np.float64)
    same_shape = runtime_values.shape == authoritative_values.shape
    differences = (
        np.abs(runtime_values - authoritative_values)
        if same_shape
        else np.asarray([np.inf], dtype=np.float64)
    )
    dtype_match = runtime_tensor.dtype == torch.float32
    passed = bool(
        dtype_match
        and same_shape
        and np.allclose(runtime_values, authoritative_values, atol=atol, rtol=rtol)
    )
    return {
        "runtime_dtype": str(runtime_tensor.dtype).replace("torch.", ""),
        "runtime_cast_elementwise_differences": differences.tolist(),
        "runtime_cast_max_abs_difference": float(differences.max(initial=0.0)),
        "runtime_cast_difference_expected": True,
        "runtime_cast_within_float32_precision": passed,
        "atol": atol,
        "rtol": rtol,
        "passed": passed,
    }


def build_audited_cross_entropy(
    authoritative_weights: list[float], device: torch.device | str = "cpu"
) -> tuple[torch.Tensor, torch.nn.CrossEntropyLoss, dict]:
    """Construct CE with the exact runtime tensor covered by the cast audit."""
    runtime_weights = torch.tensor(authoritative_weights, dtype=torch.float32, device=device)
    runtime_audit = audit_runtime_weight_cast(authoritative_weights, runtime_weights)
    if not runtime_audit["passed"]:
        raise ValueError("runtime class-weight cast audit failed")
    criterion = torch.nn.CrossEntropyLoss(weight=runtime_weights)
    if criterion.weight is not runtime_weights:
        raise AssertionError("CrossEntropyLoss did not retain the audited runtime tensor")
    return runtime_weights, criterion, runtime_audit
