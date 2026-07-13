#!/usr/bin/env bash
set -u

scene="${1:?scene id required}"
run_id="${2:-matrix}"
mode="${3:-full}"
root=/workspace/sgcf_nrmp_project
out="$root/artifacts/stages/stage_11b_h_full_runtime_matrix/logs/${scene}/${run_id}"
world="$root/gazebo/worlds/${scene}.sdf"
server_pid=""
server_exit="NOT_REAPED"

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT "$server_pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
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
    if [[ "$server_exit" == "NOT_REAPED" ]]; then server_exit=$code; fi
  fi
  printf '%s\n' "$server_exit" >"$out/exit_code.txt"
  ps -eo pid,comm,args | grep -E '[g]z sim|[g]z-sim-server' >"$out/residual_processes.txt" || true
  if [[ -s "$out/residual_processes.txt" ]]; then echo false >"$out/cleanup_passed.txt"; else echo true >"$out/cleanup_passed.txt"; fi
  if [[ -f /root/.gz/rendering/ogre2.log ]]; then cp /root/.gz/rendering/ogre2.log "$out/ogre2.log"; else echo LOG_NOT_CREATED >"$out/ogre2.log"; fi
}
trap cleanup EXIT

mkdir -p "$out"
if [[ ! -f "$world" ]]; then echo "missing world: $world" >&2; exit 2; fi
if ps -eo args | grep -E '[g]z sim|[g]z-sim-server' >/dev/null; then echo PREEXISTING_GAZEBO_PROCESS >&2; exit 3; fi
env | sort >"$out/environment.txt"
command=(gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 "$world")
printf '%q ' "${command[@]}" >"$out/command.txt"; printf '\n' >>"$out/command.txt"
start_ns=$(date +%s%N)
"${command[@]}" >"$out/stdout.txt" 2>"$out/stderr.txt" &
server_pid=$!
echo "$server_pid" >"$out/pid.txt"

ready=0
for _ in $(seq 1 250); do
  if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
  gz topic -l >"$out/topics.txt" 2>>"$out/stderr.txt" || true
  if grep -qx '/scan' "$out/topics.txt" && grep -qx '/camera/image_raw' "$out/topics.txt" && grep -qx '/odom' "$out/topics.txt"; then ready=1; break; fi
  sleep 0.1
done
ready_ns=$(date +%s%N)
{
  echo "scene=$scene"
  echo "run_id=$run_id"
  echo "mode=$mode"
  echo "ready=$ready"
  echo "server_pid=$server_pid"
  echo "startup_ms=$(( (ready_ns-start_ns)/1000000 ))"
} >"$out/gate_status.txt"
if [[ "$ready" -ne 1 ]]; then exit 30; fi

for topic in "/world/$scene/clock" /scan /camera/image_raw /camera/camera_info /odom /cmd_vel "/world/$scene/pose/info"; do
  safe=$(printf '%s' "$topic" | tr '/:' '__')
  gz topic -i -t "$topic" >"$out/topic_info_${safe}.txt" 2>&1 || true
done

gz model --list >"$out/entities.txt" 2>>"$out/stderr.txt" || true
gz model -m sgcf_robot -p >"$out/robot_pose.txt" 2>>"$out/stderr.txt" || true
gz model -m sgcf_robot -l >"$out/robot_links.txt" 2>>"$out/stderr.txt" || true
gz model -m sgcf_robot -j >"$out/robot_joints.txt" 2>>"$out/stderr.txt" || true
while IFS= read -r model; do
  [[ -n "$model" ]] || continue
  safe=$(printf '%s' "$model" | tr '/:' '__')
  gz model -m "$model" -p >"$out/model_pose_${safe}.txt" 2>>"$out/stderr.txt" || true
done < <(sed -n 's/^[[:space:]]*- //p' "$out/entities.txt")

timeout 15 gz topic -e --json-output -t "/world/$scene/clock" -n 1 >"$out/clock_first.jsonl"
timeout 15 gz topic -e --json-output -t "/world/$scene/pose/info" -n 1 >"$out/world_pose_1.jsonl"
if [[ "$mode" == "full" ]]; then
  timeout 20 gz topic -e --json-output -t /scan -n 20 >"$out/scan_20.jsonl"
  timeout 20 gz topic -e --json-output -t /camera/image_raw -n 5 >"$out/camera_5.jsonl"
  timeout 20 gz topic -e --json-output -t /camera/camera_info -n 1 >"$out/camera_info_1.jsonl"
  timeout 20 gz topic -e --json-output -t /odom -n 20 >"$out/odom_20.jsonl"
  timeout 15 gz topic -e --json-output -t "/world/$scene/clock" -n 20 >"$out/clock_20.jsonl"
  sleep 3
else
  timeout 10 gz topic -e --json-output -t /scan -n 1 >"$out/scan_first.jsonl"
  timeout 10 gz topic -e --json-output -t /camera/image_raw -n 1 >"$out/camera_first.jsonl"
  timeout 10 gz topic -e --json-output -t /odom -n 1 >"$out/odom_first.jsonl"
fi
timeout 15 gz topic -e --json-output -t "/world/$scene/clock" -n 1 >"$out/clock_last.jsonl"

kill -INT "$server_pid" 2>/dev/null || true
set +e
wait "$server_pid"
server_exit=$?
set -e
server_pid=""
exit 0
