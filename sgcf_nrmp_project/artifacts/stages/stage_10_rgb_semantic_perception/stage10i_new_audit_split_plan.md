# Stage 10I New Untouched Synthetic Audit Split Plan

## Purpose

The original Stage 10H test is no longer an untouched final acceptance set because its aggregate HUMAN result is known. A future acceptance decision therefore requires a newly generated audit split. This document is a plan only: no new scene, image, label, manifest, or hash was generated or inspected in Stage 10I.

## Entry condition

A candidate checkpoint, confidence policy, and every validation-derived decision must be frozen before audit-set generation. The Stage 10I diagnostic checkpoint is not eligible because the simultaneous validation gate did not pass.

## Frozen generation contract

- Use the unchanged Stage 10 appearance renderer and class IDs.
- Allocate 40–100 new scene IDs outside all existing train/validation/original-test IDs.
- Allocate new, non-overlapping geometry, appearance, and camera seeds.
- Do not copy or perturb an existing base scene.
- Preserve 160×120 RGB, masks, normalization, and metadata schema.
- Perform scene/seed disjointness and label-leakage audits before any inference.

## One-time lifecycle

1. Freeze model checkpoint, model/config hashes, normalization, class weights, and confidence policy.
2. Generate the audit split once with an independently recorded root seed range.
3. Atomically write and freeze its manifest and per-file SHA-256 hashes.
4. Verify that no scene or seed overlaps train, validation, or the original test.
5. Run inference and final metrics exactly once.
6. Do not use the audit output for tuning or a second evaluation.

## Required acceptance evidence

Report all-pixel mIoU, macro F1, per-class IoU/precision/recall, HUMAN error destinations, boundaries, components, calibration, PointPainting, Semantic Margin gap, and CPU latency under the predeclared Stage 10 gates.

## Current status

```text
NOT_GENERATED
NOT_READ
NOT_AUTHORIZED_BECAUSE_STAGE10I_VALIDATION_GATE_FAILED
```
