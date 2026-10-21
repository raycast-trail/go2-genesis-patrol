"""
eval/map_test.py — 占有格子の単体テスト(T09)。T02 と同じ既知配置(正面 1.3 m に Box、右 1.85 m に Cylinder)で
立位のまま N ステップ LiDAR を回して地図を作り、PNG に出す。Box / Cylinder の位置に占有セルが出て、周囲が空きであることを確認する。

使い方: python eval/map_test.py --backend cpu --out results/t09_map_test.png
"""

import argparse
import math
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import genesis as gs  # noqa: E402
from genesis.utils.geom import quat_to_xyz  # noqa: E402

from go2_env import Go2Env  # noqa: E402
from go2_train import get_cfgs  # noqa: E402
from nav.grid_map import GridMap  # noqa: E402
from nav.lidar import make_lidar_cfg, read_scan_full  # noqa: E402
from nav.planner import Planner  # noqa: E402

BOX = dict(type="box", pos=[1.5, 0.0], size=[0.4, 0.4, 0.6])
CYL = dict(type="cylinder", pos=[0.0, -2.0], radius=0.15, height=0.7)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="cpu")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--out", type=str, default="results/t09_map_test.png")
    args = parser.parse_args()
    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, precision="32", logging_level="warning")
    env_cfg, obs_cfg, reward_cfg, command_cfg = get_cfgs()
    reward_cfg["reward_scales"] = {}
    obstacles = [gs.morphs.Box(pos=(1.5, 0.0, 0.3), size=(0.4, 0.4, 0.6), fixed=True),
                 gs.morphs.Cylinder(pos=(0.0, -2.0, 0.35), radius=0.15, height=0.7, fixed=True)]
    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg, command_cfg=command_cfg,
                 show_viewer=False, lidar_cfg=make_lidar_cfg(), obstacles=obstacles)
    env.reset()
    actions = torch.zeros((1, 12), dtype=gs.tc_float, device=gs.device)
    gmap = GridMap()
    import time
    t_upd = 0.0
    for k in range(args.steps):
        env.step(actions)
        if k < 5:
            continue
        scan, raw, pts = read_scan_full(env)
        pos = env.robot.get_pos()[0].cpu().numpy()
        yaw = float(quat_to_xyz(env.robot.get_quat(), rpy=True, degrees=False)[0, 2])
        t0 = time.perf_counter()
        gmap.update(pos[:2], yaw, scan, raw, pts)
        t_upd += time.perf_counter() - t0
    occ = gmap.occupied()
    ys, xs = np.nonzero(occ)
    cells = [gmap.to_world(ix, iy) for ix, iy in zip(xs, ys)]
    n_box = sum(1 for x, y in cells if 1.2 <= x <= 1.75 and -0.3 <= y <= 0.3)
    n_cyl = sum(1 for x, y in cells if -0.3 <= x <= 0.3 and -2.25 <= y <= -1.75)
    n_other = len(cells) - n_box - n_cyl
    free = (gmap.logodds < -0.5).sum()
    print(f"[map_test] occupied cells={len(cells)} (box region {n_box}, cylinder region {n_cyl}, elsewhere {n_other}); "
          f"free cells={free}; unknown={(np.abs(gmap.logodds) <= 0.5).sum()}; update {1e3 * t_upd / max(args.steps - 5, 1):.2f} ms/step")
    if n_box:
        bx = [x for x, y in cells if 1.2 <= x <= 1.75 and -0.3 <= y <= 0.3]
        print(f"[map_test] box occupied x range {min(bx):.2f}..{max(bx):.2f} (front face at 1.30 expected)")
    if n_cyl:
        cy = [y for x, y in cells if -0.3 <= x <= 0.3 and -2.25 <= y <= -1.75]
        print(f"[map_test] cylinder occupied y range {min(cy):.2f}..{max(cy):.2f} (near face at -1.85 expected)")
    # 計画の動作確認: (0,0) → (3, 0)(Box の向こう)
    t0 = time.perf_counter()
    planner = Planner(gmap)
    path = planner.plan(pos[:2], (3.0, 0.0))
    print(f"[map_test] A* (0,0)->(3,0): {'found, %d points, inflate %.2f' % (len(path), planner.last_inflate) if path else 'NOT found'} "
          f"in {1e3 * (time.perf_counter() - t0):.1f} ms; local goal {planner.local_goal(pos[:2])}")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    gmap.save_png(args.out, robot_xy=pos[:2], path_xy=path, obstacles=[BOX, CYL],
                  title=f"T09 map test: {args.steps} steps standing, A* to (3, 0)")
    print(f"[map_test] wrote {args.out}")


if __name__ == "__main__":
    main()
