#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
out="$repo/sgcf_nrmp_project/artifacts/stages/stage_12_ros2_offline_rosbag"
image=$(docker image inspect sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1 --format '{{.Id}}')
mkdir -p "$out/runtime" "$out/logs" "$out/rosbag"

snapshot() {
  case "$1" in
    single_static_obstacle) echo "$repo/sgcf_nrmp_project/artifacts/stages/stage_11c_d1a_speed_contract_and_geometry_diagnosis/planner_inputs/single_static_obstacle";;
    vehicle_path) echo "$repo/sgcf_nrmp_project/artifacts/stages/stage_11c_d3a_semantic_safety_completion/planner_inputs/vehicle_path_p2_closed_loop";;
    rgb_dropout_contract) echo "$repo/sgcf_nrmp_project/artifacts/stages/stage_11c_d3a_semantic_safety_completion/planner_inputs/rgb_dropout_contract";;
    outdated_rgb_contract) echo "$repo/sgcf_nrmp_project/artifacts/stages/stage_11c_d3a_semantic_safety_completion/planner_inputs/outdated_rgb_contract";;
  esac
}
modes() { case "$1" in single_static_obstacle) echo P0;; *) echo P0,P2;; esac; }

for scene in single_static_obstacle vehicle_path rgb_dropout_contract outdated_rgb_contract; do
  log="$out/logs/$scene"; runtime="$out/runtime/$scene"; mkdir -p "$log" "$runtime"
  snap=$(snapshot "$scene")
  snap_rel=${snap#"$repo"/}
  bag_args=()
  if [[ "$scene" == vehicle_path ]]; then bag_args=(-e STAGE12_BAG_PATH=/workspace/sgcf_nrmp_project/artifacts/stages/stage_12_ros2_offline_rosbag/rosbag/stage12_rosbag.sqlite3); fi
  docker run --rm --name "sgcf_stage12_${scene}" --network host \
    -e ROS_DOMAIN_ID=62 -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
    -e STAGE12_SCENE="$scene" -e STAGE12_SNAPSHOT_DIR="/workspace/$snap_rel" \
    -e STAGE11CC_SCENE="$scene" -e STAGE11CC_MODES="$(modes "$scene")" \
    -e STAGE11CC_SCENE_OUT="/workspace/sgcf_nrmp_project/artifacts/stages/stage_12_ros2_offline_rosbag/runtime/$scene" \
    -e STAGE11CC_REPO=/workspace -e STAGE12_FUSION_OUT="/workspace/sgcf_nrmp_project/artifacts/stages/stage_12_ros2_offline_rosbag/runtime/$scene/fusion.jsonl" "${bag_args[@]}" -v "$repo:/workspace" -w /workspace "$image" bash -lc '
      set -eo pipefail
      source /opt/ros/humble/setup.bash; source /opt/sgcf_planner_venv/bin/activate; set -u
      export PYTHONPATH=/workspace/sgcf_nrmp_project/core/src:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bridge:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_msgs:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_fusion:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_planner:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_visualization:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_evaluation:/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bringup:${PYTHONPATH:-}
      pids=""
      stop(){ for p in $pids; do kill -INT "$p" 2>/dev/null || true; done; wait || true; }
      trap stop EXIT
      python -m sgcf_nrmp_fusion.offline_fusion >"$STAGE11CC_SCENE_OUT/fusion.log" 2>&1 & pids+=" $!"
      python -m sgcf_nrmp_visualization.offline_visualization >"$STAGE11CC_SCENE_OUT/visualization.log" 2>&1 & pids+=" $!"
      python -m sgcf_nrmp_evaluation.offline_diagnostics >"$STAGE11CC_SCENE_OUT/diagnostics.log" 2>&1 & pids+=" $!"
      if [[ -n "${STAGE12_BAG_PATH:-}" ]]; then python -c "from sgcf_nrmp_bringup.bag_tools import record_main;record_main()" >"$STAGE11CC_SCENE_OUT/recorder.log" 2>&1 & rec=$!;pids+=" $rec"; fi
      python -c "from sgcf_nrmp_bridge.stage11cc_planner_shadow_node import main;main()" >"$STAGE11CC_SCENE_OUT/planner.log" 2>&1 & planner=$!;pids+=" $planner"
      sleep 1
      ros2 topic list -t >"$STAGE11CC_SCENE_OUT/topics.txt"
      ros2 node list >"$STAGE11CC_SCENE_OUT/nodes.txt"
      (ros2 topic info /cmd_vel -v || true) >"$STAGE11CC_SCENE_OUT/cmd_vel_info.txt" 2>&1
      python -m sgcf_nrmp_bringup.synthetic_publisher >"$STAGE11CC_SCENE_OUT/publisher.log" 2>&1 & pub=$!;pids+=" $pub"
      wait "$pub"; wait "$planner"
      if [[ -n "${rec:-}" ]]; then wait "$rec"; fi
    ' >"$log/container_stdout.txt" 2>"$log/container_stderr.txt"
  docker ps -a --format '{{.Names}}' | grep -Fx "sgcf_stage12_${scene}" >"$log/residual_container.txt" || true
done

for sample in 1 2; do
  audit="$out/rosbag/replay_${sample}.json"
  docker run --rm --name "sgcf_stage12_replay_${sample}" --network host -e ROS_DOMAIN_ID=$((70+sample)) \
    -e STAGE12_BAG_PATH=/workspace/sgcf_nrmp_project/artifacts/stages/stage_12_ros2_offline_rosbag/rosbag/stage12_rosbag.sqlite3 \
    -e STAGE12_REPLAY_AUDIT="/workspace/${audit#$repo/}" -v "$repo:/workspace" -w /workspace "$image" bash -lc '
      set -eo pipefail;source /opt/ros/humble/setup.bash;source /opt/sgcf_planner_venv/bin/activate;set -u
      export PYTHONPATH=/workspace/sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bringup:${PYTHONPATH:-}
      python -c "from sgcf_nrmp_bringup.bag_tools import audit_main;audit_main()" & a=$!;sleep .5
      python -c "from sgcf_nrmp_bringup.bag_tools import replay_main;replay_main()";wait "$a"
    ' >"$out/logs/replay_${sample}.log" 2>&1
done

docker ps --format '{{.Names}}' | grep '^sgcf_stage12_' >"$out/logs/residual_containers.txt" || true
pgrep -af 'sgcf_nrmp_(offline|synthetic)|stage11cc_planner_shadow' >"$out/logs/residual_processes.txt" || true
