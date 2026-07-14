#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export STAGE11CC_STAGE_DIR=stage_11c_c2_deadline_watchdog
export STAGE11CC_MODE_PROFILE=watchdog
exec "$repo/sgcf_nrmp_project/tools/run_stage11cc_shadow_gate.sh" \
  single_static_obstacle human_path_center semantic_infeasible
