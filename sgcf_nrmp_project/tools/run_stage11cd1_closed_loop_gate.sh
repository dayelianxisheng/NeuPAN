#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export STAGE11CC_STAGE_DIR=stage_11c_d1_static_p0_closed_loop
export STAGE11CC_MODE_PROFILE=watchdog
export STAGE11CC_ACTUATOR_MODULE=sgcf_nrmp_bridge.stage11cd1_safe_actuation_gate
export STAGE11CC_ACTUATOR_NODE=stage11cd1_safe_actuation_gate
export STAGE11CC_ACTUATOR_SELF_TERMINATES=true
exec "$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh" empty_world single_static_obstacle
