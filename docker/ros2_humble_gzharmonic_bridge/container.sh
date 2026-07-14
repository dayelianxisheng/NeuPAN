#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  build) docker build -t sgcf-ros2-humble-gzharmonic-bridge:local "$root" ;;
  *) echo "usage: $0 build" >&2; exit 2 ;;
esac
