"""
eval/lidar_test.py — 疑似 LiDAR(Raycaster)の単体テスト。学習・方策は不要。

既知配置の障害物(正面 1.3 m に面がくる Box、右 1.85 m に面がくる Cylinder)を置き、立位のまま N ステップ回して
  * 正面 / 右 / 左 / 後方の距離、max_range 未満のヒット一覧
  * 1 ステップ(env.step + read_scan)の平均時間 [ms]
  * 極座標プロット(results/t02_scan.png)に幾何計算した期待距離を重ねる
を出力する。Metal と CPU の両方で実行して一致を確認する(--backend)。

使い方(リポジトリ直下で):
  python eval/lidar_test.py --backend gpu --out results/t02_scan.png --csv results/t02_timing.csv
  python eval/lidar_test.py --backend cpu --out results/t02_scan_cpu.png --csv results/t02_timing.csv
"""

import argparse
import math
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import genesis as gs  # noqa: E402

from go2_env import Go2Env  # noqa: E402
from go2_train import get_cfgs  # noqa: E402
from nav.lidar import (ANGLES_DEG, IDX_BACK, IDX_FRONT, IDX_LEFT, IDX_RIGHT, make_lidar_cfg,  # noqa: E402
                       read_scan, sector_min)

# 既知配置(タスク T02 指定)
BOX = dict(pos=(1.5, 0.0, 0.25), size=(0.4, 0.4, 0.5))        # 正面: 面は x = 1.3
CYL = dict(pos=(0.0, -2.0, 0.3), radius=0.15, height=0.6)    # 右: 面は y = -1.85


def expected_scan(origin_xy, angles_deg, max_range):
    """センサ原点から各レイを飛ばしたときの Box / Cylinder までの幾何距離(2D)。"""
    ox, oy = origin_xy
    out = np.full(len(angles_deg), max_range)
    bx, by, _ = BOX["pos"]
    hx, hy = BOX["size"][0] / 2, BOX["size"][1] / 2
    cx, cy, _ = CYL["pos"]
    r = CYL["radius"]
    for i, a in enumerate(np.deg2rad(angles_deg)):
        dx, dy = math.cos(a), math.sin(a)
        best = max_range
        # AABB slab
        tmin, tmax = 0.0, max_range
        for o, d, lo, hi in ((ox, dx, bx - hx, bx + hx), (oy, dy, by - hy, by + hy)):
            if abs(d) < 1e-9:
                if o < lo or o > hi:
                    tmin, tmax = 1.0, 0.0
                    break
            else:
                t1, t2 = (lo - o) / d, (hi - o) / d
                tmin, tmax = max(tmin, min(t1, t2)), min(tmax, max(t1, t2))
        if tmin <= tmax and tmin > 0:
            best = min(best, tmin)
        # circle
        fx, fy = ox - cx, oy - cy
        b = 2 * (fx * dx + fy * dy)
        c = fx * fx + fy * fy - r * r
        disc = b * b - 4 * c
        if disc >= 0:
            t = (-b - math.sqrt(disc)) / 2
            if t > 0:
                best = min(best, t)
        out[i] = best
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--out", type=str, default="results/t02_scan.png")
    parser.add_argument("--csv", type=str, default="results/t02_timing.csv", help="計測行を追記する CSV")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-points", action="store_true", help="return_points=False で計測(地面除去なし)")
    parser.add_argument("--no-lidar", action="store_true", help="LiDAR なしで env.step() だけ計測(コストの切り分け用)")
    args = parser.parse_args()

    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, precision="32", logging_level="warning", seed=args.seed)
    print(f"[lidar_test] gs.backend={gs.backend} gs.device={gs.device}")

    env_cfg, obs_cfg, reward_cfg, command_cfg = get_cfgs()
    reward_cfg["reward_scales"] = {}
    lidar_cfg = make_lidar_cfg(return_points=not args.no_points)
    obstacles = [gs.morphs.Box(pos=BOX["pos"], size=BOX["size"], fixed=True),
                 gs.morphs.Cylinder(pos=CYL["pos"], radius=CYL["radius"], height=CYL["height"], fixed=True)]
    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg, command_cfg=command_cfg,
                 show_viewer=False, lidar_cfg=None if args.no_lidar else lidar_cfg, obstacles=obstacles)
    if args.no_lidar:
        env.reset()
        actions = torch.zeros((1, 12), dtype=gs.tc_float, device=gs.device)
        env.step(actions)
        t_step = []
        for _ in range(args.steps):
            t0 = time.perf_counter()
            env.step(actions)
            t_step.append(time.perf_counter() - t0)
        ms_step = 1e3 * np.mean(t_step)
        print(f"[lidar_test] timing (no lidar): step={ms_step:.2f} ms (mean of {args.steps} steps, {args.backend})")
        with open(args.csv, "a", encoding="utf-8") as f:
            f.write(f"{gs.backend},no_lidar,{args.steps},{ms_step:.3f},0.000,{ms_step:.3f},,,,,,,,{args.seed}\n")
        return
    max_range = lidar_cfg["max_range"]
    print(f"[lidar_test] n_rays={len(ANGLES_DEG)} angles[0]={ANGLES_DEG[0]} angles[36]={ANGLES_DEG[36]} "
          f"min_range={lidar_cfg['min_range']} max_range={max_range} pos_offset={lidar_cfg['pos_offset']}")

    env.reset()
    actions = torch.zeros((1, 12), dtype=gs.tc_float, device=gs.device)
    # ウォームアップ(JIT)
    env.step(actions)
    read_scan(env)

    t_step, t_read, scans = [], [], []
    for _ in range(args.steps):
        t0 = time.perf_counter()
        env.step(actions)
        t1 = time.perf_counter()
        scan = read_scan(env)
        t2 = time.perf_counter()
        t_step.append(t1 - t0)
        t_read.append(t2 - t1)
        scans.append(scan)
    scans = np.array(scans)
    scan = scans[-1]
    ms_step, ms_read = 1e3 * np.mean(t_step), 1e3 * np.mean(t_read)
    ms_total = ms_step + ms_read

    base = env.robot.get_pos()[0].cpu().numpy()
    origin = (base[0] + lidar_cfg["pos_offset"][0], base[1] + lidar_cfg["pos_offset"][1])
    exp = expected_scan(origin, ANGLES_DEG, max_range)
    raw = torch.as_tensor(env.lidar.read().distances).reshape(1, -1)[0].cpu().numpy()

    print(f"[lidar_test] base pos after {args.steps} steps: ({base[0]:.3f}, {base[1]:.3f}, {base[2]:.3f})")
    # 立ち上がり(初期高さから着地・整定)の間の変化を確認する
    print("[lidar_test] front distance per step (settling): " +
          ", ".join(f"s{i}={scans[i, IDX_FRONT]:.2f}" for i in [0, 1, 2, 3, 5, 10, 20, 50, args.steps - 1]))
    n_settled = int(np.sum(np.abs(scans[:, IDX_FRONT] - scan[IDX_FRONT]) < 0.02))
    print(f"[lidar_test] steps with front within 2 cm of final: {n_settled}/{args.steps}")
    print(f"[lidar_test] front(idx{IDX_FRONT})={scan[IDX_FRONT]:.3f}  right(idx{IDX_RIGHT})={scan[IDX_RIGHT]:.3f}  "
          f"left(idx{IDX_LEFT})={scan[IDX_LEFT]:.3f}  back(idx{IDX_BACK})={scan[IDX_BACK]:.3f}  (expected "
          f"front={exp[IDX_FRONT]:.3f} right={exp[IDX_RIGHT]:.3f})")
    hits = np.where(scan < max_range)[0]
    print(f"[lidar_test] hits (< max_range) after ground removal: {len(hits)} rays")
    for i in hits:
        print(f"    idx {i:2d}  angle {ANGLES_DEG[i]:7.1f} deg  d={scan[i]:.3f}  expected={exp[i]:.3f}  raw={raw[i]:.3f}")
    near = np.where(scan < 1.0)[0]
    print(f"[lidar_test] hits < 1.0 m: {[(int(i), round(float(scan[i]), 3)) for i in near]}")
    raw_hits = np.where(raw < max_range)[0]
    ground_removed = sorted(set(raw_hits) - set(hits))
    print(f"[lidar_test] raw hits={len(raw_hits)}, removed as ground/min_range={len(ground_removed)}: "
          f"{[int(i) for i in ground_removed]}")
    # 障害物以外のレイが max_range か(期待が max_range のレイは測定も max_range であるべき)
    non_obst = exp >= max_range
    n_spurious = int(np.sum(scan[non_obst] < max_range))
    print(f"[lidar_test] spurious hits on non-obstacle rays: {n_spurious}")
    err = np.abs(scan - exp)
    print(f"[lidar_test] |scan - expected|: max={err.max():.3f} mean={err.mean():.3f}; "
          f"scan std over {args.steps} steps (front)={scans[:, IDX_FRONT].std():.4f}")
    print(f"[lidar_test] sector_min(12) = {np.round(sector_min(scan), 2)}")
    print(f"[lidar_test] timing: step={ms_step:.2f} ms  read_scan={ms_read:.2f} ms  total={ms_total:.2f} ms  "
          f"(mean of {args.steps} steps, {args.backend})")

    # CSV(追記)
    os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
    new = not os.path.exists(args.csv)
    with open(args.csv, "a", encoding="utf-8") as f:
        if new:
            f.write("backend,return_points,steps,ms_step,ms_read_scan,ms_total,front_m,right_m,left_m,back_m,"
                    "n_hits,n_spurious,max_abs_err_m,seed\n")
        f.write(f"{gs.backend},{not args.no_points},{args.steps},{ms_step:.3f},{ms_read:.3f},{ms_total:.3f},"
                f"{scan[IDX_FRONT]:.3f},{scan[IDX_RIGHT]:.3f},{scan[IDX_LEFT]:.3f},{scan[IDX_BACK]:.3f},"
                f"{len(hits)},{n_spurious},{err.max():.3f},{args.seed}\n")
    np.savetxt(os.path.splitext(args.out)[0] + ".csv", np.c_[ANGLES_DEG, scan, exp, raw], delimiter=",",
               fmt="%.4f", header="angle_deg,scan_m,expected_m,raw_m", comments="")

    # 極座標プロット
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    th = np.deg2rad(ANGLES_DEG)
    fig = plt.figure(figsize=(6.5, 6.5))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N")      # 正面を上に
    ax.set_theta_direction(1)            # 反時計回り = 左が左側に来るよう、+90°(左)を左に
    ax.plot(np.r_[th, th[0]], np.r_[exp, exp[0]], "k--", lw=1.0, label="expected (geometry)")
    ax.plot(th, raw, ".", color="tab:gray", ms=4, alpha=0.6, label="raw distances")
    ax.plot(th, scan, "o", color="tab:blue", ms=4, label="scan (ground removed)")
    ax.set_rmax(max_range + 0.2)
    ax.set_rticks([1, 2, 3, 4, 5])
    ax.set_title(f"T02 pseudo-LiDAR scan ({gs.backend}, {args.steps} steps)\n"
                 f"front={scan[IDX_FRONT]:.2f} m, right={scan[IDX_RIGHT]:.2f} m, step+read={ms_total:.1f} ms", fontsize=10)
    ax.legend(loc="lower right", fontsize=8, bbox_to_anchor=(1.15, -0.1))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"[lidar_test] wrote {args.out}")


if __name__ == "__main__":
    main()
