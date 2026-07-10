"""
robot — 机器人运动学模型与优化约束定义
功能：
  1. 定义机器人几何（凸包 vertices → G/h 不等式）
  2. 定义运动学模型（diff / acker / omni）的线性化 A/B/C 矩阵
  3. 定义 NRMP 优化问题的变量、参数、代价函数和约束

核心输出:
  - G, h: 机器人凸包不等式 G @ p <= h（描述机器人形状）
  - A, B, C: 每个 receding step 的线性化运动学矩阵
  - C0_cost / I_cost / dynamics_constraint / bound_su_constraints: 优化问题组件

三种运动学:
  - diff: (v, w) → (x, y, theta)，线速度+角速度
  - acker: (v, psi) → (x, y, theta)，线速度+转向角
  - omni: (v_linear, theta_direction) → (x, y)，全向移动（不改变 theta）
"""

from __future__ import annotations
from math import inf
import numpy as np
from typing import Optional, Union
import cvxpy as cp
from math import sin, cos, tan
import torch
from neupan.configuration import to_device
from neupan.util import gen_inequal_from_vertex


class robot:
    def __init__(self, receding=10, step_time=0.1,
                 kinematics=None, vertices=None,
                 max_speed=[inf, inf], max_acce=[inf, inf],
                 wheelbase=None, length=None, width=None, **kwargs):
        """
        Args:
            receding: MPC 滚动时域步数
            step_time: MPC 每步时间 (s)
            kinematics: 'diff' / 'acker' / 'omni'
            vertices: 凸包顶点 (2, N)，若 None 则由 length/width 生成矩形
            max_speed: [v_max, phi_max/psi_max/w_max]
            max_acce: [a_v_max, a_phi_max]
            wheelbase: 轴距（仅 acker 需要）
            length, width: 矩形机器人尺寸（若 vertices 未指定）
        """
        if kinematics is None:
            raise ValueError("kinematics is required")

        self.shape = None          # 'rectangle' 或其他形状名
        self.vertices = self.cal_vertices(vertices, length, width, wheelbase)
        self.G, self.h = gen_inequal_from_vertex(self.vertices)  # G @ p <= h

        self.T = receding
        self.dt = step_time
        self.L = wheelbase  # 轴距

        self.kinematics = kinematics
        self.max_speed = np.c_[max_speed] if isinstance(max_speed, list) else max_speed
        self.max_acce = np.c_[max_acce] if isinstance(max_acce, list) else max_acce

        # acker 转向角限幅（不超过 90°）
        if kinematics == 'acker':
            if self.max_speed[1] >= 1.57:
                print(f"Warning: max steering angle {self.max_speed[1]} > 1.57, clamped to 1.57")
                self.max_speed[1] = 1.57

        self.speed_bound = self.max_speed       # 速度边界
        self.acce_bound = self.max_acce * self.dt  # 加速度边界（转为每步变化量）
        self.name = kwargs.get("name", self.kinematics + "_robot" + '_default')

    def define_variable(self, no_obs=False, indep_dis=None):
        """
        定义 cvxpy 优化变量：
          - indep_s: (3, T+1) 状态序列 [x, y, theta]
          - indep_u: (2, T) 控制序列
          - indep_dis: (1, T) 距离变量（有避障时）
        """
        self.indep_s = cp.Variable((3, self.T + 1), name="state")
        self.indep_u = cp.Variable((2, self.T), name="vel")
        if no_obs:
            return [self.indep_s, self.indep_u]
        return [self.indep_s, self.indep_u, indep_dis]

    def state_parameter_define(self):
        """
        定义 cvxpy 参数（状态相关）：
          - para_gamma_a: q_s * ref_s，状态跟踪目标
          - para_gamma_b: p_u * ref_us，速度跟踪目标
          - para_s: 名义状态（近端项参考点）
          - para_A/B/C_list: 运动学线性化矩阵
        """
        self.para_s = cp.Parameter((3, self.T + 1), name='para_state')
        self.para_gamma_a = cp.Parameter((3, self.T + 1), name='para_gamma_a')
        self.para_gamma_b = cp.Parameter((self.T,), name='para_gamma_b')
        self.para_A_list = [cp.Parameter((3, 3), name='para_A_' + str(t)) for t in range(self.T)]
        self.para_B_list = [cp.Parameter((3, 2), name='para_B_' + str(t)) for t in range(self.T)]
        self.para_C_list = [cp.Parameter((3, 1), name='para_C_' + str(t)) for t in range(self.T)]
        return [self.para_s, self.para_gamma_a, self.para_gamma_b] \
               + self.para_A_list + self.para_B_list + self.para_C_list

    def coefficient_parameter_define(self, no_obs=False, max_num=10):
        """
        定义碰撞约束的系数参数（来自 DUNE 输出）：
          - para_gamma_c: fa = lam.T (max_num, 2)
          - para_zeta_a: fb = lam.T @ p + mu.T @ h (max_num, 1)
        """
        if no_obs:
            self.para_gamma_c, self.para_zeta_a = [], []
        else:
            self.para_gamma_c = [
                cp.Parameter((max_num, 2), value=np.zeros((max_num, 2)),
                             name="para_gamma_c" + str(i))
                for i in range(self.T)
            ]
            self.para_zeta_a = [
                cp.Parameter((max_num, 1), value=np.zeros((max_num, 1)),
                             name="para_zeta_a" + str(i))
                for i in range(self.T)
            ]
        return self.para_gamma_c + self.para_zeta_a

    def C0_cost(self, para_p_u, para_q_s):
        """
        导航代价：状态跟踪代价 + 速度跟踪代价

        状态代价:
          - 标量 q_s: q_s * ||s - ref||^2
          - 向量 q_s (3,1): diag(q_s) * (s - ref)，x/y/theta 不同权重
        速度代价:
          - p_u * ||u[0] - ref_us||^2

        omni 特殊: theta 不计入状态代价（因为 omni 不控制 theta）
        """
        diff_u = para_p_u * self.indep_u[0, :] - self.para_gamma_b
        if para_q_s.shape == (3, 1):
            diff_s = cp.multiply(para_q_s, self.indep_s) - self.para_gamma_a
        else:
            diff_s = para_q_s * self.indep_s - self.para_gamma_a
        if self.kinematics == 'omni':
            diff_s_cost = cp.sum_squares(diff_s[0:2])
        else:
            diff_s_cost = cp.sum_squares(diff_s)
        C0_cost = diff_s_cost + cp.sum_squares(diff_u)
        return C0_cost

    def proximal_cost(self):
        """
        近端代价: 0.5 * ||s - para_s||^2
        PAN 迭代中，此代价防止 nom_s 偏离上一轮的结果太远，保证收敛。
        权重 bk 由 NRMP 构造时传入。
        """
        return cp.sum_squares(self.indep_s - self.para_s)

    def I_cost(self, indep_dis, ro_obs):
        """
        碰撞规避代价（DUNE 相关部分）:
          min(0, fa @ p + fb - d)^2

        含义: 如果状态 s 使得 fa@s + fb > d（安全距离），代价 = 0
              如果 fa@s + fb < d（违背安全距离），代价 > 0
        ro_obs 控制惩罚力度。
        """
        cost = 0
        indep_t = self.indep_s[0:2, 1:]  # 排除第一个时刻
        I_list = []
        for t in range(self.T):
            I_dpp = (self.para_gamma_c[t] @ indep_t[:, t:t + 1]
                     - self.para_zeta_a[t] - indep_dis[0, t])
            I_list.append(I_dpp)
        I_array = cp.vstack(I_list)
        cost += 0.5 * ro_obs * cp.sum_squares(cp.neg(I_array))
        return cost

    def dynamics_constraint(self):
        """
        运动学约束: x_{t+1} = A_t @ x_t + B_t @ u_t + C_t
        每个 t 用线性化 A_t, B_t, C_t 逼近真实运动学。
        """
        temp_list = []
        for t in range(self.T):
            A = self.para_A_list[t]
            B = self.para_B_list[t]
            C = self.para_C_list[t]
            temp_list.append(A @ self.indep_s[:, t:t + 1]
                             + B @ self.indep_u[:, t:t + 1] + C)
        constraints = [self.indep_s[:, 1:] == cp.hstack(temp_list)]
        return constraints

    def bound_su_constraints(self):
        """
        边界约束:
          - |u| <= max_speed          速度限制
          - |Δu| <= max_acce * dt     加速度限制
          - s[:, 0] == para_s[:, 0]  初始状态固定
        """
        constraints = []
        constraints += [cp.abs(self.indep_u[:, 1:] - self.indep_u[:, :-1]) <= self.acce_bound]
        constraints += [cp.abs(self.indep_u) <= self.speed_bound]
        constraints += [self.indep_s[:, 0:1] == self.para_s[:, 0:1]]
        return constraints

    def generate_state_parameter_value(self, nom_s, nom_u, qs_ref_s, pu_ref_us):
        """
        生成 cvxpy 参数的值（每步 MPC 调用一次）。

        对每个 t 计算 A_t, B_t, C_t（在 nom_s[:,t], nom_u[:,t] 处线性化）。
        """
        state_value_list = [nom_s, qs_ref_s, pu_ref_us]
        tensor_A_list = []
        tensor_B_list = []
        tensor_C_list = []

        for t in range(self.T):
            nom_st = nom_s[:, t:t + 1]
            nom_ut = nom_u[:, t:t + 1]
            if self.kinematics == 'acker':
                A, B, C = self.linear_ackermann_model(nom_st, nom_ut, self.dt, self.L)
            elif self.kinematics == 'diff':
                A, B, C = self.linear_diff_model(nom_st, nom_ut, self.dt)
            elif self.kinematics == 'omni':
                A, B, C = self.linear_omni_model(nom_ut, self.dt)
            else:
                raise ValueError('kinematics only supports acker, diff, or omni')
            tensor_A_list.append(A)
            tensor_B_list.append(B)
            tensor_C_list.append(C)

        state_value_list += tensor_A_list
        state_value_list += tensor_B_list
        state_value_list += tensor_C_list
        return state_value_list

    def linear_ackermann_model(self, nom_st, nom_ut, dt, L):
        """
        阿克曼运动学线性化: (v, psi) → (x, y, theta)

        A = [[1, 0, -v*dt*sin(phi)],
             [0, 1,  v*dt*cos(phi)],
             [0, 0,  1]]

        B = [[cos(phi)*dt,         0              ],
             [sin(phi)*dt,         0              ],
             [tan(psi)*dt/L,  v*dt/(L*cos²(psi)) ]]

        C = [[phi*v*sin(phi)*dt         ],
             [-phi*v*cos(phi)*dt        ],
             [-psi*v*dt/(L*cos²(psi))   ]]
        """
        phi = nom_st[2, 0]
        v, psi = nom_ut[0, 0], nom_ut[1, 0]
        A = torch.Tensor([[1, 0, -v * dt * sin(phi)],
                          [0, 1, v * dt * cos(phi)],
                          [0, 0, 1]])
        B = torch.Tensor([[cos(phi) * dt, 0],
                          [sin(phi) * dt, 0],
                          [tan(psi) * dt / L, v * dt / (L * (cos(psi) ** 2))]])
        C = torch.Tensor([[phi * v * sin(phi) * dt],
                          [-phi * v * cos(phi) * dt],
                          [-psi * v * dt / (L * (cos(psi) ** 2))]])
        return to_device(A), to_device(B), to_device(C)

    def linear_diff_model(self, nom_state, nom_u, dt):
        """
        差速运动学线性化: (v, w) → (x, y, theta)

        A = [[1, 0, -v*dt*sin(phi)],
             [0, 1,  v*dt*cos(phi)],
             [0, 0,  1]]

        B = [[cos(phi)*dt,  0],
             [sin(phi)*dt,  0],
             [0,            dt]]

        C = [[phi*v*sin(phi)*dt],
             [-phi*v*cos(phi)*dt],
             [0]]
        """
        phi = nom_state[2, 0]
        v = nom_u[0, 0]
        A = torch.Tensor([[1, 0, -v * dt * sin(phi)],
                          [0, 1, v * dt * cos(phi)],
                          [0, 0, 1]])
        B = torch.Tensor([[cos(phi) * dt, 0],
                          [sin(phi) * dt, 0],
                          [0, dt]])
        C = torch.Tensor([[phi * v * sin(phi) * dt],
                          [-phi * v * cos(phi) * dt],
                          [0]])
        return to_device(A), to_device(B), to_device(C)

    def linear_omni_model(self, nom_u, dt):
        """
        全向运动学线性化: (v_linear, theta_direction) → (x, y)

        注意: omni 的自旋不受控制（输出 vx, vy 而不是直接命令方向）。
             非线性出现在 (v_linear, theta) → (vx, vy) = (v*cos(theta), v*sin(theta))

        A = [[1, 0, 0],
             [0, 1, 0],
             [0, 0, 1]]   ← omni 不改变 theta

        B = [[cos(phi)*dt,  -v*sin(phi)*dt],
             [sin(phi)*dt,   v*cos(phi)*dt],
             [0,             0]]

        C = [[phi*v*sin(phi)*dt ],
             [-phi*v*cos(phi)*dt],
             [0]]
        """
        phi = nom_u[1, 0]  # 这里 phi 是速度方向 theta
        v = nom_u[0, 0]
        A = torch.Tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        B = torch.Tensor([[cos(phi) * dt, -v * sin(phi) * dt],
                          [sin(phi) * dt, v * cos(phi) * dt],
                          [0, 0]])
        C = torch.Tensor([[phi * v * sin(phi) * dt],
                          [-phi * v * cos(phi) * dt],
                          [0]])
        return to_device(A), to_device(B), to_device(C)

    def cal_vertices_from_length_width(self, length, width, wheelbase=None):
        """
        从长宽计算矩形凸包顶点（机器人初始位姿在原点）。
        四点顺序: 左下 → 右下 → 右上 → 左上（逆时针）。

        wheelbase 不为零时，车身中心后移（阿克曼前轮转向的几何补偿）。
        """
        wheelbase = 0 if wheelbase is None else wheelbase
        start_x = -(length - wheelbase) / 2
        start_y = -width / 2

        p0 = np.array([[start_x], [start_y]])
        p1 = np.array([[start_x + length], [start_y]])
        p2 = np.array([[start_x + length], [start_y + width]])
        p3 = np.array([[start_x], [start_y + width]])
        return np.hstack((p0, p1, p2, p3))

    def cal_vertices(self, vertices=None, length=None, width=None, wheelbase=None):
        """
        通用顶点生成器:
          - vertices 已指定：直接使用
          - vertices 未指定：从 length, width 生成矩形
        """
        if vertices is not None:
            if isinstance(vertices, list):
                vertices_np = np.array(vertices).T
            elif isinstance(vertices, np.ndarray):
                vertices_np = vertices
            else:
                raise ValueError("vertices must be a list or numpy array")
        else:
            self.shape = "rectangle"
            vertices_np = self.cal_vertices_from_length_width(length, width, wheelbase)
            self.length = length
            self.width = width
            self.wheelbase = wheelbase

        assert vertices_np.shape[1] >= 3, "vertices must be (2, N), N >= 3"
        return vertices_np
