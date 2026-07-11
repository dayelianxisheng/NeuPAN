#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
baseline="579e7afa239cd7ff61f7f63fbd4aaaecbb136d3b"
protected=(neupan neupan_ros neupan_ros2 example docker)

git -C "$root" cat-file -e "${baseline}^{commit}"
echo "baseline=$baseline"
echo "baseline_tree=$(git -C "$root" rev-parse "${baseline}^{tree}")"
echo "current_head=$(git -C "$root" rev-parse HEAD)"
echo "Known differences from the baseline are reported, not repaired:"
git -C "$root" diff --name-status "$baseline"..HEAD -- "${protected[@]}" || true
echo "Working-tree status in protected paths:"
git -C "$root" status --short -- "${protected[@]}" || true
