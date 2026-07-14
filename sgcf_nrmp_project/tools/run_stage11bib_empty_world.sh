#!/usr/bin/env bash
set -u

world="${1:?world path required}"
out="${2:?output directory required}"
resource_path="${3:?resource path required}"
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
    server_exit=$?
    set -e
  fi
  ps -eo pid,comm,args | grep -E '[g]z sim|[g]z-sim-server' >"$out/residual_processes.txt" || true
  if [[ -s "$out/residual_processes.txt" ]]; then cleanup_passed=false; else cleanup_passed=true; fi
  python3 -c 'import json,sys; json.dump({"server_exit":sys.argv[1],"residual_process_count":int(sys.argv[2]),"passed":sys.argv[3]=="true"},open(sys.argv[4],"w"),indent=2)' \
    "$server_exit" "$(wc -l <"$out/residual_processes.txt")" "$cleanup_passed" "$out/cleanup.json"
}
trap cleanup EXIT

mkdir -p "$out"
if ps -eo args | grep -E '[g]z sim|[g]z-sim-server' >/dev/null; then exit 3; fi
export GZ_SIM_RESOURCE_PATH="$resource_path"
command=(gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 "$world")
printf '%q ' "${command[@]}" >"$out/command.txt"; printf '\n' >>"$out/command.txt"
"${command[@]}" >"$out/stdout.txt" 2>"$out/stderr.txt" &
server_pid=$!

ready=0
for _ in $(seq 1 300); do
  kill -0 "$server_pid" 2>/dev/null || break
  gz topic -l >"$out/topics.txt" 2>>"$out/stderr.txt" || true
  if grep -qx '/scan' "$out/topics.txt" && grep -qx '/camera/image_raw' "$out/topics.txt" && grep -qx '/odom' "$out/topics.txt"; then ready=1; break; fi
  sleep 0.1
done
[[ "$ready" -eq 1 ]] || exit 30

timeout 25 gz topic -e --json-output -t /scan -n 20 >"$out/scan_20.jsonl"
timeout 25 gz topic -e --json-output -t /camera/image_raw -n 5 >"$out/camera_5.jsonl"
timeout 25 gz topic -e --json-output -t /camera/camera_info -n 1 >"$out/camera_info_1.jsonl"
timeout 25 gz topic -e --json-output -t /odom -n 20 >"$out/odom_20.jsonl"
timeout 25 gz topic -e --json-output -t /world/empty_world/clock -n 20 >"$out/clock_20.jsonl"

python3 -c 'import json,sys; json.dump({"ready":True,"world":"empty_world","lidar_requested":20,"camera_requested":5,"odometry_requested":20,"clock_requested":20},open(sys.argv[1],"w"),indent=2)' "$out/runtime.json"
kill -INT "$server_pid" 2>/dev/null || true
set +e
wait "$server_pid"
server_exit=$?
set -e
server_pid=""
exit 0
