"""
neupan — NeuPAN 主类（torch.nn.Module）
功能：封装 PAN、InitialPath、Robot 等模块，提供统一的 forward 接口。
      是用户（或 ROS 节点）直接调用的顶层 API。

核心流程:
  init_from_yaml(path) → neupan.forward(state, points, point_class) → action, info

API 设计:
  - forward(): 单步 MPC 推理（高频率 10-50Hz 调用）
  - scan_to_point() / scan_to_point_velocity(): 激光→点云转换
  - set_initial_path() / update_initial_path_from_goal(): 路径管理
  - update_adjust_parameters(): 实时调参
  - train_dune(): 训练 DUNE 模型
  - reset(): 重置状态

本文修改：
  - forward 新增 point_class 参数，支持语义类别输入
  - 新增 loop_triggered / turn_remaining 调头旋转逻辑
  - point_class=None 时行为完全等同于原版
"""

from __future__ import annotations

import yaml
import torch
from neupan.robot import robot
from neupan.blocks import InitialPath, PAN
from neupan import configuration
from neupan.util import time_it, file_check, get_transform
import numpy as np
from neupan.configuration import np_to_tensor, tensor_to_np
from math import cos, sin


class neupan(torch.nn.Module):

    def __init__(self, receding=10, step_time=0.1, ref_speed=4.0,
                 device="cpu", robot_kwargs=None, ipath_kwargs=None,
                 pan_kwargs=None, adjust_kwargs=None, train_kwargs=None, **kwargs):
        super(neupan, self).__init__()

        # === MPC 参数 ===
        self.T = receding           # 滚动时域步数
        self.dt = step_time         # 每步时间 (s)
        self.ref_speed = ref_speed  # 参考速度 (m/s)

        configuration.device = torch.device(device)
        configuration.time_print = kwargs.get("time_print", False)
        self.collision_threshold = kwargs.get("collision_threshold", 0.1)  # 碰撞检测阈值 (m)

        # === 初始化子模块 ===
        self.cur_vel_array = np.zeros((2, self.T))  # 当前速度序列（MPC 初始猜测）
        self.robot = robot(receding, step_time, **robot_kwargs)  # 机器人运动学

        # 参考路径生成器
        self.ipath = InitialPath(
            receding, step_time, ref_speed, self.robot, **ipath_kwargs
        )

        # PAN 求解器（DUNE + NRMP）
        if pan_kwargs is None:
            pan_kwargs = dict()
        pan_kwargs["adjust_kwargs"] = adjust_kwargs
        pan_kwargs["train_kwargs"] = train_kwargs
        self.dune_train_kwargs = train_kwargs
        self.pan = PAN(receding, step_time, self.robot, **pan_kwargs)

        # 状态信息
        self.info = {"stop": False, "arrive": False, "collision": False}

    @classmethod
    def init_from_yaml(cls, yaml_file, **kwargs):
        """
        从 YAML 文件初始化 NeuPAN。
        最常用的构建方式。
        """
        abs_path = file_check(yaml_file)
        with open(abs_path, "r") as f:
            config = yaml.safe_load(f)
            config.update(kwargs)
        # 将 YAML 中的节转换为类的命名参数
        config["robot_kwargs"] = config.pop("robot", dict())
        config["ipath_kwargs"] = config.pop("ipath", dict())
        config["pan_kwargs"] = config.pop("pan", dict())
        config["adjust_kwargs"] = config.pop("adjust", dict())
        config["train_kwargs"] = config.pop("train", dict())
        return cls(**config)

    @time_it("neupan forward")
    def forward(self, state, points, velocities=None, point_class=None):
        """
        单步 MPC 推理。

        Args:
            state: (3, 1) 机器人位姿 [x, y, theta]
            points: (2, N) 障碍物点云（世界坐标系）
            velocities: (2, N) 或 None 每个点的速度（动态避障用）
            point_class: (N,) 或 None 每个点的语义类别id

        Returns:
            action: (2, 1) 控制指令 [vx, vy]（omni 输出）
            info: dict 包含 arrive/stop/min_distance 等信息

        重要返回条件:
          - arrive=True 时: action = zeros
          - stop=True 时:  action = zeros（碰撞检测）
          - rotate_omega!=0 时: forward 返回零速 + 旋转角速度
        """
        assert state.shape[0] >= 3

        # === 到达检测 ===
        if self.ipath.check_arrive(state):
            self.info["arrive"] = True
            return np.zeros((2, 1)), self.info

        # === loop 触发后处理 ===
        if self.ipath.loop_triggered:
            self.cur_vel_array = np.zeros_like(self.cur_vel_array)
            # 给 MPC 非零初始速度，避免 omni 下 v=0 导致 B 矩阵 y 轴控制项消失
            if self.robot.kinematics == 'omni' and len(self.ipath.cur_curve) >= 2:
                p0 = self.ipath.cur_curve[0]
                p1 = self.ipath.cur_curve[1]
                dx = p1[0, 0] - p0[0, 0]
                dy = p1[1, 0] - p0[1, 0]
                theta = np.arctan2(dy, dx)
                self.cur_vel_array[0, :] = self.ref_speed * 0.3
                self.cur_vel_array[1, :] = theta
            self.ipath.loop_triggered = False

        # === 调头旋转阶段 ===
        if self.ipath.turn_remaining > 0:
            self.info["rotate_omega"] = self.ipath.turn_speed
            self.ipath.turn_remaining -= self.dt
            return np.zeros((2, 1)), self.info

        # === 生成参考状态 ===
        nom_input_np = self.ipath.generate_nom_ref_state(
            state, self.cur_vel_array, self.ref_speed
        )

        # === 转 tensor ===
        nom_input_tensor = [np_to_tensor(n) for n in nom_input_np]
        obstacle_points_tensor = np_to_tensor(points) if points is not None else None
        point_velocities_tensor = (
            np_to_tensor(velocities) if velocities is not None else None
        )
        point_class_tensor = (
            np_to_tensor(point_class).long() if point_class is not None else None
        )

        # === PAN 求解（DUNE + NRMP） ===
        opt_state_tensor, opt_vel_tensor, opt_distance_tensor = self.pan(
            *nom_input_tensor, obstacle_points_tensor, point_velocities_tensor,
            point_class=point_class_tensor
        )

        # === 结果转 numpy ===
        opt_state_np, opt_vel_np = tensor_to_np(opt_state_tensor), tensor_to_np(opt_vel_tensor)
        self.cur_vel_array = opt_vel_np

        # 填充 info（用于可视化）
        self.info["state_tensor"] = opt_state_tensor
        self.info["vel_tensor"] = opt_vel_tensor
        self.info["distance_tensor"] = opt_distance_tensor
        self.info['ref_state_tensor'] = nom_input_tensor[2]
        self.info['ref_speed_tensor'] = nom_input_tensor[3]
        self.info["ref_state_list"] = [state[:, np.newaxis] for state in nom_input_np[2].T]
        self.info["opt_state_list"] = [state[:, np.newaxis] for state in opt_state_np.T]

        # === 碰撞检测 ===
        if self.check_stop():
            self.info["stop"] = True
            return np.zeros((2, 1)), self.info
        else:
            self.info["stop"] = False

        # === omni 特殊处理 ===
        # NRMP 内部优化 (v_linear, theta)，输出转为 (vx, vy)
        action = opt_vel_np[:, 0:1]
        if self.robot.kinematics == 'omni':
            vel = opt_vel_np[:, 0:1]
            vx = vel[0, 0] * cos(vel[1, 0])
            vy = vel[0, 0] * sin(vel[1, 0])
            action = np.array([[vx], [vy]])
            self.info['omni_linear_speed'] = vel[0, 0]
            self.info['omni_orientation'] = vel[1, 0]

        return action, self.info

    def check_stop(self):
        """碰撞检测：最近障碍物距离 < 阈值"""
        return self.min_distance < self.collision_threshold

    def scan_to_point(self, state, scan, scan_offset=[0, 0, 0],
                      angle_range=[-np.pi, np.pi], down_sample=1):
        """
        将激光雷达扫描数据转换为世界坐标系下的 2D 点云。

        Args:
            state: (3, 1) [x, y, theta]
            scan: dict {ranges, angle_min, angle_max, range_max, range_min}
            scan_offset: 激光雷达相对机器人本体的偏移 [x, y, theta]
            angle_range: 有效角度范围
            down_sample: 下采样步长

        Returns:
            points: (2, n) 世界坐标系点云，或 None
        """
        point_cloud = []
        ranges = np.array(scan["ranges"])
        angles = np.linspace(scan["angle_min"], scan["angle_max"], len(ranges))

        for i in range(len(ranges)):
            scan_range = ranges[i]
            angle = angles[i]
            if scan_range < (scan["range_max"] - 0.02) and scan_range > scan["range_min"]:
                if angle > angle_range[0] and angle < angle_range[1]:
                    point = np.array([[scan_range * cos(angle)], [scan_range * sin(angle)]])
                    point_cloud.append(point)

        if len(point_cloud) == 0:
            return None

        # 激光坐标系 → 机器人坐标系
        point_array = np.hstack(point_cloud)
        s_trans, s_R = get_transform(np.c_[scan_offset])
        temp_points = s_R @ point_array + s_trans

        # 机器人坐标系 → 世界坐标系
        trans, R = get_transform(state)
        points = (R @ temp_points + trans)[:, ::down_sample]
        return points

    def scan_to_point_velocity(self, state, scan, scan_offset=[0, 0, 0],
                                angle_range=[-np.pi, np.pi], down_sample=1):
        """
        同上，但额外返回每个点的速度（需要 scan 中包含 velocity 信息）。
        用于动态障碍物场景。
        """
        point_cloud = []
        velocity_points = []
        ranges = np.array(scan["ranges"])
        angles = np.linspace(scan["angle_min"], scan["angle_max"], len(ranges))
        scan_velocity = scan.get("velocity", np.zeros((2, len(ranges))))

        for i in range(len(ranges)):
            scan_range = ranges[i]
            angle = angles[i]
            if scan_range < (scan["range_max"] - 0.02) and scan_range >= scan["range_min"]:
                if angle > angle_range[0] and angle < angle_range[1]:
                    point_cloud.append(np.array([[scan_range * cos(angle)], [scan_range * sin(angle)]]))
                    velocity_points.append(scan_velocity[:, i:i + 1])

        if len(point_cloud) == 0:
            return None, None

        point_array = np.hstack(point_cloud)
        s_trans, s_R = get_transform(np.c_[scan_offset])
        temp_points = s_R.T @ (point_array - s_trans)
        trans, R = get_transform(state)
        points = (R @ temp_points + trans)[:, ::down_sample]
        velocity = np.hstack(velocity_points)[:, ::down_sample]
        return points, velocity

    def train_dune(self):
        """触发 DUNE 模型训练"""
        self.pan.dune_layer.train_dune(self.dune_train_kwargs)

    def reset(self):
        """重置规划器状态（用于新一轮导航）"""
        self.ipath.point_index = 0
        self.ipath.curve_index = 0
        self.ipath.arrive_flag = False
        self.info["stop"] = False
        self.info["arrive"] = False
        self.cur_vel_array = np.zeros_like(self.cur_vel_array)

    def set_initial_path(self, path):
        """
        从外部全局规划器设置完整路径。
        path: list of [x, y, theta, gear] 4x1 vectors
        """
        self.ipath.set_initial_path(path)

    def set_initial_path_from_state(self, state):
        """用当前状态初始化路径（若路径未设置）"""
        self.ipath.init_check(state)

    def set_reference_speed(self, speed: float):
        """实时修改参考速度"""
        self.ipath.ref_speed = speed
        self.ref_speed = speed

    def update_initial_path_from_goal(self, start, goal):
        """从 start 到 goal 生成新路径"""
        self.ipath.update_initial_path_from_goal(start, goal)

    def update_initial_path_from_waypoints(self, waypoints):
        """从新的 waypoints 生成路径"""
        self.ipath.set_ipath_with_waypoints(waypoints)

    def update_adjust_parameters(self, **kwargs):
        """
        实时调参（不重启规划器）。
        支持: q_s, p_u, eta, d_max, d_min
        """
        self.pan.nrmp_layer.update_adjust_parameters_value(**kwargs)

    @property
    def min_distance(self):
        """最近障碍物距离（m）"""
        return self.pan.min_distance

    @property
    def dune_points(self):
        """DUNE 层处理的障碍物点"""
        return self.pan.dune_points

    @property
    def nrmp_points(self):
        """NRMP 优化层使用的障碍物点"""
        return self.pan.nrmp_points

    @property
    def initial_path(self):
        """当前参考路径"""
        return self.ipath.initial_path

    @property
    def adjust_parameters(self):
        """当前可调参数值"""
        return self.pan.nrmp_layer.adjust_parameters

    @property
    def waypoints(self):
        """用户设置的导航路点"""
        return self.ipath.waypoints

    @property
    def opt_trajectory(self):
        """MPC 优化的轨迹"""
        return self.info["opt_state_list"]

    @property
    def ref_trajectory(self):
        """参考轨迹"""
        return self.info["ref_state_list"]
