#!/usr/bin/env bash
set -eo pipefail

export CUDA_VISIBLE_DEVICES=""
export NVIDIA_VISIBLE_DEVICES=void
source /opt/ros/humble/setup.bash

if [[ "${1:-}" == "python" ]]; then
  shift
  exec /opt/sgcf_planner_venv/bin/python "$@"
fi

exec "$@"
