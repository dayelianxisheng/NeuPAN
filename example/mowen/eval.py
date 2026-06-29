"""mowen 仿真测试
用法: python eval.py               # 跑所有场景
      python eval.py corridor      # 跑指定场景"""
import os, sys, argparse
import numpy as np
import irsim
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from neupan import neupan

DIR = os.path.dirname(__file__)
MODEL = os.path.join(DIR, 'model', 'mowen_real', 'model_5000.pth')

SCENES = ['corridor', 'non_obs', 'convex_obs', 'dyna_obs', 'dyna_non_obs', 'line_obs', 'pf', 'pf_obs', 'polygon_robot']


def run(scene, max_steps=1000):
    env_path = os.path.join(DIR, 'envs', scene, 'env.yaml')
    cfg_path = os.path.join(DIR, 'envs', scene, 'planner.yaml')

    if not os.path.exists(env_path):
        print(f"  {scene}: SKIP (no env)")
        return None

    env = irsim.make(env_path, display=True)
    planner = neupan.init_from_yaml(cfg_path)
    goal_pos = np.array(planner.ipath.waypoints[-1][:2]).flatten()

    for i in range(max_steps):
        state = env.get_robot_state()
        scan = env.get_lidar_scan()
        pts, vels = None, None
        if scan.get('velocity') is not None:
            pts, vels = planner.scan_to_point_velocity(state, scan)
        else:
            pts = planner.scan_to_point(state, scan)
        action, info = planner(state, pts, vels)
        goal_dist = np.linalg.norm(state[:2].flatten() - goal_pos)
        pidx = planner.ipath.point_index
        cidx = planner.ipath.curve_index
        clen = len(planner.ipath.cur_curve)
        if i == 150:
            cc = planner.ipath.cur_curve
            print(f"=== curve[{clen}] around pidx=139 ===")
            for j in range(max(0,135), min(clen, 150)):
                pt = cc[j]
                print(f"  [{j}]: x={pt[0,0]:.3f} y={pt[1,0]:.3f} theta={pt[2,0]:.3f}")
        if i == 400:
            cc = planner.ipath.cur_curve
            print(f"=== curve[{clen}] around pidx=205 ===")
            for j in range(max(0,195), min(clen, 215)):
                pt = cc[j]
                print(f"  [{j}]: x={pt[0,0]:.3f} y={pt[1,0]:.3f} theta={pt[2,0]:.3f}")
        if info.get('stop'):
            print(f"step {i:3d}: pos=({state[0,0]:.2f},{state[1,0]:.2f}) goal_dist={goal_dist:.2f} pidx={pidx}/{clen} cidx={cidx} stop=True arrive=False min_dist={planner.min_distance:.3f}")
            env.end(3)
            return False
        if info.get('arrive'):
            print(f"step {i:3d}: pos=({state[0,0]:.2f},{state[1,0]:.2f}) goal_dist={goal_dist:.2f} pidx={pidx}/{clen} cidx={cidx} stop=False arrive=True min_dist={planner.min_distance:.3f}")
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
            # 再次规划获取终态
            state2 = env.get_robot_state()
            pts2 = planner.scan_to_point(state2, scan) if scan.get('velocity') is None else planner.scan_to_point_velocity(state2, scan)[0]
            _, info2 = planner(state2, pts2, None)
            gd2 = np.linalg.norm(state2[:2].flatten() - goal_pos)
            p2 = planner.ipath.point_index
            print(f"step {i+1:3d}: pos=({state2[0,0]:.2f},{state2[1,0]:.2f}) goal_dist={gd2:.2f} pidx={p2}/{len(planner.ipath.cur_curve)} cidx={planner.ipath.curve_index} stop={info2.get('stop')} arrive={info2.get('arrive')} min_dist={planner.min_distance:.3f}")
            if info2.get('arrive') or gd2 < 0.3:
                env.end(3)
                return True
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
