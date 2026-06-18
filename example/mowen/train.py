"""训练 mowen 真实尺寸 DUNE 模型"""
import sys
import argparse
from neupan import neupan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='envs/train.yaml', help='训练配置文件')
    args = parser.parse_args()
    neupan_planner = neupan.init_from_yaml(args.config)
    neupan_planner.train_dune()


if __name__ == '__main__':
    main()
