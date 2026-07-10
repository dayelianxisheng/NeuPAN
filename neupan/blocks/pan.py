"""
PAN (Proximal Alternating-minimization Network) — 近端交替最小化网络
功能：NeuPAN 的核心求解器。在每步 MPC 中交替执行 DUNE 编码和 NRMP 优化，
      通过 iter_num 轮迭代使控制序列收敛到最优解。

迭代流程:
  for i in range(iter_num):
    1. DUNE: 点云 → mu, lam          (感知 → 特征)
    2. NRMP: mu, lam → opt_vel       (特征 → 优化)
    3. 检查是否收敛（stop_criteria）    （早期退出）

本文修改: forward 新增 point_class 透传参数，支持语义类别输入。
           point_class=None 时行为完全等同于原版。
"""

import torch
from neupan.blocks import NRMP, DUNE
from math import inf
from typing import Optional
from neupan.configuration import to_device, tensor_to_np
from neupan.util import downsample_decimation


class PAN(torch.nn.Module):
    """
    Args:
        receding: MPC 滚动时域步数
        step_time: MPC 每步时间间隔 (s)
        robot: 机器人运动学模型
        iter_num: PAN 迭代次数，越多越容易收敛但计算量更大
        dune_max_num: DUNE 最大处理点数
        nrmp_max_num: NRMP 最大处理点数
        dune_checkpoint: DUNE 模型权重路径
        iter_threshold: 收敛判定阈值
        adjust_kwargs: 可调参数（q_s, p_u, eta, d_max, d_min）
        train_kwargs: DUNE 训练参数
    """

    def __init__(self, receding=10, step_time=0.1, robot=None,
                 iter_num=2, dune_max_num=100, nrmp_max_num=10,
                 dune_checkpoint=None, iter_threshold=0.1,
                 adjust_kwargs=None, train_kwargs=None, **kwargs):
        super(PAN, self).__init__()

        if adjust_kwargs is None: adjust_kwargs = dict()
        if train_kwargs is None: train_kwargs = dict()

        self.robot = robot
        self.T = receding
        self.dt = step_time

        self.iter_num = iter_num
        self.iter_threshold = iter_threshold

        # === 创建 NRMP 层（可微分凸优化求解器） ===
        self.nrmp_layer = NRMP(
            receding, step_time, robot, nrmp_max_num,
            eta=adjust_kwargs.get("eta", 10.0),
            d_max=adjust_kwargs.get("d_max", 1.0),
            d_min=adjust_kwargs.get("d_min", 0.1),
            q_s=adjust_kwargs.get("q_s", 1.0),
            p_u=adjust_kwargs.get("p_u", 1.0),
            ro_obs=adjust_kwargs.get("ro_obs", 400),
            bk=adjust_kwargs.get("bk", 0.1),
            solver=adjust_kwargs.get("solver", "ECOS"),
        )

        # 关闭避障模式: 两个 max_num 中任一为0则跳过碰撞规避
        self.no_obs = (nrmp_max_num == 0 or dune_max_num == 0)
        self.nrmp_max_num = nrmp_max_num
        self.dune_max_num = dune_max_num

        # === 创建 DUNE 层（点云→特征编码器） ===
        if not self.no_obs:
            self.dune_layer = DUNE(
                receding, dune_checkpoint, robot, dune_max_num, train_kwargs,
            )
        else:
            self.dune_layer = None

        # 缓存上一轮迭代的值，用于收敛判定
        self.current_nom_values = [None] * 4  # nom_s, nom_u, nom_lam, nom_mu
        self.printed = False

    def forward(self, nom_s, nom_u, ref_s, ref_us,
                obs_points=None, point_velocities=None,
                point_class: Optional[torch.Tensor] = None):
        """
        一次 PAN 迭代求解。

        Args:
            nom_s: (3, T+1) 名义状态序列
            nom_u: (2, T) 名义控制序列
            ref_s: (3, T+1) 参考状态序列
            ref_us: (T,) 参考速度序列
            obs_points: (2, N) 障碍物点云（世界坐标系）
            point_velocities: (2, N) 点速度
            point_class: (N,) 或 None，每个点的语义类别id

        Returns:
            nom_s: 优化后的状态序列
            nom_u: 优化后的控制序列
            nom_distance: 优化后的距离序列（用于 NRMP 侧视化）
        """
        for i in range(self.iter_num):

            if obs_points is not None and not self.no_obs:
                # Step 1: 生成点流（将点云旋转到每个 receding step 的机器人坐标系）
                point_flow_list, R_list, obs_points_list = self.generate_point_flow(
                    nom_s, obs_points, point_velocities
                )
                # Step 2: DUNE 编码
                # point_class 对所有 receding step 都一样，复制即可
                pc_list = [point_class] * (self.T + 1) if point_class is not None else None
                mu_list, lam_list, sort_point_list = self.dune_layer(
                    point_flow_list, R_list, obs_points_list,
                    point_class_list=pc_list
                )
            else:
                mu_list, lam_list, sort_point_list = [], [], []

            # Step 3: NRMP 优化（可微分凸优化求解）
            nom_s, nom_u, nom_distance = self.nrmp_layer(
                nom_s, nom_u, ref_s, ref_us, mu_list, lam_list, sort_point_list
            )

            # Step 4: 检查是否收敛（小于 iter_threshold 则提前退出）
            if self.stop_criteria(nom_s, nom_u, mu_list, lam_list):
                break

        return nom_s, nom_u, nom_distance

    def generate_point_flow(self, nom_s, obs_points, point_velocities=None):
        """
        生成每个 receding step 下的点流。

        对每个未来时刻 i:
          1. 用被预测的 ego-motion 预测障碍物位置（静止或匀速运动）
          2. 将障碍物点从世界坐标系变换到机器人坐标系

        Args:
            nom_s: (3, T+1) 名义状态
            obs_points: (2, N) 当前障碍物点（世界坐标系）
            point_velocities: (2, N) 每个点的速度（用于动态障碍物预测）

        Returns:
            point_flow_list: T+1 个 (2, n) — 机器人坐标系下的点
            R_list: T+1 个 (2, 2) — 旋转矩阵
            obs_points_list: T+1 个 (2, n) — 世界坐标系下的点
        """
        if point_velocities is None:
            point_velocities = torch.zeros_like(obs_points)

        # 如果点数超过 DUNE 上限，均匀下采样
        if obs_points.shape[1] > self.dune_max_num:
            self.print_once(f"down sample the obs points from {obs_points.shape[1]} to {self.dune_max_num}")
            obs_points = downsample_decimation(obs_points, self.dune_max_num)
            point_velocities = downsample_decimation(point_velocities, self.dune_max_num)

        obs_points_list = []
        point_flow_list = []
        R_list = []

        for i in range(self.T + 1):
            # 用匀速模型预测未来时刻的障碍物位置
            receding_obs_points = obs_points + i * (point_velocities * self.dt)
            obs_points_list.append(receding_obs_points)
            # 将世界坐标系点转到机器人坐标系
            p0, R = self.point_state_transform(nom_s[:, i], receding_obs_points)
            point_flow_list.append(p0)
            R_list.append(R)

        return point_flow_list, R_list, obs_points_list

    def point_state_transform(self, state, obs_points):
        """
        将世界坐标系下的障碍物点变换到机器人坐标系。

        变换: p_robot = R.T @ (p_world - trans)
        其中 R 由机器人朝向 theta 决定，trans 为机器人位置 (x, y)
        """
        state = state.reshape((3, 1))
        trans = state[0:2]
        theta = state[2, 0]
        R = to_device(torch.tensor([
            [torch.cos(theta), -torch.sin(theta)],
            [torch.sin(theta), torch.cos(theta)]
        ]))
        p0 = R.T @ (obs_points - trans)
        return p0, R

    def stop_criteria(self, nom_s, nom_u, mu_list, lam_list):
        """
        PAN 提前停止准则：检查本轮迭代和上一轮迭代的解的差异。

        无障碍物时：检查状态和控制的差异
        有障碍物时：检查 mu 和 lam 的差异（对碰撞规避更敏感）
        """
        if self.current_nom_values[0] is None:
            self.current_nom_values = [nom_s, nom_u, mu_list, lam_list]
            return False
        else:
            nom_s_diff = torch.norm(nom_s - self.current_nom_values[0])
            nom_u_diff = torch.norm(nom_u - self.current_nom_values[1])
            if len(mu_list) == 0 or len(self.current_nom_values[2]) == 0:
                diff = nom_s_diff ** 2 + nom_u_diff ** 2
            else:
                effect_num = min(mu_list[0].shape[1],
                                 self.current_nom_values[2][0].shape[1],
                                 self.nrmp_max_num)
                mu_diff = torch.norm(
                    torch.cat(mu_list)[:, :effect_num] -
                    torch.cat(self.current_nom_values[2])[:, :effect_num]
                ) / effect_num
                lam_diff = torch.norm(
                    torch.cat(lam_list)[:, :effect_num] -
                    torch.cat(self.current_nom_values[3])[:, :effect_num]
                ) / effect_num
                diff = mu_diff ** 2 + lam_diff ** 2
            self.current_nom_values = [nom_s, nom_u, mu_list, lam_list]
            return diff < self.iter_threshold

    @property
    def min_distance(self):
        """最近障碍物距离（用于碰撞检测）"""
        if self.dune_layer is None or self.no_obs:
            return inf
        return self.dune_layer.min_distance

    @property
    def dune_points(self):
        """DUNE 层处理的障碍物点"""
        if self.dune_layer is None or self.no_obs:
            return None
        return tensor_to_np(self.dune_layer.points)

    @property
    def nrmp_points(self):
        """NRMP 层使用的障碍物点"""
        if self.nrmp_layer is None or self.no_obs:
            return None
        return tensor_to_np(self.nrmp_layer.points)

    def print_once(self, message):
        """避免重复打印相同信息"""
        if not self.printed:
            print(message)
            self.printed = True
