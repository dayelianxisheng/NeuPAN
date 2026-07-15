#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
runner="$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh"
manifest="$repo/sgcf_nrmp_project/gazebo/overlays/stage15_oracle_mixed/manifest.json"
shard="${1:-0}"; shard_count="${2:-1}"
python "$repo/sgcf_nrmp_project/tools/generate_stage15_mixed_worlds.py"
python - "$manifest" <<'PY' | while IFS=$'\t' read -r group seed scene world oracle; do
import json,sys
d=json.load(open(sys.argv[1]))
for row in d['scenarios']:
 print(row['group'],row['seed'],row['scene_id'],'/workspace/'+row['world'],json.dumps([{'name':x['name'],'class_name':x['class_name'],'center':x['center']} for x in row['obstacles']],separators=(',',':')),sep='\t')
PY
  (( seed % shard_count == shard )) || continue
  for mode in P0 P2; do
    run_id="${group}_${scene}_${mode,,}"
    domain=$((100 + seed % 50)); [[ "$mode" == P2 ]] && domain=$((domain + 50))
    [[ -s "$repo/sgcf_nrmp_project/artifacts/stages/stage_15_oracle_semantic_closed_loop/runtime/$run_id/planner_result.json" ]] && continue
    STAGE11CC_STAGE_DIR=stage_15_oracle_semantic_closed_loop \
    STAGE11CC_RUN_ID="$run_id" STAGE11CC_MODES_OVERRIDE="$mode" STAGE11CC_GAZEBO_SEED="$seed" \
    STAGE11CC_GZ_PARTITION="sgcf_stage15_${seed}_${mode,,}" STAGE11CC_ROS_DOMAIN_ID="$domain" \
    STAGE11CC_WORLD_PATH="$world" STAGE15_SCENE_LABEL="$scene" STAGE15_ORACLE_MAP_JSON="$oracle" \
    STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
    STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
    STAGE11CD1_ALLOWED_MODES="$mode" STAGE11CD1_ACTIVE_DURATION_S=6.0 \
    "$runner" human_path_side
  done
done
