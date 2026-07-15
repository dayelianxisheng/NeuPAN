#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
runner="$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh"
stage=stage_15b_p0_navigation_baseline
seeds=(101 202 303)
scenes=(empty_world single_static_obstacle static_corridor narrow_passage)
index=0
for scene in "${scenes[@]}"; do
  for seed in "${seeds[@]}"; do
    if [[ "$scene" == empty_world && "$seed" == 101 && -s "$repo/sgcf_nrmp_project/artifacts/stages/$stage/runtime/smoke_empty_seed101_p0/planner_result.json" ]]; then
      continue
    fi
    run_id="fixed_${scene}_seed${seed}_p0"
    [[ -s "$repo/sgcf_nrmp_project/artifacts/stages/$stage/runtime/$run_id/planner_result.json" ]] && continue
    domain=$((130 + index)); index=$((index + 1))
    STAGE11CC_STAGE_DIR="$stage" STAGE11CC_RUN_ID="$run_id" STAGE11CC_MODES_OVERRIDE=P0 \
    STAGE11CC_GAZEBO_SEED="$seed" STAGE11CC_GZ_PARTITION="sgcf_stage15b_${scene}_${seed}" \
    STAGE11CC_ROS_DOMAIN_ID="$domain" \
    STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
    STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
    STAGE11CD1_ALLOWED_MODES=P0 STAGE11CD1_ACTIVE_DURATION_S=20 \
    STAGE15B_EVALUATION_DURATION_S=20 STAGE15B_GOAL_TOLERANCE_M=0.25 STAGE15B_WALL_TIMEOUT_S=180 \
    "$runner" "$scene"
  done
done

for seed in "${seeds[@]}"; do
  run_id="fixed_mixed_seed${seed}_p0"
  [[ -s "$repo/sgcf_nrmp_project/artifacts/stages/$stage/runtime/$run_id/planner_result.json" ]] && continue
  domain=$((145 + index)); index=$((index + 1))
  STAGE11CC_STAGE_DIR="$stage" STAGE11CC_RUN_ID="$run_id" STAGE11CC_MODES_OVERRIDE=P0 \
  STAGE11CC_GAZEBO_SEED="$seed" STAGE11CC_GZ_PARTITION="sgcf_stage15b_mixed_${seed}" \
  STAGE11CC_ROS_DOMAIN_ID="$domain" \
  STAGE11CC_WORLD_PATH="/workspace/sgcf_nrmp_project/gazebo/overlays/stage15_oracle_mixed/stage15_mixed_fixed_${seed}.sdf" \
  STAGE15_SCENE_LABEL="stage15_mixed_fixed_${seed}" \
  STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
  STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
  STAGE11CD1_ALLOWED_MODES=P0 STAGE11CD1_ACTIVE_DURATION_S=20 \
  STAGE15B_EVALUATION_DURATION_S=20 STAGE15B_GOAL_TOLERANCE_M=0.25 STAGE15B_WALL_TIMEOUT_S=180 \
  "$runner" human_path_side
done
