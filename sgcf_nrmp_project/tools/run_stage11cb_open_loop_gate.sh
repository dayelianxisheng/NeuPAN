#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
project="$repo/sgcf_nrmp_project"
out="$project/artifacts/stages/stage_11c_b_open_loop_command"
logs="$out/logs"
stage11ca="$project/artifacts/stages/stage_11c_a_ros2_bridge_data_plane"
gz_name=sgcf_gz_stage11cb
bridge_name=sgcf_ros_bridge_stage11cb
partition=sgcf_stage11ca
ros_domain_id=42
node_pid=""
capture_pid=""

mkdir -p "$logs"
gz_image="$(cat "$stage11ca/logs/runtime_gate/gazebo_immutable_image_id.txt")"
bridge_image="$(cat "$stage11ca/logs/runtime_gate/bridge_immutable_image_id.txt")"

cleanup() {
  set +e
  if docker ps --format '{{.Names}}' | grep -qx "$bridge_name"; then
    docker exec "$bridge_name" bash -lc \
      "source /opt/ros/humble/setup.bash; timeout 5 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'" \
      >>"$logs/final_zero_cleanup.txt" 2>&1
  fi
  [[ -z "$node_pid" ]] || kill -TERM "$node_pid" 2>/dev/null
  [[ -z "$capture_pid" ]] || kill -TERM "$capture_pid" 2>/dev/null
  [[ -z "$node_pid" ]] || wait "$node_pid" 2>/dev/null
  [[ -z "$capture_pid" ]] || wait "$capture_pid" 2>/dev/null
  docker logs "$bridge_name" >"$logs/bridge_stdout.txt" 2>"$logs/bridge_stderr.txt"
  docker logs "$gz_name" >"$logs/gazebo_stdout.txt" 2>"$logs/gazebo_stderr.txt"
  docker stop --timeout 10 "$bridge_name" "$gz_name" >"$logs/container_stop.txt" 2>&1
  docker rm "$bridge_name" "$gz_name" >"$logs/container_remove.txt" 2>&1
  docker ps -a --format '{{.Names}}' | grep -E "^(${gz_name}|${bridge_name})$" >"$logs/residual_stage_containers.txt"
  ps -eo pid,comm,args | grep -E 'gz sim|parameter_bridge|stage11cb_open_loop_audit' | grep -v grep >"$logs/residual_host_processes.txt"
  set -e
}
trap cleanup EXIT

for image in "$gz_image" "$bridge_image"; do
  docker image inspect "$image" >/dev/null
done
for name in "$gz_name" "$bridge_name"; do
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    echo "Stage container already exists: $name" >&2
    exit 2
  fi
done

printf '%s\n' "$gz_image" >"$logs/gazebo_immutable_image_id.txt"
printf '%s\n' "$bridge_image" >"$logs/bridge_immutable_image_id.txt"
docker image inspect "$gz_image" >"$logs/gazebo_image_inspect.json"
docker image inspect "$bridge_image" >"$logs/bridge_image_inspect.json"

docker run -d \
  --name "$gz_name" \
  --network host \
  -e "GZ_PARTITION=$partition" \
  -v "$repo:/workspace" \
  -w /workspace \
  "$gz_image" \
  bash -lc 'exec gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 /workspace/sgcf_nrmp_project/gazebo/worlds/empty_world.sdf' \
  >"$logs/gazebo_container_id.txt"

gz_ready=false
for _ in $(seq 1 300); do
  docker exec "$gz_name" bash -lc 'gz topic -l' >"$logs/gz_topic_list.txt" 2>/dev/null || true
  if grep -qx /scan "$logs/gz_topic_list.txt" \
    && grep -qx /camera/image_raw "$logs/gz_topic_list.txt" \
    && grep -qx /camera/camera_info "$logs/gz_topic_list.txt" \
    && grep -qx /odom "$logs/gz_topic_list.txt" \
    && grep -qx /cmd_vel "$logs/gz_topic_list.txt"; then
    gz_ready=true
    break
  fi
  sleep .1
done
test "$gz_ready" = true

docker run -d \
  --name "$bridge_name" \
  --network host \
  -e "ROS_DOMAIN_ID=$ros_domain_id" \
  -e "GZ_PARTITION=$partition" \
  -v "$repo:/workspace" \
  -w /workspace \
  "$bridge_image" \
  bash -lc 'source /opt/ros/humble/setup.bash; exec ros2 run ros_gz_bridge parameter_bridge "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image" "/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo" "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"' \
  >"$logs/bridge_container_id.txt"

bridge_ready=false
for _ in $(seq 1 200); do
  docker exec "$bridge_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic list -t' >"$logs/ros_topic_list.txt" 2>/dev/null || true
  if grep -q '^/clock ' "$logs/ros_topic_list.txt" \
    && grep -q '^/scan ' "$logs/ros_topic_list.txt" \
    && grep -q '^/camera/image_raw ' "$logs/ros_topic_list.txt" \
    && grep -q '^/camera/camera_info ' "$logs/ros_topic_list.txt" \
    && grep -q '^/odom ' "$logs/ros_topic_list.txt" \
    && grep -q '^/cmd_vel ' "$logs/ros_topic_list.txt"; then
    bridge_ready=true
    break
  fi
  sleep .1
done
test "$bridge_ready" = true

docker exec "$gz_name" bash -lc \
  'timeout 55 gz topic -e --json-output -t /cmd_vel' \
  >"$logs/cmd_vel_gz.txt" 2>"$logs/cmd_vel_gz_stderr.txt" &
capture_pid=$!

docker exec "$bridge_name" bash -lc \
  'source /opt/ros/humble/setup.bash; export PYTHONPATH=/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bridge:${PYTHONPATH:-}; export STAGE11CB_LOG_DIR=/workspace/sgcf_nrmp_project/artifacts/stages/stage_11c_b_open_loop_command/logs; exec python3 -m sgcf_nrmp_bridge.stage11cb_open_loop_audit' \
  >"$logs/open_loop_node_stdout.txt" 2>"$logs/open_loop_node_stderr.txt" &
node_pid=$!

node_ready=false
for _ in $(seq 1 200); do
  docker exec "$bridge_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 node list' >"$logs/ros_node_list.txt" 2>/dev/null || true
  if grep -qx /stage11cb_open_loop_audit "$logs/ros_node_list.txt"; then
    node_ready=true
    break
  fi
  sleep .05
done
test "$node_ready" = true

for topic in /clock /scan /camera/image_raw /camera/camera_info /odom /cmd_vel; do
  safe="${topic//\//_}"
  docker exec "$bridge_name" bash -lc \
    "source /opt/ros/humble/setup.bash; ros2 topic info -v $topic" \
    >"$logs/ros_topic_info${safe}.txt"
done
docker exec "$gz_name" bash -lc 'gz topic -i -t /cmd_vel' >"$logs/gz_cmd_vel_info.txt" 2>&1 || true

deadline=$((SECONDS + 65))
while kill -0 "$node_pid" 2>/dev/null; do
  if (( SECONDS >= deadline )); then
    echo 'Audit node exceeded wall-clock timeout' >&2
    exit 40
  fi
  sleep .1
done
set +e
wait "$node_pid"
node_exit=$?
set -e
node_pid=""
printf '%s\n' "$node_exit" >"$logs/open_loop_node_exit_code.txt"
test "$node_exit" -eq 0

sleep 1
if [[ -n "$capture_pid" ]]; then
  kill -TERM "$capture_pid" 2>/dev/null || true
  wait "$capture_pid" 2>/dev/null || true
  capture_pid=""
fi

docker exec "$bridge_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 node list; ros2 topic list -t' >"$logs/final_ros_graph.txt"
echo 'STAGE_11C_B_OPEN_LOOP_CAPTURE_COMPLETE'
