#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
out="$repo/sgcf_nrmp_project/artifacts/stages/stage_14_external_depot_scene"
cache="/home/zq/.cache/sgcf_nrmp/vendor/depot/337924487ba19259ef46b7d1737c3c69df61cde1f85657c418ac13c23d948e1c"
world="/workspace/sgcf_nrmp_project/gazebo/overlays/depot/depot_stage14.sdf"
gz_image=$(cat "$repo/sgcf_nrmp_project/artifacts/stages/stage_13_minimal_gazebo_sensor_world/logs/gazebo_image_id.txt")
bridge_image=$(cat "$repo/sgcf_nrmp_project/artifacts/stages/stage_13_minimal_gazebo_sensor_world/logs/bridge_image_id.txt")
mkdir -p "$out/logs" "$out/runtime"
current_gz=""; current_bridge=""

cleanup_round() {
  docker stop -t 10 "$2" "$1" >/dev/null 2>&1 || true
  docker rm "$2" "$1" >/dev/null 2>&1 || true
}
cleanup_active() { [[ -z "$current_gz" ]] || cleanup_round "$current_gz" "$current_bridge"; }
trap cleanup_active EXIT

for mode in zero motion; do
  gz_name="sgcf_gz_stage14_${mode}"; bridge_name="sgcf_bridge_stage14_${mode}"
  current_gz="$gz_name"; current_bridge="$bridge_name"
  partition="sgcf_stage14_${mode}"; domain=$([[ $mode == zero ]] && echo 83 || echo 84)
  log="$out/logs/$mode"; runtime="$out/runtime/$mode"; mkdir -p "$log" "$runtime"
  cleanup_round "$gz_name" "$bridge_name"
  docker run -d --name "$gz_name" --network host -e GZ_PARTITION="$partition" \
    -e GZ_SIM_RESOURCE_PATH=/vendor_cache:/workspace/sgcf_nrmp_project/gazebo/models \
    -v "$repo:/workspace:ro" -v "$out:/workspace/sgcf_nrmp_project/artifacts/stages/stage_14_external_depot_scene" \
    -v "$cache:/vendor_cache:ro" "$gz_image" \
    bash -lc "exec gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 '$world'" >"$log/gazebo_container_id.txt"
  ready=false
  for _ in $(seq 1 900); do
    docker exec "$gz_name" bash -lc 'gz topic -l' >"$log/gz_topics.txt" 2>/dev/null || true
    if grep -qx /scan "$log/gz_topics.txt" && grep -qx /camera/image_raw "$log/gz_topics.txt" && grep -qx /camera/camera_info "$log/gz_topics.txt" && grep -qx /odom "$log/gz_topics.txt" && grep -qx /cmd_vel "$log/gz_topics.txt"; then ready=true; break; fi
    sleep .1
  done
  test "$ready" = true
  docker run -d --name "$bridge_name" --network host -e ROS_DOMAIN_ID="$domain" -e GZ_PARTITION="$partition" \
    -v "$repo:/workspace:ro" -v "$out:/workspace/sgcf_nrmp_project/artifacts/stages/stage_14_external_depot_scene" \
    -w /workspace "$bridge_image" bash -lc \
    'source /opt/ros/humble/setup.bash; exec ros2 run ros_gz_bridge parameter_bridge "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image" "/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo" "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"' >"$log/bridge_container_id.txt"
  ready=false
  for _ in $(seq 1 200); do
    docker exec "$bridge_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic list -t' >"$log/ros_topics.txt" 2>/dev/null || true
    if grep -q '^/clock ' "$log/ros_topics.txt" && grep -q '^/scan ' "$log/ros_topics.txt" && grep -q '^/camera/image_raw ' "$log/ros_topics.txt" && grep -q '^/camera/camera_info ' "$log/ros_topics.txt" && grep -q '^/odom ' "$log/ros_topics.txt" && grep -q '^/cmd_vel ' "$log/ros_topics.txt"; then ready=true; break; fi
    sleep .1
  done
  test "$ready" = true
  docker exec "$gz_name" bash -lc 'timeout 90 gz topic -e --json-output -t /cmd_vel' >"$log/cmd_vel_gz.jsonl" 2>"$log/cmd_vel_gz_stderr.txt" & capture=$!
  set +e
  docker exec -e ROS_DOMAIN_ID="$domain" -e STAGE13_MODE="$mode" -e STAGE13_OUT="/workspace/sgcf_nrmp_project/artifacts/stages/stage_14_external_depot_scene/runtime/$mode" "$bridge_name" bash -lc \
    'source /opt/ros/humble/setup.bash; export PYTHONPATH=/workspace/sgcf_nrmp_project/tools:${PYTHONPATH:-}; exec python3 /workspace/sgcf_nrmp_project/tools/stage13_sensor_command_audit.py' >"$log/audit_stdout.txt" 2>"$log/audit_stderr.txt"
  status=$?
  set -e
  kill -TERM "$capture" 2>/dev/null || true; wait "$capture" 2>/dev/null || true
  docker logs "$gz_name" >"$log/gazebo_stdout.txt" 2>"$log/gazebo_stderr.txt"
  docker logs "$bridge_name" >"$log/bridge_stdout.txt" 2>"$log/bridge_stderr.txt"
  cleanup_round "$gz_name" "$bridge_name"; current_gz=""; current_bridge=""
  printf '%s\n' "$status" >"$log/audit_exit_code.txt"; test "$status" -eq 0
  docker ps -a --format '{{.Names}}' | grep -E "^(${gz_name}|${bridge_name})$" >"$log/residual_containers.txt" || true
done
docker ps -a --format '{{.Names}}' | grep '^sgcf_.*stage14_' >"$out/logs/residual_containers.txt" || true
pgrep -af 'stage13_sensor_command_audit|gz sim.*depot_stage14|parameter_bridge' >"$out/logs/residual_processes.txt" || true
printf '%s\n' "$gz_image" >"$out/logs/gazebo_image_id.txt"
printf '%s\n' "$bridge_image" >"$out/logs/bridge_image_id.txt"
