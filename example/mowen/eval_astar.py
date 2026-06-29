"""mowen 仿真测试（集成 A* 全局规划）
用法: python eval_astar.py maze_obs
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
        self.grid = grid            # 2D numpy, 0=空闲 1=障碍
        self.res = resolution       # 米/格
        self.origin = origin        # (x_min, y_min) 世界坐标
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
    """判断点 (px,py) 是否在矩形障碍物内（含旋转）"""
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
    x_min, x_max = ox, ox + w_world
    y_min, y_max = oy, oy + h_world

    gw = int(w_world / resolution) + 2   # +2 避免边界越界
    gh = int(h_world / resolution) + 2
    grid = np.zeros((gh, gw), dtype=np.uint8)
    inflate = int(robot_radius / resolution) + 1

    # 收集所有障碍物
    all_obs = []
    for obs_group in env_cfg.get('obstacle', []):
        shapes = obs_group['shape']
        states = obs_group['state']
        for shape, state in zip(shapes, states):
            all_obs.append((shape, state))

    # 遍历所有栅格，检查是否在障碍物内
    for gy in range(gh):
        for gx in range(gw):
            wx = ox + gx * resolution
            wy = oy + gy * resolution
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
                    # 膨胀
                    for dy in range(-inflate, inflate+1):
                        for dx in range(-inflate, inflate+1):
                            ngx, ngy = gx+dx, gy+dy
                            if 0 <= ngx < gw and 0 <= ngy < gh:
                                grid[ngy, ngx] = 1
                    break

    return grid, resolution, (ox, oy), (x_min, x_max, y_min, y_max)


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

    print(f"=== {scene}: A* + NeuPAN ===")

    # 读取 A* 配置（从 planner.yaml）
    astar_cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            planner_cfg = yaml.safe_load(f)
        astar_cfg = planner_cfg.get('astar', {})
    robot_radius = astar_cfg.get('robot_radius', 0.22)
    resolution = astar_cfg.get('resolution', 0.05)

    # 构建 A* 栅格
    grid, res, origin, bounds = build_grid_from_env(env_path, robot_radius, resolution)
    print(f"  栅格: {grid.shape[1]}x{grid.shape[0]}, 分辨率={res}m")
    obs_count = np.sum(grid)
    print(f"  障碍格: {obs_count}/{grid.size} ({100*obs_count/grid.size:.1f}%)")

    astar = AStar(grid, res, origin)

    # 读取 env.yaml 获取起终点
    with open(env_path) as f:
        env_cfg = yaml.safe_load(f)
    robot_cfg = env_cfg['robot'][0]
    sx, sy = robot_cfg['state'][:2]
    gx, gy = robot_cfg['goal'][:2]

    # A* 规划
    path = astar.plan(sx, sy, gx, gy)
    if path is None:
        print(f"  ❌ A* 找不到路径!")
        exit(1)

    # 路径抽稀（每 N 个点取一个，减少 waypoint 数量）
    step = max(1, len(path) // 30)
    waypoints = []
    for i in range(0, len(path), step):
        wx, wy = astar.grid_to_world(*path[i])
        waypoints.append(np.array([[wx], [wy], [0.0]]))
    last = waypoints[-1]
    if abs(last[0,0]-gx) > 0.01 or abs(last[1,0]-gy) > 0.01:
        waypoints.append(np.array([[gx], [gy], [0.0]]))

    print(f"  ✅ A* 路径: {len(path)}格 → {len(waypoints)}个waypoints")

    # === 运行 NeuPAN 仿真 ===
    env = irsim.make(env_path, display=True)
    planner = neupan.init_from_yaml(cfg_path)

    # 用 A* 路径替换 waypoints
    planner.update_initial_path_from_waypoints(waypoints)
    planner.reset()

    goal_pos = np.array(waypoints[-1][:2]).flatten()
    max_steps = 1500

    for i in range(max_steps):
        state = env.get_robot_state()
        scan = env.get_lidar_scan()
        pts = planner.scan_to_point(state, scan)
        action, info = planner(state, pts, None)
        goal_dist = np.linalg.norm(state[:2].flatten() - goal_pos)

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
        env.draw_trajectory(planner.ref_trajectory, "b", refresh=True)
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
