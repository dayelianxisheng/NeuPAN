#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$repo/sgcf_nrmp_project/artifacts/stages/stage_11c_a_ros2_bridge_data_plane"
logs="$out/logs/runtime_gate"
gz_name=sgcf_gz_stage11ca
bridge_name=sgcf_ros_bridge_stage11ca
partition=sgcf_stage11ca
gz_image_tag=sgcf-gazebo-harmonic:hlms-media-fix
bridge_image_tag=sgcf-ros2-humble-gzharmonic-bridge:local
gz_image="$(docker image inspect "$gz_image_tag" --format '{{.Id}}')"
bridge_image="$(docker image inspect "$bridge_image_tag" --format '{{.Id}}')"

mkdir -p "$logs"

cleanup() {
  set +e
  docker logs "$bridge_name" >"$logs/bridge_stdout.txt" 2>"$logs/bridge_stderr.txt"
  docker logs "$gz_name" >"$logs/gazebo_stdout.txt" 2>"$logs/gazebo_stderr.txt"
  docker stop --time 10 "$bridge_name" "$gz_name" >"$logs/container_stop.txt" 2>&1
  docker rm "$bridge_name" "$gz_name" >"$logs/container_remove.txt" 2>&1
  docker ps -a --format '{{.Names}}' | grep -E "^(${gz_name}|${bridge_name})$" >"$logs/residual_stage_containers.txt"
  set -e
}
trap cleanup EXIT

for name in "$gz_name" "$bridge_name"; do
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    echo "Stage container already exists: $name" >&2
    exit 2
  fi
done

docker image inspect "$gz_image" >"$logs/gazebo_image_inspect.json"
docker image inspect "$bridge_image" >"$logs/bridge_image_inspect.json"
printf '%s\n' "$gz_image" >"$logs/gazebo_immutable_image_id.txt"
printf '%s\n' "$bridge_image" >"$logs/bridge_immutable_image_id.txt"

docker run -d \
  --name "$gz_name" \
  --network host \
  -e "GZ_PARTITION=$partition" \
  -v "$repo:/workspace" \
  -w /workspace \
  "$gz_image" \
  bash -lc 'exec gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 /workspace/sgcf_nrmp_project/gazebo/worlds/empty_world.sdf' \
  >"$logs/gazebo_container_id.txt"

ready=false
for _ in $(seq 1 300); do
  docker exec "$gz_name" bash -lc 'gz topic -l' >"$logs/gz_topics.txt" 2>/dev/null || true
  if grep -qx /scan "$logs/gz_topics.txt" \
    && grep -qx /camera/image_raw "$logs/gz_topics.txt" \
    && grep -qx /camera/camera_info "$logs/gz_topics.txt" \
    && grep -qx /odom "$logs/gz_topics.txt" \
    && grep -qx /cmd_vel "$logs/gz_topics.txt"; then
    ready=true
    break
  fi
  sleep .1
done
test "$ready" = true

docker run -d \
  --name "$bridge_name" \
  --network host \
  -e ROS_DOMAIN_ID=42 \
  -e "GZ_PARTITION=$partition" \
  "$bridge_image" \
  bash -lc 'source /opt/ros/humble/setup.bash; exec ros2 run ros_gz_bridge parameter_bridge "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image" "/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo" "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"' \
  >"$logs/bridge_container_id.txt"

bridge_ready=false
for _ in $(seq 1 200); do
  docker exec "$bridge_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic list -t' >"$logs/ros_topics.txt" 2>/dev/null || true
  if grep -q '^/scan ' "$logs/ros_topics.txt" \
    && grep -q '^/camera/image_raw ' "$logs/ros_topics.txt" \
    && grep -q '^/camera/camera_info ' "$logs/ros_topics.txt" \
    && grep -q '^/odom ' "$logs/ros_topics.txt" \
    && grep -q '^/cmd_vel ' "$logs/ros_topics.txt"; then
    bridge_ready=true
    break
  fi
  sleep .1
done
test "$bridge_ready" = true

for topic in clock scan camera/image_raw camera/camera_info odom; do
  safe="${topic//\//_}"
  docker exec "$bridge_name" bash -lc "source /opt/ros/humble/setup.bash; timeout 20 ros2 topic echo /$topic --once" \
    >"$logs/ros_${safe}_once.yaml"
done

capture_for() {
  local topic="$1"
  local seconds="$2"
  local output="$3"
  set +e
  docker exec "$bridge_name" bash -lc \
    "source /opt/ros/humble/setup.bash; timeout $seconds ros2 topic echo $topic" \
    >"$output"
  local code=$?
  set -e
  test "$code" -eq 124
}

capture_for /clock 7 "$logs/ros_clock_stream.yaml"
capture_for /scan 4 "$logs/ros_scan_stream.yaml"
capture_for /camera/image_raw 2 "$logs/ros_camera_image_raw_stream.yaml"
capture_for /odom 2 "$logs/ros_odom_stream.yaml"

docker exec "$gz_name" bash -lc 'timeout 15 gz topic -e --json-output -t /world/empty_world/pose/info -n 1' \
  >"$logs/pose_before_zero.jsonl"
docker exec "$bridge_name" bash -lc "source /opt/ros/humble/setup.bash; ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'" \
  >"$logs/zero_twist_publish.txt"
sleep 1
docker exec "$gz_name" bash -lc 'timeout 15 gz topic -e --json-output -t /world/empty_world/pose/info -n 1' \
  >"$logs/pose_after_zero.jsonl"

docker exec "$bridge_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 node list; ros2 topic list -t' \
  >"$logs/ros_graph.txt"

echo 'STAGE_11C_A_RUNTIME_GATE_CAPTURE_COMPLETE'
