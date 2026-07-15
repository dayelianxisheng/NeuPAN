#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
manifest="$repo/sgcf_nrmp_project/gazebo/overlays/stage15c_feasible_semantics/manifest.json"
runner="$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh"
stage=stage_15c_oracle_semantic_reevaluation
filter=${STAGE15C_SCENE_FILTER:-}
seed_start=${STAGE15C_SEED_START:-1}
seed_end=${STAGE15C_SEED_END:-10}
while IFS= read -r row; do
  scene=$(jq -r .scene_id <<<"$row")
  [[ -n "$filter" && "$scene" != "$filter" ]] && continue
  case "$scene" in
    stage15c_human_side_feasible) scene_index=0 ;;
    stage15c_vehicle_side_feasible) scene_index=1 ;;
    stage15c_mixed_feasible) scene_index=2 ;;
    *) echo "unsupported scene: $scene" >&2; exit 2 ;;
  esac
  world=/workspace/$(jq -r .world <<<"$row")
  duration=$(jq -r .control_window_s <<<"$row")
  reference=$(jq -c .reference_waypoints <<<"$row")
  oracle=$(jq -c '[.obstacles[] | {name,class_name,center}]' <<<"$row")
  for seed_offset in $(seq "$seed_start" "$seed_end"); do
    seed=$((1100 + seed_offset))
    for mode_index in 0 1; do
      if [[ "$mode_index" == 0 ]]; then mode=P0; else mode=P2; fi
      run_id="paired_${scene}_seed${seed}_${mode,,}"
      [[ -s "$repo/sgcf_nrmp_project/artifacts/stages/$stage/runtime/$run_id/planner_result.json" ]] && continue
      domain=$((10 + scene_index * 40 + seed_offset * 2 + mode_index))
      STAGE11CC_STAGE_DIR="$stage" STAGE11CC_RUN_ID="$run_id" STAGE11CC_MODES_OVERRIDE="$mode" \
      STAGE11CC_GAZEBO_SEED="$seed" STAGE11CC_GZ_PARTITION="sgcf_${scene}_${seed}_${mode,,}" \
      STAGE11CC_ROS_DOMAIN_ID="$domain" STAGE11CC_WORLD_PATH="$world" \
      STAGE15_SCENE_LABEL="$scene" STAGE15_ORACLE_MAP_JSON="$oracle" \
      STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
      STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
      STAGE11CD1_ALLOWED_MODES="$mode" STAGE11CD1_ACTIVE_DURATION_S="$duration" \
      STAGE15B_EVALUATION_DURATION_S="$duration" STAGE15B_GOAL_TOLERANCE_M=0.25 \
      STAGE15B_REFERENCE_WAYPOINTS_JSON="$reference" STAGE15B_WALL_TIMEOUT_S=240 \
      "$runner" human_path_side
    done
  done
done < <(jq -c '.scenarios[]' "$manifest")
