"""
NRMP (Neural Regularized Motion Planner) — 神经正则化运动规划器
功能：作为 PAN 中的"优化"模块，接收 DUNE 编码的 mu/lambda 特征，
      用 cvxpylayers 求解带碰撞约束的凸优化问题，输出最优控制序列。

核心优化问题（简化）：
  min   状态跟踪代价 + 速度跟踪代价 + 碰撞规避代价
  s.t.  运动学约束 (Ax + Bu + C = x_next)
        速度/加速度边界 (|u| <= max_speed, |Δu| <= max_acce)
        安全距离边界 (d_min <= d <= d_max)

可微分性：cvxpylayers 将 cvxpy 问题包装为 torch 层，允许梯度流过求解器。
          这意味着可以通过反向传播调整 cost 权重（q_s, p_u, eta 等）。

注意：NRMP 完全在 CPU 上运行（cvxpy 不支持 GPU）。
      本文不需要修改 NRMP，它只消费 DUNE 的输出，不关心 mu 是如何计算的。
"""

from __future__ import annotations
from typing import Union

import torch
import cvxpy as cp
import numpy as np
from neupan.robot import robot
from neupan.configuration import to_device, value_to_tensor, np_to_tensor, tensor_dtype
from cvxpylayers.torch import CvxpyLayer
from neupan.util import time_it
from typing import Optional, List


class NRMP(torch.nn.Module):

    def __init__(self, receding: int, step_time: float, robot: robot,
                 nrmp_max_num: int = 10, eta: float = 10.0,
                 d_max: float = 1.0, d_min: float = 0.1,
                 q_s: Union[float, list, np.ndarray] = 1.0,
                 p_u: float = 1.0, ro_obs: float = 400, bk: float = 0.1,
                 **kwargs):
        super(NRMP, self).__init__()

        self.T = receding             # 滚动时域步数
        self.dt = step_time           # 时间步
        self.robot = robot            # 机器人运动学模型
        self.G = np_to_tensor(robot.G)  # 凸包 G 矩阵
        self.h = np_to_tensor(robot.h)  # 凸包 h 向量

        self.max_num = nrmp_max_num   # NRMP 最大使用点数
        self.no_obs = False if nrmp_max_num > 0 else True  # 是否无避障

        # === 可调参数（可通过 update_adjust_parameters 实时修改） ===
        self.eta = value_to_tensor(eta, True)       # 松弛变量 L1 正则权重
        self.d_max = value_to_tensor(d_max, True)   # 最大安全距离
        self.d_min = value_to_tensor(d_min, True)   # 最小安全距离

        # q_s 支持标量和 3 维向量（x, y, theta 不同权重）
        if isinstance(q_s, (list, np.ndarray)):
            q_s_array = np.array(q_s).flatten()
            if q_s_array.shape[0] != 3:
                raise ValueError(f"q_s must be scalar or 3-element, got {q_s_array.shape[0]}")
            self.q_s = np_to_tensor(q_s_array, False).reshape(3, 1)
            self.q_s.requires_grad_(True)
        else:
            self.q_s = value_to_tensor(q_s, True)   # 状态跟踪权重（标量）

        self.p_u = value_to_tensor(p_u, True)       # 速度跟踪权重

        self.ro_obs = ro_obs  # 碰撞规避惩罚系数
        self.bk = bk          # 近端系数（PAN 收敛用）

        # 可调参数列表（给 cvxpy parameter 赋值用）
        self.adjust_parameters = (
            [self.q_s, self.p_u]
            if self.no_obs
            else [self.q_s, self.p_u, self.eta, self.d_max, self.d_min]
        )

        # === 构建 cvxpy 优化问题（只在 __init__ 中构造一次） ===
        self.variable_definition()    # 定义变量
        self.parameter_definition()   # 定义参数（占位）
        self.problem_definition()     # 构造问题 → CvxpyLayer

        self.obstacle_points = None
        self.solver = kwargs.get("solver", "ECOS")

    @time_it("- nrmp forward")
    def forward(self, nom_s, nom_u, ref_s, ref_us,
                mu_list=None, lam_list=None, point_list=None):
        """
        执行一次 NRMP 优化求解。

        Args:
            nom_s: (3, T+1) 名义状态（初始猜测）
            nom_u: (2, T) 名义控制（初始猜测）
            ref_s: (3, T+1) 参考状态
            ref_us: (T,) 参考速度
            mu_list: T+1 个 mu 矩阵（DUNE 输出）
            lam_list: T+1 个 lam 矩阵（DUNE 输出）
            point_list: T+1 个点云（最近点优先排序）

        Returns:
            opt_s: 最优状态序列 (3, T+1)
            opt_u: 最优控制序列 (2, T)
            opt_d: 最优距离序列 (1, T)
        """
        if point_list:
            # 只保留最近的前 max_num 个点给 NRMP
            self.obstacle_points = point_list[0][:, :self.max_num]

        # 组装参数值（状态 + 系数 + 调节参数）
        parameter_values = self.generate_parameter_value(
            nom_s, nom_u, ref_s, ref_us, mu_list, lam_list, point_list
        )

        # 求解凸优化（cvxpylayers 自动处理参数赋值和求解）
        solutions = self.nrmp_layer(
            *parameter_values, solver_args={"solve_method": self.solver}
        )
        opt_solution_state = solutions[0].type(tensor_dtype)
        opt_solution_vel = solutions[1].type(tensor_dtype)
        nom_d = None if self.no_obs else solutions[2].type(tensor_dtype)

        return opt_solution_state, opt_solution_vel, nom_d

    def generate_parameter_value(self, nom_s, nom_u, ref_s, ref_us,
                                  mu_list, lam_list, point_list):
        """组装所有优化参数的值"""
        adjust_value_list = self.generate_adjust_parameter_value()
        state_value_list = self.robot.generate_state_parameter_value(
            nom_s, nom_u, self.q_s * ref_s, self.p_u * ref_us
        )
        coefficient_value_list = self.generate_coefficient_parameter_value(
            mu_list, lam_list, point_list
        )
        return state_value_list + coefficient_value_list + adjust_value_list

    def generate_adjust_parameter_value(self):
        """返回可调参数的当前值（torch tensor，自动被 cvxpylayers 提取）"""
        return self.adjust_parameters

    def update_adjust_parameters_value(self, **kwargs):
        """
        实时更新可调参数值（不重构优化问题，只改数值）。

        Args see: neupan.update_adjust_parameters()
        """
        q_s_value = kwargs.get("q_s", self.q_s)
        # 标量/向量一致性检查
        if self.q_s.dim() == 0:
            if isinstance(q_s_value, (list, np.ndarray)):
                value = q_s_value[0]
                print(f"q_s should be scalar, using first element: {value}")
            self.q_s = value_to_tensor(value, True)
        elif self.q_s.shape == (3, 1):
            if isinstance(q_s_value, (list, np.ndarray)):
                q_s_array = np.array(q_s_value).flatten()
                if q_s_array.shape[0] != 3:
                    raise ValueError(f"q_s must be 3-element, got {q_s_array.shape[0]}")
                np_q_s = q_s_array.reshape(3, 1)
            else:
                raise ValueError(f"q_s must be 3d list/array, got {type(q_s_value)}")
            self.q_s = np_to_tensor(np_q_s, True).reshape(3, 1)

        self.p_u = value_to_tensor(kwargs.get("p_u", self.p_u), True)
        self.eta = value_to_tensor(kwargs.get("eta", self.eta), True)
        self.d_max = value_to_tensor(kwargs.get("d_max", self.d_max), True)
        self.d_min = value_to_tensor(kwargs.get("d_min", self.d_min), True)

        self.adjust_parameters = (
            [self.q_s, self.p_u] if self.no_obs
            else [self.q_s, self.p_u, self.eta, self.d_max, self.d_min]
        )

    def generate_coefficient_parameter_value(self, mu_list, lam_list, point_list):
        """
        将 DUNE 输出的 mu/lambda 转换为 NRMP 碰撞约束的系数。

        碰撞约束: fa @ p_t + fb >= distance_t, ∀t
        其中 fa = lam^T, fb = mu^T @ h + lam^T @ p

        Args:
            mu_list: T+1 个 (edge_dim, n)
            lam_list: T+1 个 (state_dim, n)
            point_list: T+1 个 (2, n)

        Returns:
            fa_list: T 个 (max_num, 2) — 碰撞约束的线性系数
            fb_list: T 个 (max_num, 1) — 碰撞约束的常数项
        """
        if self.no_obs:
            return []
        else:
            fa_list = [to_device(torch.zeros((self.max_num, 2))) for _ in range(self.T)]
            fb_list = [to_device(torch.zeros((self.max_num, 1))) for _ in range(self.T)]
            if not mu_list:
                return fa_list + fb_list
            for t in range(self.T):
                mu, lam, point = mu_list[t + 1], lam_list[t + 1], point_list[t + 1]
                fa = lam.T
                temp = torch.bmm(lam.T.unsqueeze(1), point.T.unsqueeze(2)).squeeze(1)
                fb = temp + mu.T @ self.h
                pn = min(mu.shape[1], self.max_num)
                fa_list[t][:pn, :] = fa[:pn, :]
                fb_list[t][:pn, :] = fb[:pn, :]
                # 超出实际点数时用第一个点填充（保持矩阵大小固定）
                if pn < self.max_num:
                    fa_list[t][pn:, :] = fa[0, :]
                    fb_list[t][pn:, :] = fb[0, :]
            return fa_list + fb_list

    def variable_definition(self):
        """定义优化变量"""
        self.indep_dis = cp.Variable((1, self.T), name="distance", nonneg=True)
        self.indep_list = self.robot.define_variable(self.no_obs, self.indep_dis)

    def parameter_definition(self):
        """定义优化参数（占位符，赋值由 cvxpylayers 自动完成）"""
        self.para_list = []
        self.para_list += self.robot.state_parameter_define()
        self.para_list += self.robot.coefficient_parameter_define(self.no_obs, self.max_num)
        self.para_list += self.adjust_parameter_define()

    def problem_definition(self):
        """构造 cvxpy 问题并将其包装为 CvxpyLayer"""
        prob = self.construct_prob()
        self.nrmp_layer = to_device(
            CvxpyLayer(prob, parameters=self.para_list, variables=self.indep_list)
        )

    def construct_prob(self):
        """
        构造完整的优化问题:
          min  nav_cost + dune_cost
          s.t. nav_constraints + dune_constraints
        """
        nav_cost, nav_constraints = self.nav_cost_cons()
        dune_cost, dune_constraints = self.dune_cost_cons()
        if self.no_obs:
            prob = cp.Problem(cp.Minimize(nav_cost), nav_constraints)
        else:
            prob = cp.Problem(
                cp.Minimize(nav_cost + dune_cost),
                nav_constraints + dune_constraints
            )
        assert prob.is_dcp(dpp=True)
        return prob

    def adjust_parameter_define(self):
        """定义可调参数的 cvxpy Parameter 占位"""
        if self.q_s.dim() == 0:
            self.para_q_s = cp.Parameter(name="para_q_s", value=1.0)
        elif self.q_s.shape == (3, 1):
            self.para_q_s = cp.Parameter((3, 1), name="para_q_s", value=np.ones((3, 1)))
        self.para_p_u = cp.Parameter(name="para_p_u", value=1.0)
        self.para_eta = cp.Parameter(value=8, nonneg=True, name="para_eta")
        self.para_d_max = cp.Parameter(name="para_d_max", value=1.0, nonneg=True)
        self.para_d_min = cp.Parameter(name="para_d_min", value=0.1, nonneg=True)
        if self.no_obs:
            return [self.para_q_s, self.para_p_u]
        return [self.para_q_s, self.para_p_u, self.para_eta,
                self.para_d_max, self.para_d_min]

    def nav_cost_cons(self):
        """导航代价和约束（路径跟踪 + 运动学）"""
        cost = 0
        constraints = []
        cost += self.robot.C0_cost(self.para_p_u, self.para_q_s)
        cost += 0.5 * self.bk * self.robot.proximal_cost()
        constraints += self.robot.dynamics_constraint()
        constraints += self.robot.bound_su_constraints()
        return cost, constraints

    def dune_cost_cons(self):
        """避障代价和约束（来自 DUNE 编码）"""
        cost = 0
        constraints = []
        cost += self.C1_cost_d()  # 距离代价
        if not self.no_obs:
            cost += self.robot.I_cost(self.indep_dis, self.ro_obs)  # 碰撞惩罚
        constraints += self.bound_dis_constraints()
        return cost, constraints

    def bound_dis_constraints(self):
        """安全距离边界"""
        constraints = []
        constraints += [self.indep_dis >= self.para_d_min]
        constraints += [self.indep_dis <= self.para_d_max]
        return constraints

    def C1_cost_d(self):
        """距离代价 = -eta * sum(d)，激励机器人远离障碍物"""
        return -self.para_eta * cp.sum(self.indep_dis)

    @property
    def points(self):
        """NRMP 层使用的障碍物点"""
        return self.obstacle_points
