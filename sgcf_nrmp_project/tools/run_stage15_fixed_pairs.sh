#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
runner="$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh"
scenes=(human_path_center human_path_side vehicle_path semantic_infeasible)
seeds=(101 202 303)
for scene in "${scenes[@]}"; do
  for seed in "${seeds[@]}"; do
    for mode in P0 P2; do
      run_id="fixed_${scene}_seed${seed}_${mode,,}"
      [[ -s "$repo/sgcf_nrmp_project/artifacts/stages/stage_15_oracle_semantic_closed_loop/runtime/$run_id/planner_result.json" ]] && continue
      STAGE11CC_STAGE_DIR=stage_15_oracle_semantic_closed_loop \
      STAGE11CC_RUN_ID="$run_id" STAGE11CC_MODES_OVERRIDE="$mode" \
      STAGE11CC_GAZEBO_SEED="$seed" \
      STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate \
      STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate \
      STAGE11CC_ACTUATOR_SELF_TERMINATES=true \
      STAGE11CD1_ALLOWED_MODES="$mode" STAGE11CD1_ACTIVE_DURATION_S=6.0 \
      "$runner" "$scene"
    done
  done
done
