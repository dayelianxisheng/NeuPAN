#!/usr/bin/env bash
set -u

scene="${1:?scene required}"
root=/workspace/sgcf_nrmp_project
out="$root/artifacts/stages/stage_11b_m_exact_primitive_materialization/logs/$scene"
world="$root/gazebo/worlds/$scene.sdf"
server_pid=""
server_exit="NOT_REAPED"

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT "$server_pid" 2>/dev/null || true
    for _ in $(seq 1 50); do kill -0 "$server_pid" 2>/dev/null || break; sleep 0.1; done
    kill -TERM "$server_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$server_pid" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$server_pid" 2>/dev/null || true
  fi
  if [[ -n "$server_pid" ]]; then set +e; wait "$server_pid" 2>/dev/null; server_exit=$?; set -e; fi
  ps -eo pid,comm,args | awk '$2 ~ /^gz(-sim-server)?$/ {print}' >"$out/residual_processes.txt" || true
  [[ -s "$out/residual_processes.txt" ]] && cleanup_passed=false || cleanup_passed=true
  python3 -c 'import json,sys; json.dump({"server_exit":sys.argv[1],"residual_process_count":int(sys.argv[2]),"passed":sys.argv[3]=="true"},open(sys.argv[4],"w"),indent=2)' "$server_exit" "$(wc -l <"$out/residual_processes.txt")" "$cleanup_passed" "$out/cleanup.json"
}
trap cleanup EXIT

mkdir -p "$out"
[[ -f "$world" ]] || exit 2
if ps -eo pid,comm | awk '$2 ~ /^gz(-sim-server)?$/ {found=1} END {exit !found}'; then exit 3; fi
env | sort >"$out/environment.txt"
hostname >"$out/container_id.txt"
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

gz model --list >"$out/entities.txt" 2>>"$out/stderr.txt" || true
timeout 15 gz topic -e --json-output -t "/world/$scene/pose/info" -n 1 >"$out/world_pose_1.jsonl"
timeout 25 gz topic -e --json-output -t /scan -n 20 >"$out/scan_20.jsonl"
timeout 25 gz topic -e --json-output -t /camera/image_raw -n 5 >"$out/camera_5.jsonl"
timeout 25 gz topic -e --json-output -t /camera/camera_info -n 1 >"$out/camera_info_1.jsonl"
timeout 25 gz topic -e --json-output -t /odom -n 20 >"$out/odom_20.jsonl"
timeout 25 gz topic -e --json-output -t "/world/$scene/clock" -n 20 >"$out/clock_20.jsonl"
python3 -c 'import json,sys; json.dump({"scene":sys.argv[1],"ready":True,"image_id":"sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3"},open(sys.argv[2],"w"),indent=2)' "$scene" "$out/runtime.json"

kill -INT "$server_pid" 2>/dev/null || true
for _ in $(seq 1 50); do kill -0 "$server_pid" 2>/dev/null || break; sleep 0.1; done
kill -TERM "$server_pid" 2>/dev/null || true
for _ in $(seq 1 20); do kill -0 "$server_pid" 2>/dev/null || break; sleep 0.1; done
kill -KILL "$server_pid" 2>/dev/null || true
set +e; wait "$server_pid"; server_exit=$?; set -e
server_pid=""
