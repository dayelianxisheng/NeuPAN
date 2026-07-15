#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
stage_dir="${STAGE11CC_STAGE_DIR:-stage_11c_c_planner_shadow_mode}"
out="$repo/sgcf_nrmp_project/artifacts/stages/$stage_dir"
planner_tag=sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1
gazebo_tag=sgcf-gazebo-harmonic:hlms-media-fix
planner_image="${STAGE11CC_PLANNER_IMAGE:-$(docker image inspect "$planner_tag" --format '{{.Id}}')}"
gazebo_image="${STAGE11CC_GAZEBO_IMAGE:-$(docker image inspect "$gazebo_tag" --format '{{.Id}}')}"
partition=sgcf_stage11ca
domain=42
all_scenes=(empty_world single_static_obstacle static_corridor narrow_passage robot_obstacle human_path_center human_path_side vehicle_path semantic_infeasible initial_collision rgb_dropout_contract outdated_rgb_contract)
scenes=("${@:-${all_scenes[@]}}")

docker image inspect "$planner_image" >/dev/null
docker image inspect "$gazebo_image" >/dev/null
mkdir -p "$out/logs" "$out/planner_inputs"

for scene in "${scenes[@]}"; do
  case " ${all_scenes[*]} " in *" $scene "*) ;; *) echo "Unauthorized scene: $scene" >&2; exit 2;; esac
  run_id="${STAGE11CC_RUN_ID:-$scene}"
  logs="$out/logs/$run_id"
  scene_out="$out/runtime/$run_id"
  mode_list=""
  if [[ "${STAGE11CC_MODE_PROFILE:-}" == watchdog ]]; then
    case "$scene" in
      single_static_obstacle|static_corridor|narrow_passage|robot_obstacle) mode_list=P0 ;;
      human_path_center|semantic_infeasible) mode_list=P1,P2 ;;
    esac
  fi
  if [[ -n "${STAGE11CC_MODES_OVERRIDE:-}" ]]; then
    mode_list="$STAGE11CC_MODES_OVERRIDE"
  fi
  actuator_module="${STAGE11CC_ACTUATOR_MODULE:-sgcf_nrmp_bridge.stage11cc_zero_guard}"
  actuator_node="${STAGE11CC_ACTUATOR_NODE:-stage11cc_zero_guard}"
  container_id="${run_id//[^a-zA-Z0-9_.-]/_}"
  gz_name="sgcf_gz_stage11cc_${container_id}"
  ros_name="sgcf_ros_stage11cc_${container_id}"
  bridge_pid="" guard_pid="" planner_pid="" capture_pid=""
  if [[ -e "$scene_out" || -e "$logs" ]]; then
    docker run --rm --entrypoint chmod -v "$repo:/workspace" "$planner_image" \
      -R a+rwX "/workspace/sgcf_nrmp_project/artifacts/stages/$stage_dir/runtime/$run_id" \
      "/workspace/sgcf_nrmp_project/artifacts/stages/$stage_dir/logs/$run_id" 2>/dev/null || true
  fi
  rm -rf "$logs" "$scene_out"
  mkdir -p "$logs" "$scene_out"

  cleanup_scene() {
    set +e
    if [[ -n "$planner_pid" ]]; then kill -TERM "$planner_pid" 2>/dev/null; wait "$planner_pid" 2>/dev/null; fi
    if [[ -n "$guard_pid" ]]; then kill -TERM "$guard_pid" 2>/dev/null; wait "$guard_pid" 2>/dev/null; fi
    if [[ -n "$bridge_pid" ]]; then kill -TERM "$bridge_pid" 2>/dev/null; wait "$bridge_pid" 2>/dev/null; fi
    if [[ -n "$capture_pid" ]]; then kill -TERM "$capture_pid" 2>/dev/null; wait "$capture_pid" 2>/dev/null; fi
    docker logs "$ros_name" >"$logs/ros_container_stdout.txt" 2>"$logs/ros_container_stderr.txt" || true
    docker logs "$gz_name" >"$logs/gazebo_stdout.txt" 2>"$logs/gazebo_stderr.txt" || true
    docker stop --timeout 10 "$ros_name" "$gz_name" >"$logs/container_stop.txt" 2>&1 || true
    docker rm -f "$ros_name" "$gz_name" >"$logs/container_remove.txt" 2>&1 || true
    docker ps -a --format '{{.Names}}' | grep -E "^(${gz_name}|${ros_name})$" >"$logs/residual_containers.txt" || true
    ps -eo pid,comm,args | grep -E "${scene}|stage11cc|parameter_bridge" | grep -v grep >"$logs/residual_processes.txt" || true
    set -e
  }
  trap cleanup_scene EXIT

  docker rm -f "$gz_name" "$ros_name" >/dev/null 2>&1 || true
  printf '%s\n' "$gazebo_image" >"$logs/gazebo_image_id.txt"
  printf '%s\n' "$planner_image" >"$logs/planner_image_id.txt"
  docker run -d --name "$gz_name" --network host \
    -e "GZ_PARTITION=$partition" -v "$repo:/workspace" -w /workspace \
    "$gazebo_image" bash -lc \
    "exec gz sim -s -r --headless-rendering --render-engine-server ogre2 -v 4 /workspace/sgcf_nrmp_project/gazebo/worlds/${scene}.sdf" \
    >"$logs/gazebo_container_id.txt"

  ready=false
  for _ in $(seq 1 400); do
    docker exec "$gz_name" bash -lc 'gz topic -l' >"$logs/gz_topics.txt" 2>/dev/null || true
    if grep -qx /scan "$logs/gz_topics.txt" && grep -qx /odom "$logs/gz_topics.txt" \
      && grep -qx /cmd_vel "$logs/gz_topics.txt" && grep -qx /camera/camera_info "$logs/gz_topics.txt"; then ready=true; break; fi
    sleep .1
  done
  test "$ready" = true

  docker run -d --name "$ros_name" --network host \
    -e "ROS_DOMAIN_ID=$domain" -e "GZ_PARTITION=$partition" \
    -e 'CUDA_VISIBLE_DEVICES=' -e 'NVIDIA_VISIBLE_DEVICES=void' \
    -v "$repo:/workspace" -w /workspace "$planner_image" sleep infinity \
    >"$logs/ros_container_id.txt"

  docker exec "$ros_name" bash -lc \
    'source /opt/ros/humble/setup.bash; exec ros2 run ros_gz_bridge parameter_bridge "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image" "/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo" "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"' \
    >"$logs/bridge_stdout.txt" 2>"$logs/bridge_stderr.txt" &
  bridge_pid=$!

  ready=false
  for _ in $(seq 1 300); do
    docker exec "$ros_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic list -t' >"$logs/ros_topics.txt" 2>/dev/null || true
    if grep -q '^/clock ' "$logs/ros_topics.txt" && grep -q '^/scan ' "$logs/ros_topics.txt" \
      && grep -q '^/odom ' "$logs/ros_topics.txt" && grep -q '^/cmd_vel ' "$logs/ros_topics.txt"; then ready=true; break; fi
    sleep .1
  done
  test "$ready" = true

  docker exec "$gz_name" bash -lc 'timeout 120 gz topic -e --json-output -t /cmd_vel' \
    >"$logs/cmd_vel_gz.txt" 2>"$logs/cmd_vel_gz_stderr.txt" & capture_pid=$!

  docker exec "$ros_name" bash -lc \
    "source /opt/ros/humble/setup.bash; export PYTHONPATH=/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bridge:\${PYTHONPATH:-}; export STAGE11CC_ZERO_LOG=/workspace/sgcf_nrmp_project/artifacts/stages/${stage_dir}/logs/${run_id}/cmd_vel_ros.jsonl; export STAGE11CD1_GATE_OUT=/workspace/sgcf_nrmp_project/artifacts/stages/${stage_dir}/runtime/${run_id}/safe_gate_result.json; export STAGE11CD1_CONFIG_V_MAX=1.0; export STAGE11CD1_CONFIG_W_MAX=1.5; export STAGE11CD1_FRESHNESS_S=0.2; export STAGE11CD1_ALLOWED_MODES=${STAGE11CD1_ALLOWED_MODES:-P0}; export STAGE11CD1_ACTIVE_DURATION_S=${STAGE11CD1_ACTIVE_DURATION_S:-10.0}; exec /opt/sgcf_planner_venv/bin/python -m ${actuator_module}" \
    >"$logs/zero_guard_stdout.txt" 2>"$logs/zero_guard_stderr.txt" & guard_pid=$!

  guard_ready=false
  for _ in $(seq 1 200); do
    docker exec "$ros_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 node list' >"$logs/ros_nodes.txt" 2>/dev/null || true
    if grep -qx "/${actuator_node}" "$logs/ros_nodes.txt"; then guard_ready=true; break; fi
    sleep .05
  done
  test "$guard_ready" = true

  docker exec "$ros_name" bash -lc \
    "source /opt/ros/humble/setup.bash; export CUDA_VISIBLE_DEVICES=''; export NVIDIA_VISIBLE_DEVICES=void; export PYTHONPATH=/workspace/sgcf_nrmp_project/core/src:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bridge:\${PYTHONPATH:-}; export STAGE11CC_SCENE=${scene}; export STAGE11CC_MODES=${mode_list}; export STAGE11CC_SCENE_OUT=/workspace/sgcf_nrmp_project/artifacts/stages/${stage_dir}/runtime/${run_id}; export STAGE11CC_REPO=/workspace; exec /opt/sgcf_planner_venv/bin/python -m sgcf_nrmp_bridge.stage11cc_planner_shadow_node" \
    >"$logs/planner_stdout.txt" 2>"$logs/planner_stderr.txt" & planner_pid=$!

  planner_ready=false
  for _ in $(seq 1 300); do
    docker exec "$ros_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 node list' >"$logs/ros_nodes.txt" 2>/dev/null || true
    if grep -qx /stage11cc_planner_shadow "$logs/ros_nodes.txt"; then planner_ready=true; break; fi
    kill -0 "$planner_pid" 2>/dev/null || break
    sleep .05
  done
  test "$planner_ready" = true
  docker exec "$ros_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 node info /stage11cc_planner_shadow' >"$logs/planner_node_info.txt"
  docker exec "$ros_name" bash -lc "source /opt/ros/humble/setup.bash; ros2 node info /${actuator_node}" >"$logs/zero_guard_node_info.txt"
  docker exec "$ros_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic info -v /cmd_vel' >"$logs/cmd_vel_topic_info.txt"
  docker exec "$ros_name" bash -lc 'source /opt/ros/humble/setup.bash; ros2 topic info -v /sgcf/planner_candidate_cmd_vel' >"$logs/candidate_topic_info.txt"

  deadline=$((SECONDS + 110))
  while kill -0 "$planner_pid" 2>/dev/null; do
    (( SECONDS < deadline )) || { echo "Planner timeout: $scene" >&2; exit 40; }
    sleep .2
  done
  set +e; wait "$planner_pid"; planner_exit=$?; set -e; planner_pid=""
  printf '%s\n' "$planner_exit" >"$logs/planner_exit_code.txt"
  test "$planner_exit" -eq 0
  docker exec "$ros_name" chmod -R a+rwX \
    "/workspace/sgcf_nrmp_project/artifacts/stages/$stage_dir/runtime/$run_id"
  cp "$scene_out/planner_records.jsonl" "$logs/planner_candidates.txt"
  rm -rf "$out/planner_inputs/$run_id"
  cp -a "$scene_out/planner_inputs/$scene" "$out/planner_inputs/$run_id"

  sleep .5
  if [[ "${STAGE11CC_ACTUATOR_SELF_TERMINATES:-false}" == true ]]; then
    actuator_deadline=$((SECONDS + 120))
    while kill -0 "$guard_pid" 2>/dev/null; do
      (( SECONDS < actuator_deadline )) || { echo "Actuator timeout: $scene" >&2; exit 41; }
      sleep .2
    done
  else
    kill -TERM "$guard_pid" 2>/dev/null || true
  fi
  set +e; wait "$guard_pid"; guard_exit=$?; set -e; guard_pid=""
  printf '%s\n' "$guard_exit" >"$logs/zero_guard_exit_code.txt"
  test "$guard_exit" -eq 0

  cleanup_scene
  trap - EXIT
  test ! -s "$logs/residual_containers.txt"
  printf '%s\n' "SCENE_COMPLETE $scene"
done
