# Reliability Information Boundary

No complete-world, hidden-instance, GT point class, GT association correctness, true perturbation magnitude, Oracle depth, or future-frame information may enter a deployable gate. This audit preserves that boundary.

Counterexample:

- Case A: a true HUMAN LiDAR point projects into a uniform HUMAN semantic region; reliability GT is 1.
- Case B: a true STATIC LiDAR point is misprojected into the same uniform HUMAN semantic region; reliability GT is 0.
- All permitted point-level and frame-level features are bitwise identical.

Therefore no deterministic rule or learned MLP over the permitted features can separate the pair. Adding GT perturbation, GT class, Oracle instance/depth, or world geometry would make the task separable only by violating the deployment boundary.
