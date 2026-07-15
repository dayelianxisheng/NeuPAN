#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
manifest="$repo/sgcf_nrmp_project/gazebo/overlays/stage15c_feasible_semantics/manifest.json"
runner="$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh"
stage=stage_15c_oracle_semantic_reevaluation
index=0
while IFS= read -r row; do
  scene=$(jq -r .scene_id <<<"$row")
  world=/workspace/$(jq -r .world <<<"$row")
  duration=$(jq -r .control_window_s <<<"$row")
  reference=$(jq -c .reference_waypoints <<<"$row")
  run_id="precheck_v2_${scene}_seed101_p0"
  domain=$((190 + index)); index=$((index + 1))
  STAGE11CC_STAGE_DIR="$stage" STAGE11CC_RUN_ID="$run_id" STAGE11CC_MODES_OVERRIDE=P0 \
  STAGE11CC_GAZEBO_SEED=101 STAGE11CC_GZ_PARTITION="sgcf_${scene}_precheck" \
  STAGE11CC_ROS_DOMAIN_ID="$domain" STAGE11CC_WORLD_PATH="$world" \
  STAGE15_SCENE_LABEL="$scene" STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
  STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
  STAGE11CD1_ALLOWED_MODES=P0 STAGE11CD1_ACTIVE_DURATION_S="$duration" \
  STAGE15B_EVALUATION_DURATION_S="$duration" STAGE15B_GOAL_TOLERANCE_M=0.25 \
  STAGE15B_REFERENCE_WAYPOINTS_JSON="$reference" STAGE15B_WALL_TIMEOUT_S=240 \
  "$runner" human_path_side
done < <(jq -c '.scenarios[]' "$manifest")
