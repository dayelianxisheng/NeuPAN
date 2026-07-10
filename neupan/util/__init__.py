"""
util — NeuPAN 工具函数集合

功能：
  - time_it: 函数耗时测量装饰器
  - file_check: 文件路径搜索（支持4种解析方式）
  - WrapToPi: 角度归一化 [-π, π]
  - distance: 2D 距离计算
  - get_transform: 从状态提取旋转平移矩阵
  - gen_inequal_from_vertex: 从凸包顶点生成 G/h 不等式
  - is_convex_and_ordered / cross_product: 凸性检测
  - repeat_mk_dirs: 避重目录创建
  - downsample_decimation: 均匀下采样
"""

from __future__ import annotations

import time
from neupan import configuration
import os
import sys
from math import sqrt, pi, cos, sin
import numpy as np
import neupan


def time_it(name="Function"):
    """
    函数耗时测量装饰器。

    当 configuration.time_print = True 时，每次函数调用后打印耗时。
    用于 forward 性能监控。

    Args:
        name: 打印时显示的函数名
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            wrapper.count += 1
            start = time.time()
            result = func(self, *args, **kwargs)
            end = time.time()
            wrapper.func_count += 1
            if configuration.time_print:
                print(f"{name} execute time {(end - start):.6f} seconds")
            return result
        wrapper.count = 0
        wrapper.func_count = 0
        return wrapper
    return decorator


def file_check(file_name):
    """
    检查文件存在性，按优先级搜索4个路径。

    搜索顺序:
      1. 完整路径（直接 os.path.exists）
      2. sys.path[0] / 文件名（脚本运行目录）
      3. os.getcwd() / 文件名（当前工作目录）
      4. neupan 包根目录 / 文件名

    Raises:
        FileNotFoundError: 所有路径都找不到
    """
    root_path = os.path.dirname(os.path.dirname(neupan.__file__))

    if file_name is None:
        return None
    if os.path.exists(file_name):
        return file_name
    if os.path.exists(sys.path[0] + "/" + file_name):
        return sys.path[0] + "/" + file_name
    if os.path.exists(os.getcwd() + "/" + file_name):
        return os.getcwd() + "/" + file_name

    if root_path is None:
        raise FileNotFoundError("File not found: " + file_name)
    root_file_name = root_path + "/" + file_name
    if os.path.exists(root_file_name):
        return root_file_name

    raise FileNotFoundError("File not found: " + file_name)


def WrapToPi(rad: float, positive: bool = False) -> float:
    """
    将角度归一化到 [-π, π] 范围。

    Args:
        rad: 输入角度 (rad)
        positive: True 时返回 [0, π] 的绝对值

    用途: 角度差计算、theta 归一化。
    """
    while rad > pi:
        rad = rad - 2 * pi
    while rad < -pi:
        rad = rad + 2 * pi
    return rad if not positive else abs(rad)


def distance(point1: np.ndarray, point2: np.ndarray) -> float:
    """
    计算两个 2D 点之间的欧氏距离。

    Args:
        point1: (2, 1) 或 (2,)
        point2: (2, 1) 或 (2,)
    """
    return sqrt((point1[0, 0] - point2[0, 0]) ** 2
                + (point1[1, 0] - point2[1, 0]) ** 2)


def get_transform(state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    从状态中提取旋转矩阵和平移向量。

    Args:
        state: (3, 1) [x, y, theta] 或 (2, 1) [x, y]

    Returns:
        trans: (2,) 平移向量
        rot:   (2, 2) 旋转矩阵

    用途: scan_to_point 和 generate_point_flow 中的坐标变换
    """
    if state.shape == (2, 1):
        rot = np.array([[1, 0], [0, 1]])
        trans = state[0:2]
    else:
        rot = np.array([
            [cos(state[2, 0]), -sin(state[2, 0])],
            [sin(state[2, 0]), cos(state[2, 0])],
        ])
        trans = state[0:2]
    return trans, rot


def gen_inequal_from_vertex(vertex: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    从凸多边形顶点生成半平面不等式: G @ x <= h

    对每条边 (v_i → v_{i+1}) 求法向量:
      a = dy, b = -dx, c = a*x_i + b*y_i
    G[i] = [a, b], h[i] = c

    Args:
        vertex: (2, N) 逆时针排列的凸多边形顶点

    Returns:
        G: (N, 2) 不等式系数矩阵
        h: (N, 1) 不等式右侧向量

    如果输入多边形不是凸的，返回 (None, None)。
    """
    convex_flag, order = is_convex_and_ordered(vertex)

    if not convex_flag:
        print("The polygon constructed by vertex is not convex.")
        return None, None

    # 如果是顺时针，反转为逆时针
    if order == "CW":
        first_point = vertex[:, 0:1]
        rest_points = vertex[:, 1:]
        vertex = np.hstack([first_point, rest_points[:, ::-1]])

    num = vertex.shape[1]
    G = np.zeros((num, 2))
    h = np.zeros((num, 1))

    for i in range(num):
        if i + 1 < num:
            pre_point = vertex[:, i]
            next_point = vertex[:, i + 1]
        else:
            pre_point = vertex[:, i]
            next_point = vertex[:, 0]

        diff = next_point - pre_point
        a = diff[1]
        b = -diff[0]
        c = a * pre_point[0] + b * pre_point[1]
        G[i, 0] = a
        G[i, 1] = b
        h[i, 0] = c

    return G, h


def is_convex_and_ordered(points: np.ndarray):
    """
    判断多边形是否是凸的，并返回顶点顺序。

    用叉积法：遍历所有相邻三条边，叉积方向必须一致。

    Returns:
        (bool, str): (是否凸, 'CW'/'CCW'/'None')
    """
    n = points.shape[1]  # 顶点数
    if n < 3:
        return False, None

    direction = 0
    for i in range(n):
        o = points[:, i]
        a = points[:, (i + 1) % n]
        b = points[:, (i + 2) % n]
        cross = cross_product(o, a, b)
        if cross != 0:
            if direction == 0:
                direction = 1 if cross > 0 else -1
            elif (cross > 0 and direction < 0) or (cross < 0 and direction > 0):
                return False, None  # 方向改变 → 不是凸多边形

    return True, "CCW" if direction > 0 else "CW"


def cross_product(o, a, b) -> float:
    """
    计算向量 OA 和 OB 的叉积（z 分量）。

    cross = (a.x - o.x)*(b.y - o.y) - (a.y - o.y)*(b.x - o.x)

    用于判断多边形顶点顺序和凸性。
    """
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def repeat_mk_dirs(path, max_num=100):
    """
    创建目录，如果已存在则追加编号（_1, _2, ...）。

    用于 DUNE 训练时自动生成不重复的模型保存目录。
    """
    if not os.path.exists(path):
        os.makedirs(path)
        return path
    else:
        if len(os.listdir(path)) == 0:
            return path
        else:
            i = 1
            while i < max_num:
                new_path = path + "_" + str(i)
                i += 1
                if not os.path.exists(new_path):
                    break
            os.makedirs(new_path)
            return new_path


def downsample_decimation(mat, m):
    """
    将 d×n 矩阵均匀下采样为 d×m（线性选取 m 个样本）。

    用于点数超过 dune_max_num 时降低计算量。

    Args:
        mat: (d, n) 输入矩阵
        m: 目标列数

    Returns:
        (d, m) 下采样后的矩阵
    """
    n = mat.shape[1]
    if m >= n:
        return mat
    indices = np.linspace(0, n - 1, m).astype(int)
    return mat[:, indices]
