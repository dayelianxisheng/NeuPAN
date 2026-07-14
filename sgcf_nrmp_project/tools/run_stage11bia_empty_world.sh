#!/usr/bin/env bash
set -u

world="${1:?world path required}"
out="${2:?output directory required}"
resource_path="${3:-/workspace/sgcf_nrmp_project/gazebo/models}"
server_pid=""
server_exit="NOT_REAPED"

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT "$server_pid" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 "$server_pid" 2>/dev/null || break
      sleep 0.1
    done
    kill -TERM "$server_pid" 2>/dev/null || true
  fi
  if [[ -n "$server_pid" ]]; then
    set +e
    wait "$server_pid" 2>/dev/null
    code=$?
    set -e
    [[ "$server_exit" == "NOT_REAPED" ]] && server_exit=$code
  fi
  printf '%s\n' "$server_exit" >"$out/exit_code.txt"
  ps -eo pid,comm,args | grep -E '[g]z sim|[g]z-sim-server' >"$out/residual_processes.txt" || true
  [[ -s "$out/residual_processes.txt" ]] && echo false >"$out/cleanup_passed.txt" || echo true >"$out/cleanup_passed.txt"
  [[ -f /root/.gz/rendering/ogre2.log ]] && cp /root/.gz/rendering/ogre2.log "$out/ogre2.log"
}
trap cleanup EXIT

mkdir -p "$out"
[[ -f "$world" ]] || { echo "missing world: $world" >&2; exit 2; }
if ps -eo args | grep -E '[g]z sim|[g]z-sim-server' >/dev/null; then
  echo PREEXISTING_GAZEBO_PROCESS >&2
  exit 3
fi

export GZ_SIM_RESOURCE_PATH="$resource_path"
env | sort >"$out/environment.txt"
command=(gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 "$world")
printf '%q ' "${command[@]}" >"$out/command.txt"; printf '\n' >>"$out/command.txt"
"${command[@]}" >"$out/stdout.txt" 2>"$out/stderr.txt" &
server_pid=$!
echo "$server_pid" >"$out/pid.txt"

ready=0
for _ in $(seq 1 300); do
  kill -0 "$server_pid" 2>/dev/null || break
  gz topic -l >"$out/topics.txt" 2>>"$out/stderr.txt" || true
  if grep -qx '/scan' "$out/topics.txt" && grep -qx '/camera/image_raw' "$out/topics.txt" && grep -qx '/odom' "$out/topics.txt"; then
    ready=1
    break
  fi
  sleep 0.1
done
echo "ready=$ready" >"$out/gate_status.txt"
[[ "$ready" -eq 1 ]] || exit 30

timeout 25 gz topic -e --json-output -t /scan -n 20 >"$out/scan_20.jsonl"
timeout 25 gz topic -e --json-output -t /camera/image_raw -n 5 >"$out/camera_5.jsonl"
timeout 25 gz topic -e --json-output -t /odom -n 20 >"$out/odom_20.jsonl"

kill -INT "$server_pid" 2>/dev/null || true
set +e
wait "$server_pid"
server_exit=$?
set -e
server_pid=""
exit 0
