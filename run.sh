#!/bin/bash
# 构建并启动 NeuPAN 仿真环境

IMAGE="neupan:noetic"
CONTAINER="neupan_dev"

case "${1:-build}" in
  build)
    echo "=== 构建镜像 ==="
    docker build -t $IMAGE .
    ;;
  run)
    echo "=== 启动容器 ==="
    docker stop $CONTAINER 2>/dev/null
    docker rm $CONTAINER 2>/dev/null
    xhost +local:docker 2>/dev/null
    docker run -d --name $CONTAINER \
      --gpus all --net=host \
      -e DISPLAY=$DISPLAY \
      -v /tmp/.X11-unix:/tmp/.X11-unix \
      $IMAGE sleep infinity
    echo "容器 $CONTAINER 已启动"
    echo "进入: docker exec -it $CONTAINER bash"
    ;;
  gazebo)
    echo "=== 启动 Gazebo 仿真 ==="
    docker exec -it $CONTAINER bash -c '
      pkill -9 -f roslaunch 2>/dev/null
      pkill -9 -f gzserver 2>/dev/null
      pkill -9 -f gzclient 2>/dev/null
      sleep 1
      roslaunch neupan_ros gazebo_limo_env_complex_20.launch
    '
    ;;
  neupan)
    echo "=== 启动 NeuPAN 控制器 ==="
    docker exec -it $CONTAINER bash -c '
      roslaunch neupan_ros neupan_gazebo_limo.launch
    '
    ;;
  all)
    $0 build && $0 run && echo "镜像构建完成，容器已启动"
    echo ""
    echo "终端1: ./run.sh gazebo"
    echo "终端2: ./run.sh neupan"
    ;;
  stop)
    docker stop $CONTAINER 2>/dev/null
    docker rm $CONTAINER 2>/dev/null
    echo "已停止"
    ;;
  *)
    echo "用法: $0 {build|run|gazebo|neupan|all|stop}"
    ;;
esac
