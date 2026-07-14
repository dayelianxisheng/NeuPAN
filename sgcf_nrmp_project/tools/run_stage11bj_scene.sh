#!/usr/bin/env bash
set -u

scene="${1:?scene required}"
run_id="${2:?run id required}"
mode="${3:-full}"
root=/workspace/sgcf_nrmp_project
out="$root/artifacts/stages/stage_11b_j_full_runtime_matrix_rerun/logs/$scene/$run_id"
world="$root/gazebo/worlds/$scene.sdf"
server_pid=""
server_exit="NOT_REAPED"
start_ns=$(date +%s%N)

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT "$server_pid" 2>/dev/null || true
    for _ in $(seq 1 50); do kill -0 "$server_pid" 2>/dev/null || break; sleep 0.1; done
    kill -TERM "$server_pid" 2>/dev/null || true
  fi
  if [[ -n "$server_pid" ]]; then set +e; wait "$server_pid" 2>/dev/null; server_exit=$?; set -e; fi
  ps -eo pid,comm,args | grep -E '[g]z sim|[g]z-sim-server' >"$out/residual_processes.txt" || true
  [[ -s "$out/residual_processes.txt" ]] && cleanup_passed=false || cleanup_passed=true
  python3 -c 'import json,sys; json.dump({"server_exit":sys.argv[1],"signal":None,"timeout":False,"residual_process_count":int(sys.argv[2]),"passed":sys.argv[3]=="true"},open(sys.argv[4],"w"),indent=2)' "$server_exit" "$(wc -l <"$out/residual_processes.txt")" "$cleanup_passed" "$out/cleanup.json"
}
trap cleanup EXIT

mkdir -p "$out"
[[ -f "$world" ]] || exit 2
if ps -eo args | grep -E '[g]z sim|[g]z-sim-server' >/dev/null; then exit 3; fi
env | sort >"$out/environment.txt"
echo "$(hostname)" >"$out/container_id.txt"
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
ready_ns=$(date +%s%N)
[[ "$ready" -eq 1 ]] || exit 30

gz model --list >"$out/entities.txt" 2>>"$out/stderr.txt" || true
timeout 15 gz topic -e --json-output -t "/world/$scene/pose/info" -n 1 >"$out/world_pose_1.jsonl"
for topic in "/world/$scene/clock" /scan /camera/image_raw /camera/camera_info /odom /cmd_vel "/world/$scene/pose/info"; do
  safe=$(printf '%s' "$topic" | tr '/:' '__')
  gz topic -i -t "$topic" >"$out/topic_info_${safe}.txt" 2>&1 || true
done

timeout 15 gz topic -e --json-output -t "/world/$scene/clock" -n 1 >"$out/clock_first.jsonl"; first_clock_ns=$(date +%s%N)
timeout 15 gz topic -e --json-output -t /scan -n 1 >"$out/scan_first.jsonl"; first_lidar_ns=$(date +%s%N)
timeout 15 gz topic -e --json-output -t /camera/image_raw -n 1 >"$out/camera_first.jsonl"; first_camera_ns=$(date +%s%N)
timeout 15 gz topic -e --json-output -t /odom -n 1 >"$out/odom_first.jsonl"; first_odom_ns=$(date +%s%N)

if [[ "$mode" == "full" ]]; then
  timeout 25 gz topic -e --json-output -t /scan -n 20 >"$out/scan_20.jsonl"
  timeout 25 gz topic -e --json-output -t /camera/image_raw -n 5 >"$out/camera_5.jsonl"
  timeout 25 gz topic -e --json-output -t /camera/camera_info -n 1 >"$out/camera_info_1.jsonl"
  timeout 25 gz topic -e --json-output -t /odom -n 20 >"$out/odom_20.jsonl"
  timeout 25 gz topic -e --json-output -t "/world/$scene/clock" -n 20 >"$out/clock_20.jsonl"
fi
timeout 15 gz topic -e --json-output -t "/world/$scene/clock" -n 1 >"$out/clock_last.jsonl"
end_ns=$(date +%s%N)
python3 -c 'import json,sys; ns=lambda x:int(x); json.dump({"scene":sys.argv[1],"run_id":sys.argv[2],"mode":sys.argv[3],"ready":True,"image_id":"sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3","start_ns":ns(sys.argv[4]),"ready_ns":ns(sys.argv[5]),"first_clock_ns":ns(sys.argv[6]),"first_lidar_ns":ns(sys.argv[7]),"first_camera_ns":ns(sys.argv[8]),"first_odometry_ns":ns(sys.argv[9]),"end_ns":ns(sys.argv[10])},open(sys.argv[11],"w"),indent=2)' "$scene" "$run_id" "$mode" "$start_ns" "$ready_ns" "$first_clock_ns" "$first_lidar_ns" "$first_camera_ns" "$first_odom_ns" "$end_ns" "$out/runtime.json"

kill -INT "$server_pid" 2>/dev/null || true
for _ in $(seq 1 50); do
  kill -0 "$server_pid" 2>/dev/null || break
  sleep 0.1
done
kill -TERM "$server_pid" 2>/dev/null || true
for _ in $(seq 1 20); do
  kill -0 "$server_pid" 2>/dev/null || break
  sleep 0.1
done
kill -KILL "$server_pid" 2>/dev/null || true
set +e; wait "$server_pid"; server_exit=$?; set -e
server_pid=""
exit 0
