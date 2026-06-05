"""
用自己训练的 DUNE 模型测试所有 diff 场景

用法:
    python eval.py -e corridor      # 单场景
    python eval.py -e all           # 全部9个场景

场景: corridor, convex_obs, dyna_non_obs, dyna_obs, non_obs,
      pf, pf_obs, polygon_robot, reverse

逻辑: 使用各场景自带的 planner.yaml (路点/环境匹配)，然后替换为你训练的 DUNE 权重
"""
from neupan import neupan
import irsim
import torch
import argparse

MODEL_PATH = "model/my_diff_robot/model_1500.pth"

SCENARIOS = [
    "corridor", "convex_obs", "dyna_non_obs", "dyna_obs",
    "non_obs", "pf", "pf_obs", "polygon_robot", "reverse",
]


def run_scenario(scenario, max_steps=1000):
    env_path = f"../{scenario}/diff/env.yaml"
    planner_path = f"../{scenario}/diff/planner.yaml"

    print(f"\n{'='*50}")
    print(f"  {scenario}/diff  ({MODEL_PATH})")
    print(f"{'='*50}")

    env = irsim.make(env_path, save_ani=False, full=False, display=True)
    planner = neupan.init_from_yaml(planner_path)

    # 替换为你的训练权重
    checkpoint = torch.load(MODEL_PATH, map_location="cpu")
    planner.pan.dune_layer.model.load_state_dict(checkpoint)
    planner.pan.dune_layer.model.eval()
    print(f"  Loaded custom weights: {MODEL_PATH}")

    for i in range(max_steps):
        state = env.get_robot_state()
        scan = env.get_lidar_scan()
        points = planner.scan_to_point(state, scan)
        action, info = planner(state, points)

        if info["stop"]:
            print(f"[{scenario}] STOP: too close to obstacle")
            break
        if info["arrive"]:
            print(f"[{scenario}] ARRIVED at target")
            break

        env.draw_points(planner.dune_points, s=25, c="g", refresh=True)
        env.draw_points(planner.nrmp_points, s=13, c="r", refresh=True)
        env.draw_trajectory(planner.opt_trajectory, "r", refresh=True)
        env.draw_trajectory(planner.ref_trajectory, "b", refresh=True)
        env.step(action)
        env.render()

        if i == 0:
            env.draw_trajectory(planner.initial_path, traj_type="-k", show_direction=False)
            env.render()
        if env.done():
            break

    env.end(3, ani_name=f"my_diff_{scenario}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--example", type=str, default="corridor",
                        help=f"Scenario or 'all'. Choices: {', '.join(SCENARIOS)}")
    parser.add_argument("-m", "--max_steps", type=int, default=1000)
    parser.add_argument("--model", type=str, default=MODEL_PATH,
                        help="Path to trained DUNE checkpoint")
    args = parser.parse_args()

    if args.example == "all":
        for s in SCENARIOS:
            run_scenario(s, args.max_steps)
    elif args.example in SCENARIOS:
        run_scenario(args.example, args.max_steps)
    else:
        print(f"Unknown '{args.example}'. Available: {', '.join(SCENARIOS)}")
        exit(1)
