# Stage 10 Known Limitations after Stage 10H

- Status: `BLOCKED_OPTIMIZATION_CONVERGENCE` after the final Stage 10J
  validation-only stabilization attempt.
- Stage 07 fixed-color RGB debug images are invalid training inputs.
- The generated data are simplified synthetic-domain icons, not real imagery.
- The training lifecycle and 48-image memorization gates are repaired and pass,
  but the one-time test HUMAN recall is `0.71340` versus the required `0.80`.
- Test HUMAN IoU is `0.57726`, below the suggested `0.60` target.
- Boundary errors remain substantial (boundary-1px accuracy `0.59488`).
- The validation-selected checkpoint is retained for audit only and is not an
  accepted Stage 10 deployment model.
- PointPainting, margin-gap, robustness, and CPU-latency evaluation were not
  executed because the HUMAN test gate failed first.
- Epoch-100 Train/Validation HUMAN recall was `0.92222/0.77804`; the gap is real,
  but training HUMAN itself was not fully saturated.
- Under frozen continuation, HUMAN recall oscillated against aggregate mIoU and
  VEHICLE/ROBOT performance. No epoch met all simultaneous diagnostic gates.
- Validation has only 19 visible HUMAN instances after hard occlusion, limiting
  factor/seed correlation strength.
- A new untouched audit split is only planned; it has not been generated or read.
- Real RGB, silent calibration drift, future motion, Planner stability, formal
  safety, ROS, and Gazebo are not validated.
- Stage 05 Exact Geometry, Stage 07 projection/PointPainting/margin, Stage 08 R1
  rules, and Stage 09 Planner remain frozen.
- The final authorized Stage 10J stabilization attempt completed epochs 146–195
  at learning rate `0.0002`. Low-LR validation metrics were stable, but HUMAN
  recall remained in `[0.74810, 0.75610]`; no checkpoint met the simultaneous
  validation gates.
- No further Stage 10 tuning is authorized for the current model, loss,
  renderer, split, and optimizer configuration. Any continuation requires a
  newly defined model/data redesign protocol with a fresh untouched audit set.
