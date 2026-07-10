"""
Configuration file for NeuPan — 全局配置模块
功能：管理 NeuPAN 运行时的全局状态（device、数据类型、转换函数）。
      所有模块通过 `from neupan import configuration` 来读写这些值。

关键设计：
  - device 在 neupan.__init__ 时设定（CPU/CUDA）
  - time_print 控制是否打印 forward 耗时
  - tensor_dtype 统一为 float32（与 cvxpylayers 兼容）
"""

import torch
import numpy as np

# === 全局状态 ===
device = torch.device("cpu")    # 计算设备（默认 CPU，因为 cvxpy 不支持 GPU）
time_print = False              # 是否打印每步 forward 耗时
tensor_dtype = torch.float32    # 全局张量数据类型


def np_to_tensor(array, requires_grad=False):
    """
    NumPy 数组 → torch Tensor（自动搬到 device，转为 tensor_dtype）

    支持标量、多维数组。
    requires_grad=True 时启用梯度追踪（用于 LON 等可训练参数）。
    """
    if np.isscalar(array):
        output_tensor = torch.tensor(array, dtype=tensor_dtype,
                                      requires_grad=requires_grad).to(device)
    else:
        output_tensor = torch.from_numpy(array).type(tensor_dtype).to(device)
    if requires_grad:
        output_tensor.requires_grad_()
    return output_tensor


def tensor_to_np(tensor):
    """
    torch Tensor → NumPy 数组（搬回 CPU → detach → numpy）
    如果传入 None 则返回 None。
    """
    if tensor is None:
        return None
    tensor = tensor.cpu()
    return tensor.detach().numpy()


def value_to_tensor(value, requires_grad=False):
    """
    Python 标量值 → torch Tensor
    用于将 int/float 等标量转换。
    """
    if value is None:
        return None
    return torch.tensor(value, dtype=tensor_dtype,
                         requires_grad=requires_grad).to(device)


def to_device(tensor):
    """将张量搬到全局 device（CPU/CUDA）"""
    return tensor.to(device)
