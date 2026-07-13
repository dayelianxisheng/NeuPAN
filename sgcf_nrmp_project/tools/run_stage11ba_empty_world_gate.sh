#!/usr/bin/env bash
set -euo pipefail

ROOT=/workspace/sgcf_nrmp_project
OUT="$ROOT/artifacts/stages/stage_11b_a_runtime_asset_activation"
LOG="$OUT/logs"
WORLD="$ROOT/gazebo/worlds/empty_world.sdf"
mkdir -p "$LOG"

stdout="$LOG/empty_world_stdout.txt"
stderr="$LOG/empty_world_stderr.txt"
: >"$stdout"
: >"$stderr"

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT "$server_pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$server_pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -TERM "$server_pid" 2>/dev/null || true
  fi
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT

start_ns=$(date +%s%N)
gz sim -s -r "$WORLD" >"$stdout" 2>"$stderr" &
server_pid=$!
echo "$server_pid" >"$LOG/empty_world.pid"

ready=0
for _ in $(seq 1 100); do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  gz topic -l >"$LOG/topics.txt" 2>>"$stderr" || true
  if grep -qx '/scan' "$LOG/topics.txt" &&
     grep -qx '/camera/image_raw' "$LOG/topics.txt" &&
     grep -qx '/odom' "$LOG/topics.txt"; then
    ready=1
    break
  fi
  sleep 0.1
done
ready_ns=$(date +%s%N)

echo "ready=$ready" >"$LOG/gate_status.txt"
echo "server_pid=$server_pid" >>"$LOG/gate_status.txt"
echo "startup_ms=$(( (ready_ns-start_ns)/1000000 ))" >>"$LOG/gate_status.txt"
cat "$LOG/topics.txt" >>"$LOG/gate_status.txt"

if [[ "$ready" -ne 1 ]]; then
  exit 20
fi

for topic in /scan /camera/image_raw /odom /cmd_vel; do
  safe=${topic//\//_}
  gz topic -i -t "$topic" >"$LOG/topic_info${safe}.txt" 2>>"$stderr" || true
done

timeout 15 gz topic -e --json-output -t /scan -n 20 >"$LOG/scan_20.jsonl"
timeout 15 gz topic -e --json-output -t /odom -n 20 >"$LOG/odom_20.jsonl"
timeout 15 gz topic -e -t /camera/image_raw -n 5 >/dev/null

gz model -m sgcf_robot -p >"$LOG/pose_initial.txt" 2>>"$stderr"
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.0}'
sleep 0.3
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.2} angular: {z: 0.0}'
sleep 1
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.0}'
sleep 0.3
gz model -m sgcf_robot -p >"$LOG/pose_after_forward.txt" 2>>"$stderr"
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.3}'
sleep 1
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.0} angular: {z: 0.0}'
sleep 0.5
gz model -m sgcf_robot -p >"$LOG/pose_after_turn.txt" 2>>"$stderr"
timeout 5 gz topic -e --json-output -t /odom -n 5 >"$LOG/odom_after_stop_5.jsonl"

kill -INT "$server_pid" 2>/dev/null || true
wait "$server_pid"
exit_code=$?
server_pid=""
echo "$exit_code" >"$LOG/empty_world.exit_code"
echo false >"$LOG/empty_world.timeout"
if pgrep -af 'gz sim|gz-sim-server' >"$LOG/residual_processes.txt"; then
  echo false >"$LOG/process_cleanup_passed.txt"
  exit 21
fi
echo true >"$LOG/process_cleanup_passed.txt"
