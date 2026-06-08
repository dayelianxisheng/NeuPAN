"""
用自己训练的 DUNE 模型测试所有 diff 场景

用法:
    python eval.py -e corridor              # 单场景
    python eval.py -e all                   # 全部9个场景
    python eval.py -e corridor -a           # 保存动态图

场景: corridor, convex_obs, dyna_non_obs, dyna_obs, non_obs,
      pf, pf_obs, polygon_robot, reverse
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


def run_scenario(scenario, model_path, max_steps=1000, save_ani=False, full=False):
    env_path = f"../{scenario}/diff/env.yaml"
    planner_path = f"../{scenario}/diff/planner.yaml"
    ani_name = f"my_diff_{scenario}"

    print(f"\n{'='*50}")
    print(f"  {scenario}/diff  ({model_path})")
    if save_ani:
        print(f"  Save animation: animation/{ani_name}.gif")
    print(f"{'='*50}")

    env = irsim.make(env_path, save_ani=save_ani, full=full, display=True)
    planner = neupan.init_from_yaml(planner_path)

    if planner.pan.dune_layer is not None:
        checkpoint = torch.load(model_path, map_location="cpu")
        planner.pan.dune_layer.model.load_state_dict(checkpoint)
        planner.pan.dune_layer.model.eval()
        print(f"  Loaded custom weights: {model_path}")
    else:
        print(f"  [SKIP] No DUNE layer in this scenario, using default config")

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

        if planner.dune_points is not None:
            env.draw_points(planner.dune_points, s=25, c="g", refresh=True)
        if planner.nrmp_points is not None:
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

    env.end(3, ani_name=ani_name)
    if save_ani:
        print(f"  Animation saved: animation/{ani_name}.gif")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--example", type=str, default="corridor",
                        help=f"Scenario or 'all'. Choices: {', '.join(SCENARIOS)}")
    parser.add_argument("-m", "--max_steps", type=int, default=1000)
    parser.add_argument("-a", "--save_animation", action="store_true",
                        help="Save animation as GIF")
    parser.add_argument("-f", "--full", action="store_true",
                        help="Full screen mode")
    parser.add_argument("--model", type=str, default=MODEL_PATH,
                        help="Path to trained DUNE checkpoint")
    args = parser.parse_args()

    if args.example == "all":
        for s in SCENARIOS:
            run_scenario(s, args.model, args.max_steps, args.save_animation, args.full)
    elif args.example in SCENARIOS:
        run_scenario(args.example, args.model, args.max_steps, args.save_animation, args.full)
    else:
        print(f"Unknown '{args.example}'. Available: {', '.join(SCENARIOS)}")
        exit(1)
