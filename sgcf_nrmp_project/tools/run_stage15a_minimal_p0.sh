#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
runner="$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh"
run_one() {
  local id=$1 scene=$2 seed=$3 domain=$4 world=${5:-}
  [[ -s "$repo/sgcf_nrmp_project/artifacts/stages/stage_15a_baseline_feasibility_analysis/runtime/$id/planner_result.json" ]] && return
  STAGE11CC_STAGE_DIR=stage_15a_baseline_feasibility_analysis \
  STAGE11CC_RUN_ID="$id" STAGE11CC_MODES_OVERRIDE=P0 STAGE11CC_GAZEBO_SEED="$seed" \
  STAGE11CC_GZ_PARTITION="sgcf_stage15a_${seed}" STAGE11CC_ROS_DOMAIN_ID="$domain" \
  STAGE11CC_WORLD_PATH="$world" \
  STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
  STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
  STAGE11CD1_ALLOWED_MODES=P0 STAGE11CD1_ACTIVE_DURATION_S=20.0 \
  "$runner" "$scene"
}
run_one stage15a_vehicle_path_seed303_p0 vehicle_path 303 231
run_one stage15a_mixed_seed1015_p0 human_path_side 1015 232 \
  /workspace/sgcf_nrmp_project/gazebo/overlays/stage15_oracle_mixed/stage15_mixed_random_1015.sdf
run_one stage15a_human_path_center_seed101_p0 human_path_center 101 230
