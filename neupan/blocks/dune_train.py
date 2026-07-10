"""
DUNETrain — DUNE 模型训练器
功能：生成合成随机点 + 凸包优化求解 → ground truth mu → 训练 ObsPointNet

训练数据：随机点 (x,y) + 随机类别标签 → ObsPointNet → mu
         ground truth mu 通过凸优化问题求解得到（纯几何，与类别无关）

训练策略：
  - num_classes=0: 纯几何训练（等同于原版）
  - num_classes>0: 随机分配类别标签，让网络学习"不同类别"的 mu 差异
"""

from __future__ import annotations

import torch
from colorama import deinit
deinit()

from torch.utils.data import Dataset, random_split, DataLoader
import cvxpy as cp
from rich.console import Console
from rich.progress import Progress
from rich.live import Live
from torch.optim import Adam
import numpy as np
from neupan.configuration import np_to_tensor, value_to_tensor, to_device
import pickle
import time
import os


class PointDataset(Dataset):
    def __init__(self, input_data, label_data, distance_data, class_data=None):
        """
        Args:
            input_data: list of (2, 1) tensors — 点坐标
            label_data: list of (edge_dim, 1) tensors — ground truth mu
            distance_data: list of scalar tensors — ground truth 距离
            class_data: list of int or None — 类别标签
        """
        self.input_data = input_data
        self.label_data = label_data
        self.distance_data = distance_data
        self.class_data = class_data

    def __len__(self):
        return len(self.input_data)

    def __getitem__(self, idx):
        if self.class_data is not None:
            return (self.input_data[idx], self.label_data[idx],
                    self.distance_data[idx], self.class_data[idx])
        return (self.input_data[idx], self.label_data[idx], self.distance_data[idx])


class DUNETrain:
    def __init__(self, model, robot_G, robot_h, checkpoint_path) -> None:
        self.G = robot_G
        self.h = robot_h
        self.model = model

        # 检测模型是否有语义嵌入层
        self.num_classes = model.class_embed.num_embeddings if model.class_embed else 0

        self.construct_problem()
        self.checkpoint_path = checkpoint_path

        self.loss_fn = torch.nn.MSELoss()
        self.optimizer = Adam(self.model.parameters(), lr=1e-4, weight_decay=1e-4)

        self.console = Console()
        self.progress = Progress(transient=False)
        self.live = Live(self.progress, console=self.console, auto_refresh=False)

        self.loss_of_epoch = 0
        self.loss_list = []

    def construct_problem(self):
        """
        凸优化问题:
          max  mu^T * (G * p - h)
          s.t. ||G^T * mu|| <= 1
               mu >= 0
        求解得到 ground truth mu（纯几何，不依赖类别）
        """
        self.mu = cp.Variable((self.G.shape[0], 1), nonneg=True)
        self.p = cp.Parameter((2, 1))
        cost = self.mu.T @ (self.G.cpu() @ self.p - self.h.cpu())
        constraints = [cp.norm(self.G.cpu().T @ self.mu) <= 1]
        self.prob = cp.Problem(cp.Maximize(cost), constraints)

    def process_data(self, rand_p):
        """给定点坐标 → 求解凸优化 → 返回 (point_tensor, mu_tensor, distance_tensor)"""
        distance_value, mu_value = self.prob_solve(rand_p)
        return (
            np_to_tensor(rand_p),
            np_to_tensor(mu_value),
            value_to_tensor(distance_value),
        )

    def generate_data_set(self, data_size=10000, data_range=[-50, -50, 50, 50]):
        """
        生成训练数据集。

        Args:
            data_size: 数据量
            data_range: [x_min, y_min, x_max, y_max]

        Returns:
            dataset: PointDataset，如果 num_classes>0 则包含 class_data
        """
        input_data = []
        label_data = []
        distance_data = []
        class_data = []

        rand_p = np.random.uniform(
            low=data_range[:2], high=data_range[2:], size=(data_size, 2)
        )
        rand_p_list = [rand_p[i].reshape(2, 1) for i in range(data_size)]

        # 随机类别标签（如果模型带语义嵌入）
        if self.num_classes > 0:
            # 按比例分配: 0=background(40%), 1=obstacle(40%), 2=ignorable(20%)
            weights = np.ones(self.num_classes, dtype=float)
            weights /= weights.sum()
            rand_class = np.random.choice(self.num_classes, size=data_size, p=weights)
        else:
            rand_class = None

        for i, p in enumerate(rand_p_list):
            results = self.process_data(p)
            input_data.append(results[0])
            label_data.append(results[1])
            distance_data.append(results[2])
            if rand_class is not None:
                class_data.append(rand_class[i])

        # 如果不需要语义，用原版 Dataset（避免 DataLoader 解包不匹配）
        if self.num_classes == 0:
            dataset = PointDataset(input_data, label_data, distance_data)
        else:
            dataset = PointDataset(input_data, label_data, distance_data, class_data)

        return dataset

    def prob_solve(self, p_value):
        self.p.value = p_value
        self.prob.solve(solver=cp.ECOS)
        return self.prob.value, self.mu.value

    def start(self, data_size=100000, data_range=[-25, -25, 25, 25],
              batch_size=256, epoch=5000, valid_freq=100, save_freq=500,
              lr=5e-5, lr_decay=0.5, decay_freq=1500, save_loss=False, **kwargs):
        """启动训练"""

        train_dict = {
            "data_size": data_size, "data_range": data_range,
            "batch_size": batch_size, "epoch": epoch,
            "valid_freq": valid_freq, "save_freq": save_freq,
            "lr": lr, "lr_decay": lr_decay, "decay_freq": decay_freq,
            "robot_G": self.G, "robot_h": self.h, "model": self.model,
        }
        with open(self.checkpoint_path + "/train_dict.pkl", "wb") as f:
            pickle.dump(train_dict, f)

        print(f"data_size: {data_size}, data_range: {data_range}, "
              f"batch_size: {batch_size}, epoch: {epoch}, "
              f"num_classes: {self.num_classes}, "
              f"lr: {lr}, lr_decay: {lr_decay}, decay_freq: {decay_freq}, "
              f"robot_G: {self.G}, robot_h: {self.h}")

        with open(self.checkpoint_path + "/results.txt", "a") as f:
            print(f"data_size: {data_size}, data_range: {data_range}, "
                  f"batch_size: {batch_size}, epoch: {epoch}, "
                  f"num_classes: {self.num_classes}, "
                  f"lr: {lr}, lr_decay: {lr_decay}, decay_freq: {decay_freq}, "
                  f"robot_G: {self.G}, robot_h: {self.h}\n", file=f)

        self.optimizer.param_groups[0]["lr"] = float(lr)
        full_model_name = None

        print("dataset generating start ...")
        dataset = self.generate_data_set(data_size, data_range)
        train, valid, _ = random_split(
            dataset, [int(data_size * 0.8), int(data_size * 0.2), 0]
        )

        train_dataloader = DataLoader(train, batch_size=batch_size)
        valid_dataloader = DataLoader(valid, batch_size=batch_size)

        print("dataset training start ...")

        with self.live:
            task = self.progress.add_task("[cyan]Training...", total=epoch)

            for i in range(epoch + 1):

                self.progress.update(task, advance=1)
                self.live.refresh()

                self.model.train(True)

                mu_loss, distance_loss, fa_loss, fb_loss = self.train_one_epoch(
                    train_dataloader, False
                )

                ml = "{:.2e}".format(mu_loss)
                dl = "{:.2e}".format(distance_loss)
                al = "{:.2e}".format(fa_loss)
                bl = "{:.2e}".format(fb_loss)

                if i % valid_freq == 0:
                    self.model.eval()
                    (vm, vd, va, vb) = self.train_one_epoch(valid_dataloader, True)
                    vml, vdl, val, vbl = (
                        "{:.2e}".format(vm), "{:.2e}".format(vd),
                        "{:.2e}".format(va), "{:.2e}".format(vb),
                    )

                    self.print_loss(i, epoch, ml, dl, al, bl, vml, vdl, val, vbl,
                                    self.optimizer.param_groups[0]["lr"])
                    with open(self.checkpoint_path + "/results.txt", "a") as f:
                        self.print_loss(i, epoch, ml, dl, al, bl, vml, vdl, val, vbl,
                                        self.optimizer.param_groups[0]["lr"], f)

                if i % save_freq == 0:
                    print(f"save model at epoch {i}")
                    path = f"{self.checkpoint_path}/model_{i}.pth"
                    torch.save(self.model.state_dict(), path)
                    full_model_name = path

                if (i + 1) % decay_freq == 0:
                    self.optimizer.param_groups[0]["lr"] *= lr_decay
                    lr_now = self.optimizer.param_groups[0]["lr"]
                    print(f"current learning rate: {lr_now}")
                    with open(self.checkpoint_path + "/results.txt", "a") as f:
                        print(f"current learning rate: {lr_now}", file=f)

                self.loss_of_epoch = mu_loss + distance_loss + fa_loss + fb_loss
                self.loss_list.append(self.loss_of_epoch)

                if save_loss:
                    with open(self.checkpoint_path + "/loss.pkl", "wb") as f:
                        pickle.dump(self.loss_list, f)

        print(f"finish train, the model is saved in {full_model_name}")
        return full_model_name

    def train_one_epoch(self, dataloader, validate=False):
        """
        训练一个 epoch。

        如果模型有语义嵌入层（num_classes>0），DataLoader 会返回 4 元组，
        最后一个元素是 class_ids，传入 model 时作为第二个参数。
        """
        mu_loss, distance_loss, fa_loss, fb_loss = 0, 0, 0, 0

        for batch in dataloader:
            # 判断是否为语义模式（4 元组 vs 3 元组）
            if self.num_classes > 0 and len(batch) == 4:
                input_point, label_mu, label_distance, class_id = batch
                class_id = torch.squeeze(class_id).long()
            else:
                input_point, label_mu, label_distance = batch
                class_id = None

            self.optimizer.zero_grad()

            input_point = torch.squeeze(input_point)  # (B, 2)

            # 传入 class_ids 给模型（确保在同一个 device 上）
            if class_id is not None:
                # 搬到模型所在设备
                device = next(self.model.parameters()).device
                output_mu = self.model(input_point, class_id.to(device))
            else:
                output_mu = self.model(input_point)

            output_mu = torch.unsqueeze(output_mu, 2)  # (B, 4, 1)

            distance = self.cal_distance(output_mu, input_point)

            mse_mu = self.loss_fn(output_mu, label_mu)
            mse_distance = self.loss_fn(distance, label_distance)
            mse_fa, mse_fb = self.cal_loss_fab(output_mu, label_mu, input_point)

            loss = mse_mu + mse_distance + mse_fa + mse_fb

            if not validate:
                loss.backward()
                self.optimizer.step()

            mu_loss += mse_mu.item()
            distance_loss += mse_distance.item()
            fa_loss += mse_fa.item()
            fb_loss += mse_fb.item()

        denom = len(dataloader)
        return (mu_loss / denom, distance_loss / denom,
                fa_loss / denom, fb_loss / denom)

    def cal_loss_fab(self, output_mu, label_mu, input_point):
        """
        fa: -mu^T * G * R^T  (lam^T)
        fb: mu^T * G * R^T * p - mu^T * h  (lam^T * p + mu^T * h)
        """
        mu1 = output_mu
        mu2 = label_mu
        ip = torch.unsqueeze(input_point, 2)
        mu1T = torch.transpose(mu1, 1, 2)
        mu2T = torch.transpose(mu2, 1, 2)

        theta = np.random.uniform(0, 2 * np.pi)
        R = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        R = np_to_tensor(R)

        fa = torch.transpose(-R @ self.G.T @ mu1, 1, 2)
        fa_label = torch.transpose(-R @ self.G.T @ mu2, 1, 2)

        fb = fa @ ip + mu1T @ self.h
        fb_label = fa_label @ ip + mu2T @ self.h

        mse_lamt = self.loss_fn(fa, fa_label)
        mse_lamtb = self.loss_fn(fb, fb_label)

        return mse_lamt, mse_lamtb

    def cal_distance(self, mu, input_point):
        input_point = torch.unsqueeze(input_point, 2)
        temp = self.G @ input_point - self.h
        muT = torch.transpose(mu, 1, 2)
        distance = torch.squeeze(torch.bmm(muT, temp))
        return distance

    def print_loss(self, i, epoch, ml, dl, al, bl, vml, vdl, val, vbl, lr, file=None):
        fmt = (
            "Epoch {}/{} learning rate {} \n"
            "---------------------------------\n"
            "Losses:\n"
            "  Mu Loss:          {} | Validate Mu Loss:          {}\n"
            "  Distance Loss:    {} | Validate Distance Loss:    {}\n"
            "  Fa Loss:          {} | Validate Fa Loss:          {}\n"
            "  Fb Loss:          {} | Validate Fb Loss:          {}\n"
        ).format(i, epoch, lr,
                 str(ml).ljust(10), str(vml).rjust(10),
                 str(dl).ljust(10), str(vdl).rjust(10),
                 str(al).ljust(10), str(val).rjust(10),
                 str(bl).ljust(10), str(vbl).rjust(10))
        if file is None:
            print(fmt)
        else:
            print(fmt, file=file)
