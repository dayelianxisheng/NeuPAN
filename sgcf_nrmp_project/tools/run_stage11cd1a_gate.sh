#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export STAGE11CC_STAGE_DIR=stage_11c_d1a_speed_contract_and_geometry_diagnosis
export STAGE11CC_MODE_PROFILE=watchdog

# Empty-world is the only authorized nonzero closed-loop run.
export STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate
export STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate
export STAGE11CC_ACTUATOR_SELF_TERMINATES=true
export STAGE11CD1_ACTIVE_DURATION_S=8.0
"$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh" empty_world

# Single-static is diagnosis-only under an independent hard-zero guard.
export STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cc_zero_guard
export STAGE11CC_ACTUATOR_NODE=stage11cc_zero_guard
export STAGE11CC_ACTUATOR_SELF_TERMINATES=false
unset STAGE11CD1_ACTIVE_DURATION_S
"$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh" single_static_obstacle
