"""
InitialPath — 初始参考路径生成
功能：根据 waypoints 生成 NeuPAN 的参考轨迹。
      支持直线（line）、Dubins 曲线（dubins）、Reeds-Shepp 曲线（reeds）。
      管理路径索引推进、到达判断、loop 循环、gear（前进/后退）切换。

核心数据流：
  waypoints (用户给定) → init_path_with_state (加入当前位姿) →
  gctl.generate_curve (插值生成稠密点) → split_path_with_gear (按gear分段) →
  generate_nom_ref_state (每步MPC提取参考状态)

loop 模式: 到达终点后生成反向路径（正向行驶返回），避免倒车无雷达的问题。
           同时支持调头旋转（turn_remaining），让激光雷达始终朝前。
"""

import numpy as np
from math import tan, inf, cos, sin, sqrt
from gctl import curve_generator
from neupan.util import WrapToPi, distance
import math


class InitialPath:
    """
    waypoints: list of [x, y, yaw] or numpy array of shape (n, 3)
    loop: if True, 到达终点后生成反向路径形成循环
    """

    def __init__(self, receding, step_time, ref_speed, robot,
                 waypoints=None, loop=False, curve_style="line",
                 turn_speed=1.0, **kwargs):
        """
        Args:
            receding: MPC 滚动时域步数
            step_time: MPC 每步时间
            ref_speed: 参考速度 (m/s)
            robot: 机器人运动学模型
            waypoints: 用户指定的路径点 [[x, y, theta], ...]
            loop: 是否循环（到达终点后返回起点）
            curve_style: 曲线类型 'line'/'dubins'/'reeds'
            turn_speed: 调头旋转的角速度 (rad/s)
        """
        self.T = receding
        self.dt = step_time
        self.ref_speed = ref_speed
        self.robot = robot
        self.waypoints = self.trans_to_np_list(waypoints)
        self.loop = loop
        self.curve_style = curve_style
        self.min_radius = kwargs.get("min_radius", self.default_turn_radius())
        # 参考路径点间隔（默认 = 一步内前进的距离）
        self.interval = kwargs.get("interval", self.dt * self.ref_speed)

        # 到达判断阈值
        self.arrive_threshold = kwargs.get("arrive_threshold", 0.1)      # 距终点多远算到达
        self.close_threshold = kwargs.get("close_threshold", 0.1)        # 找最近点的搜索截止距离
        self.ind_range = kwargs.get("ind_range", 10)                     # 最近点搜索范围
        self.arrive_index_threshold = kwargs.get("arrive_index_threshold", 1)  # 索引上距终点多远算到达

        self.arrive_flag = False      # 是否已到达（非 loop 模式用）
        self.loop_triggered = False   # 是否刚触法 loop（neupan.py 用来清零速度）
        self.turn_remaining = 0.0     # 调头旋转剩余时间
        self.turn_speed = turn_speed  # 调头旋转角速度

        self.cg = curve_generator()   # gctl 曲线生成器
        self.initial_path = None      # 初始路径（未设置时为 None）

    def generate_nom_ref_state(self, state, cur_vel_array, ref_speed):
        """
        为当前 MPC 步生成:
          - nom_s: 名义状态序列 (T+1)
          - nom_u: 名义控制序列 (T)
          - ref_s: 参考状态序列 (T+1)
          - ref_us: 参考速度序列 (T)

        关键逻辑:
          - pre_state 用运动学模型向前预测（给 MPC 做动力学线性化点）
          - ref_state 沿参考路径向前推进（给 MPC 做跟踪目标）
          - gear 从路径点的 gear 字段获取（决定前进还是后退）
        """
        state = state[:3]

        ref_state = self.cur_point[0:3].copy()
        ref_index = self.point_index
        pre_state = state.copy()

        state_pre_list = [pre_state]
        state_ref_list = [ref_state]

        assert self.cur_point.shape[0] >= 4
        gear_list = [self.cur_point[-1, 0]] * self.T  # 从路径点取齿轮方向

        ref_speed_forward = ref_speed * self.dt

        for t in range(self.T):
            # 运动学预测的标称状态
            pre_state = self.motion_predict_model(
                pre_state, cur_vel_array[:, t:t + 1], self.robot.L, self.dt
            )
            state_pre_list.append(pre_state)

            # 参考状态沿路径推进
            if ref_speed_forward >= self.interval:
                inc_index = int(ref_speed_forward / self.interval)
                ref_index = ref_index + inc_index
                if ref_index > len(self.cur_curve) - 1:
                    ref_index = len(self.cur_curve) - 1
                    gear_list[t] = 0
                ref_state = self.cur_curve[ref_index][0:3]
            else:
                ref_state, ref_index = self.find_interaction_point(
                    ref_state, ref_index, ref_speed_forward
                )
                if ref_index > len(self.cur_curve) - 1:
                    gear_list[t] = 0

            # 角度差用 WrapToPi 处理，防止跳变
            diff = ref_state[2, 0] - pre_state[2, 0]
            ref_state[2, 0] = pre_state[2, 0] + WrapToPi(diff)
            state_ref_list.append(ref_state)

        nom_s = np.hstack(state_pre_list)
        nom_u = cur_vel_array
        ref_s = np.hstack(state_ref_list)
        gear_array = np.array(gear_list)
        ref_us = gear_array * ref_speed

        return nom_s, nom_u, ref_s, ref_us

    def set_initial_path(self, path):
        """
        从外部设置完整路径（用于来自全局规划器的路径）。
        path: list of [x, y, theta, gear] (4, 1) vectors
        """
        self.initial_path = path
        self.interval = self.cal_average_interval(path)
        self.split_path_with_gear()
        self.curve_index = 0
        self.point_index = 0

    def cal_average_interval(self, path):
        """计算路径的平均点间隔"""
        n = len(path)
        if n < 2:
            return 0
        dist_sum = 0.0
        for p1, p2 in zip(path, path[1:]):
            dist_sum += math.hypot(p2[0, 0] - p1[0, 0], p2[1, 0] - p1[1, 0])
        return dist_sum / (n - 1)

    def closest_point(self, state, threshold=0.1, ind_range=10):
        """
        在当前曲线上找离机器人最近的点（局部搜索，范围 ind_range）。
        更新 self.point_index。
        """
        min_dis = inf
        cur_index = self.point_index
        start = max(cur_index, 0)
        end = min(cur_index + ind_range, len(self.cur_curve))
        for index in range(start, end):
            dis = distance(state[0:2], self.cur_curve[index][0:2])
            if dis < min_dis:
                min_dis = dis
                self.point_index = index
                if dis < threshold:
                    break
        return min_dis

    def find_interaction_point(self, ref_state, ref_index, length):
        """
        在路径上找到距离参考点恰好 length 的点（沿路径前进）。
        用于 ref_speed_forward < interval 时的精确插值。
        """
        circle = np.squeeze(ref_state[0:2])
        while True:
            if ref_index > len(self.cur_curve) - 2:
                end_point = self.cur_curve[-1]
                end_point[2] = WrapToPi(end_point[2])
                return end_point[0:3], ref_index
            cur_point = self.cur_curve[ref_index]
            next_point = self.cur_curve[ref_index + 1]
            segment = [np.squeeze(cur_point[0:2]), np.squeeze(next_point[0:2])]
            interaction_point = self.range_cir_seg(circle, length, segment)
            if interaction_point is not None:
                diff = WrapToPi(next_point[2, 0] - cur_point[2, 0])
                theta = WrapToPi(cur_point[2, 0] + diff / 2)
                state_ref = np.append(interaction_point, theta).reshape((3, 1))
                return state_ref, ref_index
            else:
                ref_index += 1

    def range_cir_seg(self, circle, r, segment):
        """
        求圆和线段的交点（圆=以参考点为圆心，r=前进距离，线段=路径段）。
        用于精确计算参考点在路径段上的位置。
        """
        sp, ep = segment[0], segment[1]
        d = ep - sp
        if np.linalg.norm(d) == 0:
            return None
        f = sp - circle
        a = d @ d
        b = 2 * f @ d
        c = f @ f - r ** 2
        discriminant = b ** 2 - 4 * a * c
        if discriminant < 0:
            return None
        t2 = (-b + sqrt(discriminant)) / (2 * a)
        if 0 <= t2 <= 1:
            return sp + t2 * d
        return None

    def check_arrive(self, state):
        """
        到达检测 + loop 处理

        返回 True 表示到达终点且不循环（主程序应停止）。
        返回 False 表示: 1) 未到达, 2) 到达但触发了 loop（已生成新路径）。

        loop 处理：
          - 通过 _loop_start/_loop_goal 记录原始起止点
          - 到达时判断当前位置在起点还是终点
          - 生成从当前位置到目标点的新路径（正向行驶）
          - 设置 turn_remaining 让 robot 调头
        """
        self.init_check(state)  # 若 initial_path 未设置则自动生成
        self.closest_point(state, self.close_threshold, self.ind_range)

        if self.check_curve_arrive(state, self.arrive_threshold, self.arrive_index_threshold):
            if self.curve_index + 1 >= self.curve_number:
                if self.loop:
                    # 记录原始起终点（仅首次触法 loop 时）
                    if not hasattr(self, '_loop_start'):
                        self._loop_start = self.waypoints[0].copy()
                        self._loop_goal = self.waypoints[1].copy()
                    # 判断在起点还是终点，决定下一段方向
                    at_start = np.linalg.norm(
                        state[:2] - self._loop_start[:2]
                    ) < self.arrive_threshold
                    target = self._loop_goal if at_start else self._loop_start
                    # 生成从当前位置到目标点的正向路径
                    self.set_ipath_with_waypoints([state[0:3].copy(), target.copy()])
                    # 调头旋转（让激光雷达朝前）
                    self.turn_remaining = math.pi / self.turn_speed
                    self.loop_triggered = True
                    print(f"Info: loop, {'start→goal' if at_start else 'goal→start'} (turn {self.turn_remaining:.1f}s)")
                    return False
                else:
                    if not self.arrive_flag:
                        print("Info: arrive at the end of the path")
                        self.arrive_flag = True
                    return True
            else:
                self.curve_index += 1
                self.point_index = 0
        return False

    def check_curve_arrive(self, state, arrive_threshold=0.1, arrive_index_threshold=2):
        """检查是否到达当前路径段的终点"""
        final_point = self.cur_curve[-1][0:2]
        arrive_distance = np.linalg.norm(state[0:2] - final_point)
        return (arrive_distance < arrive_threshold
                and self.point_index >= (len(self.cur_curve) - arrive_index_threshold - 2))

    def split_path_with_gear(self):
        """将路径按 gear（前进/后退）分段，每段一个均匀的行驶方向"""
        if not hasattr(self, "initial_path"):
            raise AttributeError("Object must have a 'initial_path' attribute")
        self.curve_list = []
        current_curve = []
        current_gear = self.initial_path[0][-1]
        for point in self.initial_path:
            if point[-1] != current_gear:
                self.curve_list.append(current_curve)
                current_curve = []
                current_gear = point[-1]
            current_curve.append(point)
        if current_curve:
            self.curve_list.append(current_curve)

    def init_path_with_state(self, state):
        """
        用 waypoints 生成初始路径（将当前位姿插入到 waypoints 最前面）。
        loop=True 时还会将起点追加到末尾形成闭环。
        """
        assert len(self.waypoints) > 0, "Error: waypoints are not set"
        # 避免 state 和第一个 waypoint 相同时重复插入（零长度段导致 gctl NaN）
        if isinstance(self.waypoints, list):
            if np.linalg.norm(np.array(state[:2]).flatten()
                              - np.array(self.waypoints[0][:2]).flatten()) > 0.01:
                self.waypoints = [state] + self.waypoints
        elif isinstance(self.waypoints, np.ndarray):
            if np.linalg.norm(state[:2] - self.waypoints[0][:2]) > 0.01:
                self.waypoints = np.vstack([state, self.waypoints])
        if self.loop:
            self.waypoints = self.waypoints + [self.waypoints[0]]
        self.initial_path = self.cg.generate_curve(
            self.curve_style, self.waypoints, self.interval, self.min_radius, True
        )
        if self.curve_style == 'line':
            self._ensure_consistent_angles()

    def init_check(self, state):
        """若路径未设置，用当前状态和 waypoints 自动生成"""
        if self.initial_path is None:
            print("initial path is not set, generate path with the current state")
            self.set_ipath_with_state(state)

    def set_ipath_with_state(self, state):
        """从当前状态生成路径"""
        self.init_path_with_state(state[0:3])
        self.split_path_with_gear()
        self.curve_index = 0
        self.point_index = 0

    def update_initial_path_from_goal(self, start, goal):
        """从起始和目标位姿生成新路径（用于导航目标点更新）"""
        if self.loop:
            waypoints = [start, goal, start]
        else:
            waypoints = [start, goal]
        self.initial_path = self.cg.generate_curve(
            self.curve_style, waypoints, self.interval, self.min_radius, True
        )
        if self.curve_style == 'line':
            self._ensure_consistent_angles()
        self.split_path_with_gear()
        self.curve_index = 0
        self.point_index = 0
        self.waypoints = waypoints

    def set_ipath_with_waypoints(self, waypoints):
        """直接设置新的 waypoints 并生成路径"""
        self.initial_path = self.cg.generate_curve(
            self.curve_style, waypoints, self.interval, self.min_radius, True
        )
        if self.curve_style == 'line':
            self._ensure_consistent_angles()
        self.split_path_with_gear()
        self.curve_index = 0
        self.point_index = 0
        self.waypoints = waypoints

    def motion_predict_model(self, robot_state, vel, wheel_base, sample_time):
        """运动学预测：用当前速度预测下一时刻状态"""
        if self.robot.kinematics == "acker":
            return self.ackermann_model(robot_state, vel, wheel_base, sample_time)
        elif self.robot.kinematics == "diff":
            return self.diff_model(robot_state, vel, sample_time)
        elif self.robot.kinematics == "omni":
            return self.omni_model(robot_state, vel, sample_time)
        return robot_state

    def ackermann_model(self, car_state, vel, wheel_base, sample_time):
        """阿克曼运动学模型: (v, psi) → (x, y, theta)"""
        phi = car_state[2, 0]
        v, psi = vel[0, 0], vel[1, 0]
        ds = np.array([
            [v * cos(phi)],
            [v * sin(phi)],
            [v * tan(psi) / wheel_base]
        ])
        return car_state + ds * sample_time

    def diff_model(self, robot_state, vel, sample_time):
        """差速运动学模型: (v, w) → (x, y, theta)"""
        phi = robot_state[2, 0]
        v, w = vel[0, 0], vel[1, 0]
        ds = np.array([[v * cos(phi)], [v * sin(phi)], [w]])
        return robot_state + ds * sample_time

    def omni_model(self, robot_state, vel, sample_time):
        """全向运动学模型: (v_linear, theta) → (x,y)，theta 方向前进"""
        vx = vel[0, 0] * cos(vel[1, 0])
        vy = vel[0, 0] * sin(vel[1, 0])
        omni_vel = np.array([[vx], [vy], [0]])  # omni 不改变 theta
        return robot_state + sample_time * omni_vel

    @property
    def cur_waypoints(self):
        return self.waypoints

    @property
    def cur_curve(self):
        """当前路径段"""
        return self.curve_list[self.curve_index]

    @property
    def cur_point(self):
        """路径上的当前位置点"""
        return self.cur_curve[self.point_index]

    @property
    def curve_number(self):
        """路径段数"""
        return len(self.curve_list)

    def default_turn_radius(self):
        """默认转弯半径"""
        if self.robot.kinematics == "acker":
            max_psi = self.robot.max_speed[1]
            return self.robot.L / tan(max_psi)
        return 0.0

    def _ensure_consistent_angles(self):
        """
        确保直线路径上所有点的角度指向路径方向。
        gctl 对 line 曲线不保证角度一致，手动修正。
        """
        if self.initial_path is None or len(self.initial_path) < 2:
            return
        for i in range(len(self.initial_path) - 1):
            dx = self.initial_path[i + 1][0, 0] - self.initial_path[i][0, 0]
            dy = self.initial_path[i + 1][1, 0] - self.initial_path[i][1, 0]
            self.initial_path[i][2, 0] = math.atan2(dy, dx)
        if len(self.initial_path) >= 2:
            self.initial_path[-1][2, 0] = self.initial_path[-2][2, 0]

    def trans_to_np_list(self, point_list):
        """将 list of list 转为 list of np.array"""
        if point_list is None:
            return []
        return [np.c_[p] if isinstance(p, list) else p for p in point_list]
