#!/usr/bin/env bash
set -u

ROOT=/workspace/sgcf_nrmp_project
OUT="$ROOT/artifacts/stages/stage_11b_f_hlms_media_restoration"
LOG="$OUT/logs"
WORLD="$ROOT/gazebo/worlds/empty_world.sdf"
server_pid=""
server_exit="NOT_REAPED"

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT "$server_pid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$server_pid" 2>/dev/null || break
      sleep 0.2
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
  printf '%s\n' "$server_exit" >"$LOG/empty_world.exit_code"
  ps -eo pid,comm,args | grep -E '[g]z sim|[g]z-sim-server' >"$LOG/residual_gz_processes.txt" || true
  if [[ -s "$LOG/residual_gz_processes.txt" ]]; then
    echo false >"$LOG/process_cleanup_passed.txt"
  else
    echo true >"$LOG/process_cleanup_passed.txt"
  fi
  if [[ -f /root/.gz/rendering/ogre2.log ]]; then
    cp /root/.gz/rendering/ogre2.log "$LOG/ogre2.log"
  elif [[ ! -f "$LOG/ogre2.log" ]]; then
    echo LOG_NOT_CREATED >"$LOG/ogre2.log"
  fi
}
trap cleanup EXIT

mkdir -p "$LOG"
env | sort >"$LOG/empty_world_environment.txt"
alias="$GZ_RENDERING_PLUGIN_PATH/libgz-rendering-ogre2.so"
{
  echo "alias=$alias"
  echo "alias_target=$(readlink "$alias")"
  echo "alias_resolved=$(readlink -f "$alias")"
  echo "target_sha256=$(sha256sum "$(readlink -f "$alias")" | awk '{print $1}')"
} >"$LOG/alias_prelaunch.txt"
command=(gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 "$WORLD")
printf '%q ' "${command[@]}" >"$LOG/empty_world_command.txt"
printf '\n' >>"$LOG/empty_world_command.txt"
start_ns=$(date +%s%N)
"${command[@]}" >"$LOG/empty_world_stdout.txt" 2>"$LOG/empty_world_stderr.txt" &
server_pid=$!
echo "$server_pid" >"$LOG/empty_world.pid"

ready=0
for _ in $(seq 1 200); do
  if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
  gz topic -l >"$LOG/topic_list.txt" 2>>"$LOG/empty_world_stderr.txt" || true
  if grep -qx '/scan' "$LOG/topic_list.txt" &&
     grep -qx '/camera/image_raw' "$LOG/topic_list.txt" &&
     grep -qx '/odom' "$LOG/topic_list.txt"; then
    ready=1
    break
  fi
  sleep 0.1
done
ready_ns=$(date +%s%N)
{
  echo "ready=$ready"
  echo "server_pid=$server_pid"
  echo "startup_ms=$(( (ready_ns-start_ns)/1000000 ))"
} >"$LOG/gate_status.txt"
if [[ "$ready" -ne 1 ]]; then exit 30; fi

camera_info_topic=$(grep -E '/camera/.*/camera_info$|/camera_info$' "$LOG/topic_list.txt" | head -n 1 || true)
echo "$camera_info_topic" >"$LOG/camera_info_topic.txt"
timeout 15 gz topic -e --json-output -t /world/empty_world/clock -n 20 >"$LOG/clock_20.jsonl"
timeout 15 gz topic -e --json-output -t /scan -n 20 >"$LOG/scan_20.jsonl"
timeout 15 gz topic -e --json-output -t /odom -n 20 >"$LOG/odom_20.jsonl"
timeout 15 gz topic -e --json-output -t /camera/image_raw -n 1 >"$LOG/camera_1.jsonl"
timeout 15 gz topic -e -t /camera/image_raw -n 5 >/dev/null
echo 5 >"$LOG/camera_capture_count.txt"
if [[ -n "$camera_info_topic" ]]; then
  timeout 10 gz topic -e --json-output -t "$camera_info_topic" -n 1 >"$LOG/camera_info_1.jsonl"
fi

gz model -m sgcf_robot -p >"$LOG/pose_initial.txt" 2>>"$LOG/empty_world_stderr.txt"
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.0}'
sleep 0.3
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.2} angular: {z: 0.0}'
sleep 1
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.0}'
sleep 0.5
gz model -m sgcf_robot -p >"$LOG/pose_after_forward.txt" 2>>"$LOG/empty_world_stderr.txt"
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.3}'
sleep 1
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.0}'
sleep 0.5
gz model -m sgcf_robot -p >"$LOG/pose_after_turn.txt" 2>>"$LOG/empty_world_stderr.txt"
timeout 10 gz topic -e --json-output -t /odom -n 5 >"$LOG/odom_after_stop_5.jsonl"

kill -INT "$server_pid" 2>/dev/null || true
set +e
wait "$server_pid"
server_exit=$?
set -e
server_pid=""
exit 0
