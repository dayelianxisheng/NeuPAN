"""
训练 DUNE 模型 — 使用与 corridor/diff 示例完全相同的参数

训练完成后模型保存在 example/model/my_diff_robot/
"""
from neupan import neupan

if __name__ == '__main__':
    neupan_planner = neupan.init_from_yaml('train.yaml')
    neupan_planner.train_dune()
