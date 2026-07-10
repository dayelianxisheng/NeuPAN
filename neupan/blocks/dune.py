"""
DUNE (Deep Unfolded Neural Encoder) — 深度展开神经编码器
功能：将每个 receding step 下的障碍物点流（point_flow）编码为潜在距离特征 mu 和 lambda。
      mu 经旋转矩阵 R 变换后得到 lam，lam 作为 NRMP 碰撞规避约束的系数。

核心思想：
  1. 用 ObsPointNet 将 point_flow 中所有点一次性映射到 mu 空间（高效的 batch 计算）
  2. 对每个 receding step 的 mu，用旋转矩阵 R 生成 lam = -R @ G.T @ mu
  3. 按距离排序（最近点排在前面），只保留对碰撞最重要的点

本文修改: forward 新增 point_class_list 参数，支持语义类别输入。
            point_class=None 时行为完全等同于原版。
"""

from __future__ import annotations

import torch
from math import inf
from neupan.blocks import ObsPointNet, DUNETrain
from neupan.configuration import np_to_tensor, to_device
from neupan.util import time_it, file_check, repeat_mk_dirs
from typing import Optional
import sys


class DUNE(torch.nn.Module):

    def __init__(self, receding: int = 10, checkpoint=None, robot=None,
                 dune_max_num: int = 100, train_kwargs: Optional[dict] = None) -> None:
        super(DUNE, self).__init__()

        if train_kwargs is None:
            train_kwargs = dict()
        if robot is None:
            raise ValueError("robot parameter is required and cannot be None")

        self.T = receding            # MPC 滚动时域步数
        self.max_num = dune_max_num  # DUNE 最多处理的点数（下采样上限）
        self.robot = robot

        # === 机器人凸包不等式：G @ p <= h ===
        # G: (edge_dim, 2), h: (edge_dim, 1)
        # 对于 mowen 矩形: edge_dim=4（4条边）
        self.G = np_to_tensor(robot.G)
        self.h = np_to_tensor(robot.h)
        self.edge_dim = self.G.shape[0]   # 凸包边数 = mu 的输出维度
        self.state_dim = self.G.shape[1]  # 状态维度 = 2 (x, y)

        # === 创建 ObsPointNet ===
        # 从 train_kwargs 中读取 num_classes（多模态扩展）
        num_classes = train_kwargs.get("num_classes", 0) if train_kwargs else 0
        self.model = to_device(ObsPointNet(2, self.edge_dim, num_classes=num_classes))

        # 加载预训练模型权重（找不到则提示训练）
        self.load_model(checkpoint, train_kwargs)

        self.obstacle_points = None   # 当前步的障碍物点（给可视化用）
        self.min_distance = inf       # 最近障碍物距离（给碰撞检测用）

    @time_it('- dune forward')
    def forward(self, point_flow: list[torch.Tensor], R_list: list[torch.Tensor],
                obs_points_list: list[torch.Tensor] = [],
                point_class_list: list[torch.Tensor] = None) -> tuple:
        """
        将点流（T+1 个时刻的点云）编码为 mu、lam 特征序列。

        Args:
            point_flow: T+1 个时刻的点流，每个元素 (2, n_i)，机器人坐标系
            R_list: T+1 个旋转矩阵，每个元素 (2, 2)（从上一帧 nom_s 得到）
            obs_points_list: T+1 时刻的世界坐标系点云（用于排序输出）
            point_class_list: T+1 时刻的类别标签列表（与 point_flow 一一对应）

        Returns:
            mu_list: T+1 个 mu 矩阵，每个 (edge_dim, n_i)（按距离升序）
            lam_list: T+1 个 lam 矩阵，每个 (state_dim, n_i)（按距离升序）
            sort_point_list: T+1 个点云，每个 (2, n_i)（按距离升序）
        """
        mu_list, lam_list, sort_point_list = [], [], []
        # 记录当前时刻（index=0）的障碍物点，用于碰撞检测和可视化
        self.obstacle_points = obs_points_list[0]

        # === 将所有时刻的点拼成一个 batch，一次性通过 ObsPointNet ===
        total_points = torch.hstack(point_flow)  # (2, total_n)

        with torch.no_grad():  # DUNE 推理不参与梯度计算
            if point_class_list is not None:
                # 多模态分支：语义类别也拼接后一次性编码
                total_classes = torch.hstack(point_class_list)  # (total_n,)
                total_mu = self.model(total_points.T, total_classes).T
            else:
                # 原版分支：纯几何编码
                total_mu = self.model(total_points.T).T

        # === 按 receding step 拆分 mu，计算 lam 并排序 ===
        for index in range(self.T + 1):
            num_points = point_flow[index].shape[1]
            mu = total_mu[:, index * num_points: (index + 1) * num_points]

            R = R_list[index]
            p0 = point_flow[index]

            # lam = -R @ G.T @ mu
            # 物理意义: 将 mu（点-边距离）经旋转矩阵 R 变换为
            # 世界坐标系下的碰撞规避方向系数
            lam = (-R @ self.G.T @ mu)

            if mu.ndim == 1:
                mu = mu.unsqueeze(1)
                lam = lam.unsqueeze(1)

            # 计算每个点的目标函数距离: mu^T @ (G @ p0 - h)
            # 该值反映了该点距离机器人表面的"接近程度"
            distance = self.cal_objective_distance(mu, p0)

            # 只记录 index=0（当前时刻）的最小距离，用于碰撞检测
            if index == 0:
                self.min_distance = torch.min(distance)

            # 按距离升序排列（最近点排最前）
            # 这样 NRMP 只看前 nrmp_max_num 个点就得到最危险的障碍物
            sort_indices = torch.argsort(distance)

            mu_list.append(mu[:, sort_indices])
            lam_list.append(lam[:, sort_indices])
            sort_point_list.append(obs_points_list[index][:, sort_indices])

        return mu_list, lam_list, sort_point_list

    def cal_objective_distance(self, mu: torch.Tensor, p0: torch.Tensor) -> torch.Tensor:
        """
        计算每个点与机器人凸包的距离: d_i = mu_i^T @ (G @ p_i - h)

        注意: 这不是真实的欧氏距离，而是经过 mu 加权后的"感知距离"。
              mu 由 ObsPointNet 学习得到，DUNE 训练的目的就是让这个距离
              逼近机器人凸包到点的真实 signed distance。
        """
        temp = (self.G @ p0 - self.h).T.unsqueeze(2)  # (n, edge_dim, 1)
        muT = mu.T.unsqueeze(1)                        # (n, 1, edge_dim)
        distance = torch.squeeze(torch.bmm(muT, temp)) # (n,)
        if distance.ndim == 0:
            distance = distance.unsqueeze(0)
        return distance

    def load_model(self, checkpoint: Optional[str] = None,
                   train_kwargs: Optional[dict] = None):
        """
        加载 DUNE 模型权重。

        搜索路径顺序（由 file_check 实现）:
          1. 完整路径
          2. sys.path[0]/文件名
          3. os.getcwd()/文件名
          4. neupan 包根目录/文件名
        """
        try:
            if checkpoint is None:
                raise FileNotFoundError
            self.abs_checkpoint_path = file_check(checkpoint)
            self.model.load_state_dict(torch.load(
                self.abs_checkpoint_path, map_location=torch.device('cpu')))
            to_device(self.model)
            self.model.eval()  # 推理模式
        except FileNotFoundError:
            # 没找到模型 → 根据配置决定是否自动训练
            if train_kwargs is None or len(train_kwargs) == 0:
                print('No train kwargs provided. Default value will be used.')
                train_kwargs = dict()
            direct_train = train_kwargs.get('direct_train', False)
            if direct_train:
                print('train or test the model directly.')
                return
            if self.ask_to_train():
                self.train_dune(train_kwargs)
                if self.ask_to_continue():
                    self.model.load_state_dict(torch.load(
                        self.full_model_name, map_location=torch.device('cpu')))
                    to_device(self.model)
                    self.model.eval()
                else:
                    print('You can set the new model path to the DUNE class to use the trained model.')
            else:
                print('Can not find checkpoint. Please check the path or train first.')
                raise FileNotFoundError

    def train_dune(self, train_kwargs):
        """启动 DUNE 模型训练"""
        model_name = train_kwargs.get("model_name", self.robot.name)
        checkpoint_path = sys.path[0] + '/model' + '/' + model_name
        checkpoint_path = repeat_mk_dirs(checkpoint_path)
        self.train_model = DUNETrain(self.model, self.G, self.h, checkpoint_path)
        self.full_model_name = self.train_model.start(**train_kwargs)
        print('Complete Training. The model is saved in ' + self.full_model_name)

    def ask_to_train(self):
        """询问用户是否要训练模型"""
        while True:
            choice = input("Do not find the DUNE model; Do you want to train the model now, input Y or N:").upper()
            if choice == 'Y':
                return True
            elif choice == 'N':
                print('Please set the your model path for the DUNE layer.')
                raise FileNotFoundError("DUNE model checkpoint not found and training was declined by user.")
            else:
                print("Wrong input, Please input Y or N.")

    def ask_to_continue(self):
        """训练完成后询问是否继续运行"""
        while True:
            choice = input("Do you want to continue the case running, input Y or N:").upper()
            if choice == 'Y':
                return True
            elif choice == 'N':
                print('exit the case running.')
                raise RuntimeError("User declined to continue after training DUNE model.")
            else:
                print("Wrong input, Please input Y or N.")

    @property
    def points(self):
        """当前 DUNE 层处理的障碍物点（用于可视化）"""
        return self.obstacle_points
