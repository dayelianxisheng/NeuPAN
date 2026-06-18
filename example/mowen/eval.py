"""mowen 仿真测试
用法: python eval.py               # 跑所有场景
      python eval.py corridor      # 跑指定场景"""
import os, sys, argparse
import irsim
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from neupan import neupan

DIR = os.path.dirname(__file__)
MODEL = os.path.join(DIR, 'model', 'mowen_real', 'model_5000.pth')

SCENES = ['corridor', 'non_obs', 'convex_obs', 'dyna_obs', 'dyna_non_obs', 'pf', 'pf_obs', 'polygon_robot']


def run(scene, max_steps=500):
    env_path = os.path.join(DIR, 'envs', scene, 'env.yaml')
    cfg_path = os.path.join(DIR, 'envs', scene, 'planner.yaml')

    if not os.path.exists(env_path):
        print(f"  {scene}: SKIP (no env)")
        return None

    env = irsim.make(env_path, display=True)
    planner = neupan.init_from_yaml(cfg_path)

    for i in range(max_steps):
        state = env.get_robot_state()
        scan = env.get_lidar_scan()
        pts, vels = None, None
        if scan.get('velocity') is not None:
            pts, vels = planner.scan_to_point_velocity(state, scan)
        else:
            pts = planner.scan_to_point(state, scan)
        action, info = planner(state, pts, vels)
        if info.get('stop'):
            env.end(3)
            return False
        if info.get('arrive'):
            env.end(3)
            return True
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
    env.end(3)
    return False


if __name__ == '__main__':
    if not os.path.exists(MODEL):
        print("先训练: python train.py"); exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument('scene', nargs='?', choices=SCENES, help='场景名（可选，不填跑全部）')
    args = parser.parse_args()

    if args.scene:
        result = run(args.scene)
        print(f"\n{args.scene}: {'OK' if result else 'FAIL'}")
    else:
        print(f"\n{'场景':<20} {'结果':<10}")
        print("-" * 30)
        for s in SCENES:
            result = run(s)
            status = 'OK' if result else ('FAIL' if result is False else 'SKIP')
            print(f"{s:<20} {status:<10}")
