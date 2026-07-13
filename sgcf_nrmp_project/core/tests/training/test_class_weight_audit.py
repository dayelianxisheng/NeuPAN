"""Tests for source-definition and runtime-dtype weight audits."""

import unittest

import torch

from sgcf_nrmp.training.class_weight_audit import (
    audit_runtime_weight_cast,
    audit_source_class_weights,
    build_audited_cross_entropy,
)


WEIGHTS = [0.3282637900393733, 0.8115540256535101, 1.5283809715797676, 1.238860853978437, 1.0929403587489122]
ORDER = ["UNKNOWN", "STATIC_OBSTACLE", "HUMAN", "VEHICLE", "ROBOT"]


class ClassWeightAuditTest(unittest.TestCase):
    def test_identical_float64_sources_pass(self):
        result = audit_source_class_weights(WEIGHTS, list(WEIGHTS), ORDER, list(ORDER))
        self.assertTrue(result["passed"])
        self.assertEqual(result["source_max_abs_difference"], 0.0)

    def test_changed_float64_source_fails(self):
        changed = list(WEIGHTS)
        changed[2] += 1e-5
        self.assertFalse(audit_source_class_weights(changed, WEIGHTS, ORDER, ORDER)["passed"])

    def test_class_order_mismatch_fails(self):
        changed_order = list(ORDER)
        changed_order[2], changed_order[4] = changed_order[4], changed_order[2]
        self.assertFalse(audit_source_class_weights(WEIGHTS, WEIGHTS, changed_order, ORDER)["passed"])

    def test_normal_float32_cast_passes(self):
        runtime = torch.tensor(WEIGHTS, dtype=torch.float32)
        result = audit_runtime_weight_cast(WEIGHTS, runtime)
        self.assertTrue(result["passed"])
        self.assertEqual(result["runtime_dtype"], "float32")

    def test_excessive_runtime_deviation_fails(self):
        runtime = torch.tensor(WEIGHTS, dtype=torch.float32)
        runtime[3] += 1e-3
        self.assertFalse(audit_runtime_weight_cast(WEIGHTS, runtime)["passed"])

    def test_cross_entropy_uses_audited_tensor(self):
        runtime, criterion, result = build_audited_cross_entropy(WEIGHTS)
        self.assertTrue(result["passed"])
        self.assertIs(criterion.weight, runtime)
        logits = torch.zeros(1, 5, 2, 2)
        target = torch.zeros(1, 2, 2, dtype=torch.long)
        self.assertTrue(torch.isfinite(criterion(logits, target)))


if __name__ == "__main__":
    unittest.main()
