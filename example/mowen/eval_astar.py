"""mowen 仿真测试（A* 关键点引导 + NeuPAN 自主导航）
用法: python eval_astar.py maze_obs

设计原则：
  - A* 规划全局路径，只提取"不平衡点"（转弯/方向突变处）作为 waypoints
  - 直路/动态避障 → 完全交给 NeuPAN
  - 不做卡住检测、重规划、参考线干预
"""
import os, sys, math, yaml
import numpy as np
import irsim

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from neupan import neupan

DIR = os.path.dirname(__file__)


# ========== A* 规划器 ==========

class AStar:
    def __init__(self, grid, resolution, origin):
        self.grid = grid
        self.res = resolution
        self.origin = origin
        self.h = grid.shape[0]
        self.w = grid.shape[1]

    def world_to_grid(self, x, y):
        gx = int(round((x - self.origin[0]) / self.res))
        gy = int(round((y - self.origin[1]) / self.res))
        return max(0, min(gx, self.w-1)), max(0, min(gy, self.h-1))

    def grid_to_world(self, gx, gy):
        x = gx * self.res + self.origin[0]
        y = gy * self.res + self.origin[1]
        return x, y

    def plan(self, sx, sy, gx, gy):
        start = self.world_to_grid(sx, sy)
        goal = self.world_to_grid(gx, gy)

        for name, pt in [("起点", start), ("终点", goal)]:
            if not (0 <= pt[0] < self.w and 0 <= pt[1] < self.h):
                print(f"  ❌ {name} 超出地图边界")
                return None
            if self.grid[pt[1], pt[0]]:
                print(f"  ❌ {name} 在障碍物上")
                return None

        open_set = {start}
        came_from = {}
        g_score = {start: 0.0}
        f_score = {start: self._heuristic(start, goal)}

        while open_set:
            current = min(open_set, key=lambda p: f_score.get(p, float('inf')))
            if current == goal:
                return self._reconstruct(came_from, current)

            open_set.remove(current)
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
                nx, ny = current[0]+dx, current[1]+dy
                if not (0 <= nx < self.w and 0 <= ny < self.h):
                    continue
                if self.grid[ny, nx]:
                    continue
                neighbor = (nx, ny)
                move_cost = math.hypot(dx, dy) * self.res
                tentative = g_score[current] + move_cost
                if tentative < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative
                    f_score[neighbor] = tentative + self._heuristic(neighbor, goal)
                    open_set.add(neighbor)
        return None

    def _heuristic(self, a, b):
        return math.hypot(a[0]-b[0], a[1]-b[1]) * self.res

    def _reconstruct(self, came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path


# ========== 构建栅格地图 ==========

def is_point_in_rect(px, py, cx, cy, length, width, theta):
    dx, dy = px - cx, py - cy
    cos_t, sin_t = math.cos(-theta), math.sin(-theta)
    rx = dx * cos_t - dy * sin_t
    ry = dx * sin_t + dy * cos_t
    return abs(rx) <= length/2 and abs(ry) <= width/2


def is_point_in_circle(px, py, cx, cy, radius):
    return math.hypot(px-cx, py-cy) <= radius


def build_grid_from_env(env_path, robot_radius=0.22, resolution=0.05):
    with open(env_path) as f:
        env_cfg = yaml.safe_load(f)

    offset = env_cfg['world'].get('offset', [0, 0])
    w_world = env_cfg['world']['width']
    h_world = env_cfg['world']['height']
    ox, oy = offset

    robot_cfg = env_cfg['robot'][0]
    start_pos = robot_cfg['state'][:2]
    goal_pos = robot_cfg['goal'][:2]
    x_min = min(ox, start_pos[0] - 0.5, goal_pos[0] - 0.5)
    y_min = min(oy, start_pos[1] - 0.5, goal_pos[1] - 0.5)
    x_max = max(ox + w_world, start_pos[0] + 0.5, goal_pos[0] + 0.5)
    y_max = max(oy + h_world, start_pos[1] + 0.5, goal_pos[1] + 0.5)

    gw = int((x_max - x_min) / resolution) + 2
    gh = int((y_max - y_min) / resolution) + 2
    grid = np.zeros((gh, gw), dtype=np.uint8)
    inflate = int(robot_radius / resolution) + 1

    all_obs = []
    for obs_group in env_cfg.get('obstacle', []):
        dist = obs_group.get('distribution', {})
        if isinstance(dist, dict) and dist.get('name') != 'manual':
            continue
        if 'state' not in obs_group:
            continue
        shapes = obs_group['shape']
        states = obs_group['state']
        for shape, state in zip(shapes, states):
            all_obs.append((shape, state))

    for gy in range(gh):
        for gx in range(gw):
            wx = x_min + gx * resolution
            wy = y_min + gy * resolution
            for shape, state in all_obs:
                cx, cy = state[0], state[1]
                theta = state[2] if len(state) > 2 else 0
                hit = False
                if 'rectangle' in shape.get('name', ''):
                    if is_point_in_rect(wx, wy, cx, cy, shape['length'], shape['width'], theta):
                        hit = True
                elif 'circle' in shape.get('name', ''):
                    if is_point_in_circle(wx, wy, cx, cy, shape['radius']):
                        hit = True
                if hit:
                    for dy in range(-inflate, inflate+1):
                        for dx in range(-inflate, inflate+1):
                            ngx, ngy = gx+dx, gy+dy
                            if 0 <= ngx < gw and 0 <= ngy < gh:
                                grid[ngy, ngx] = 1
                    break

    return grid, resolution, (x_min, y_min), (x_min, x_max, y_min, y_max)


# ========== 提取关键引导点 ==========

def extract_key_waypoints(astar, path, gx, gy, angle_thresh=0.3, min_gap=5):
    """
    从 A* 路径中提取"不平衡点"——方向突变的转弯处。
    策略：连续方向变化 > angle_thresh 的地方记为一个关键点。
    只保留：起点(跳过) + 转弯点 + 终点。
    """
    if len(path) < 3:
        return [[[gx], [gy], [0.0]]]

    # 计算每个路径点的世界坐标和方向
    world_pts = [astar.grid_to_world(px, py) for px, py in path]

    # 检测方向突变
    key_indices = set()
    prev_angle = None
    for i in range(1, len(world_pts) - 1):
        dx1 = world_pts[i][0] - world_pts[i-1][0]
        dy1 = world_pts[i][1] - world_pts[i-1][1]
        dx2 = world_pts[i+1][0] - world_pts[i][0]
        dy2 = world_pts[i+1][1] - world_pts[i][1]

        if math.hypot(dx1, dy1) < 0.01 or math.hypot(dx2, dy2) < 0.01:
            continue

        angle1 = math.atan2(dy1, dx1)
        angle2 = math.atan2(dy2, dx2)
        change = abs((angle2 - angle1 + math.pi) % (2 * math.pi) - math.pi)

        if change > angle_thresh:
            # 避免相邻的转弯点太密集
            if not key_indices or i - max(key_indices) >= min_gap:
                key_indices.add(i)

    # 构建 waypoints: 转弯点 + 终点
    waypoints = []
    sorted_idx = sorted(key_indices)
    for idx in sorted_idx:
        wx, wy = world_pts[idx]
        waypoints.append(np.array([[wx], [wy], [0.0]]))

    # 确保终点在最后一个
    if not waypoints:
        # 没有转弯，直接用终点
        waypoints.append(np.array([[gx], [gy], [0.0]]))
    else:
        last = waypoints[-1]
        if abs(last[0, 0] - gx) > 0.1 or abs(last[1, 0] - gy) > 0.1:
            waypoints.append(np.array([[gx], [gy], [0.0]]))

    return waypoints


# ========== main ==========

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('scene', nargs='?', default='maze_obs')
    args = parser.parse_args()

    scene = args.scene
    env_path = os.path.join(DIR, 'envs', scene, 'env.yaml')
    cfg_path = os.path.join(DIR, 'envs', scene, 'planner.yaml')

    if not os.path.exists(env_path):
        print(f"{scene}: SKIP (no env)")
        exit(1)

    print(f"=== {scene}: A* 关键引导 + NeuPAN ===")

    # 读取配置
    astar_cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            planner_cfg = yaml.safe_load(f)
        astar_cfg = planner_cfg.get('astar', {})
    robot_radius = astar_cfg.get('robot_radius', 0.22)
    resolution = astar_cfg.get('resolution', 0.05)

    # 构建栅格
    grid, res, origin, bounds = build_grid_from_env(env_path, robot_radius, resolution)
    print(f"  栅格: {grid.shape[1]}x{grid.shape[0]}, 分辨率={res}m")
    obs_count = np.sum(grid)
    print(f"  障碍格: {obs_count}/{grid.size} ({100*obs_count/grid.size:.1f}%)")

    astar = AStar(grid, res, origin)

    # 读取起终点
    with open(env_path) as f:
        env_cfg = yaml.safe_load(f)
    robot_cfg = env_cfg['robot'][0]
    sx, sy = robot_cfg['state'][:2]
    gx, gy = robot_cfg['goal'][:2]
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            planner_cfg = yaml.safe_load(f)
        ipath_wp = planner_cfg.get('ipath', {}).get('waypoints', [])
        if ipath_wp:
            gx, gy = ipath_wp[-1][0], ipath_wp[-1][1]

    # A* 全局规划
    path = astar.plan(sx, sy, gx, gy)
    if path is None:
        print(f"  ❌ A* 找不到路径!")
        exit(1)

    # 提取关键引导点（转弯处）
    waypoints = extract_key_waypoints(astar, path, gx, gy)
    print(f"  ✅ A* 路径: {len(path)}格 → {len(waypoints)}个关键引导点")
    for idx, wp in enumerate(waypoints):
        print(f"    [{idx}]: ({wp[0,0]:.2f}, {wp[1,0]:.2f})")

    # === 运行 NeuPAN ===
    env = irsim.make(env_path, display=True)
    planner = neupan.init_from_yaml(cfg_path)
    planner.ipath.waypoints = waypoints
    planner.ipath.initial_path = None
    planner.reset()

    # 显示关键引导点（拐点标记）
    key_pts = np.array([[wp[0, 0] for wp in waypoints], [wp[1, 0] for wp in waypoints]])
    env.draw_points(key_pts, s=40, c="cyan", marker="x", refresh=True)
    env.render()

    goal_pos = np.array(waypoints[-1][:2]).flatten()
    max_steps = 1500
    first_ref_traj = None  # 保存初始参考线（只画不更新）

    for i in range(max_steps):
        state = env.get_robot_state()
        scan = env.get_lidar_scan()
        pts = planner.scan_to_point(state, scan)
        action, info = planner(state, pts, None)
        goal_dist = np.linalg.norm(state[:2].flatten() - goal_pos)

        # 保存第一次生成的参考线
        if first_ref_traj is None and planner.ref_trajectory is not None:
            first_ref_traj = planner.ref_trajectory.copy()

        if info.get('stop'):
            print(f"step {i:3d}: pos=({state[0,0]:.2f},{state[1,0]:.2f}) goal_dist={goal_dist:.2f} stop=True min_dist={planner.min_distance:.3f}")
            env.end(3)
            print(f"{scene}: FAIL (stop)")
            exit(1)
        if info.get('arrive'):
            print(f"step {i:3d}: pos=({state[0,0]:.2f},{state[1,0]:.2f}) goal_dist={goal_dist:.2f} arrive=True min_dist={planner.min_distance:.3f}")
            env.end(3)
            print(f"{scene}: ✅ OK")
            exit(0)

        env.draw_points(planner.dune_points, s=25, c="g", refresh=True)
        env.draw_points(planner.nrmp_points, s=13, c="r", refresh=True)
        env.draw_trajectory(planner.opt_trajectory, "r", refresh=True)
        if first_ref_traj is not None:
            env.draw_trajectory(first_ref_traj, "b")  # 初始蓝线，不刷新
        env.draw_points(key_pts, s=40, c="cyan", marker="x")  # 拐点标记，不刷新
        env.step(action)
        env.render()

        if env.done():
            state2 = env.get_robot_state()
            pts2 = planner.scan_to_point(state2, scan)
            _, info2 = planner(state2, pts2, None)
            gd2 = np.linalg.norm(state2[:2].flatten() - goal_pos)
            if info2.get('arrive') or gd2 < 0.3:
                env.end(3)
                print(f"{scene}: ✅ OK (env done, near goal)")
                exit(0)
            break

    print(f"{scene}: FAIL (timeout or stuck)")
    env.end(3)
    exit(1)
