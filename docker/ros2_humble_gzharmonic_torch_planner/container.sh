#!/usr/bin/env bash
set -euo pipefail

image="sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

case "${1:-check}" in
  check)
    docker image inspect "$image" --format '{{.Id}}'
    docker run --rm --network none \
      -e CUDA_VISIBLE_DEVICES= -e NVIDIA_VISIBLE_DEVICES=void \
      -v "$repo:/workspace:ro" -w /workspace "$image" \
      python -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.device("cpu"))'
    ;;
  shell)
    exec docker run --rm -it --network none \
      -e CUDA_VISIBLE_DEVICES= -e NVIDIA_VISIBLE_DEVICES=void \
      -v "$repo:/workspace:ro" -w /workspace "$image" bash
    ;;
  *)
    echo "Usage: $0 {check|shell}" >&2
    exit 2
    ;;
esac
