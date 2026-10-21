"""
eval/lidar3d_test.py — 3D 疑似 LiDAR の単体テスト(T12)。既知配置:
  正面 1.3 m に低い箱(高さ 0.15)、右 1.5 m にテーブル(天板 0.316〜0.356 m、脚 4 本)、左 1.5 m に従来の高い箱(0.6 m)
立位 100 ステップで 2D スキャンと 3D 投影スキャンを極座標で並べ、点群の高さ分類の 3D 散布図を描く。
2D では低い箱と天板が見えず脚だけ見える、3D では 3 つとも見える、を数値で示す。per-step コストも 2D / 3D で計測。

使い方: python eval/lidar3d_test.py --backend cpu --out results/t12_lidar3d_test.png
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
from eval.scenes import spec_to_morphs, TABLE_TOP_BOTTOM, TABLE_THICKNESS, TABLE_LEG_R, TABLE_LEG_INSET, LOWBOX_H  # noqa: E402
from nav.lidar import (ANGLES_DEG, IDX_FRONT, IDX_LEFT, IDX_RIGHT, make_lidar_cfg, read_scan, read_scan_3d,  # noqa: E402
                       CLS_GROUND, CLS_BODY, CLS_OVERHEAD, CLS_SELF)

SPEC = [dict(type="lowbox", pos=[1.5, 0.0], size=[0.4, 0.4, LOWBOX_H]),                       # 正面、面は x = 1.3
        dict(type="table", pos=[0.0, -1.9], top_size=0.8, top_z_bottom=TABLE_TOP_BOTTOM, thickness=TABLE_THICKNESS,
             leg_radius=TABLE_LEG_R, leg_inset=TABLE_LEG_INSET),                                # 右、天板の縁は y = −1.5
        dict(type="box", pos=[0.0, 1.7], size=[0.4, 0.4, 0.6])]                                 # 左、面は y = 1.5


def build(mode, env_cfgs):
    env_cfg, obs_cfg, reward_cfg, command_cfg = env_cfgs
    return Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg, command_cfg=command_cfg,
                  show_viewer=False, lidar_cfg=make_lidar_cfg(mode=mode), obstacles=spec_to_morphs(SPEC))


def run(env, mode, steps):
    env.reset()
    a = torch.zeros((1, 12), dtype=gs.tc_float, device=gs.device)
    for _ in range(5):
        env.step(a)
    t_step = t_read = 0.0
    for _ in range(steps):
        t0 = time.perf_counter()
        env.step(a)
        t1 = time.perf_counter()
        out = read_scan_3d(env) if mode == "3d" else read_scan(env, return_raw=True)
        t_read += time.perf_counter() - t1
        t_step += t1 - t0
    return out, 1e3 * t_step / steps, 1e3 * t_read / steps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="cpu")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--out", default="results/t12_lidar3d_test.png")
    parser.add_argument("--mode", choices=["3d", "3d-dense", "3d-dense-only"], default="3d",
                        help="3d = 16 層 ±30°(既定)、3d-dense = 30 層(T13 試作)、3d-dense-only = 25 層 ±12°")
    args = parser.parse_args()
    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, precision="32", logging_level="warning")
    cfgs = list(get_cfgs())
    cfgs[2]["reward_scales"] = {}

    env2 = build("2d", cfgs)
    (scan2, raw2), ms_step2, ms_read2 = run(env2, "2d", args.steps)
    base = env2.robot.get_pos()[0].cpu().numpy()
    env3 = build(args.mode, cfgs)
    pat = env3.lidar_cfg["pattern"]
    el = np.rad2deg(torch.as_tensor(pat.angles[1]).cpu().numpy())
    (scan3, pts2d, raw3, pts_all, cls_all, d_all, fs3), ms_step3, ms_read3 = run(env3, "3d", args.steps)
    N_LAYERS = len(el)
    base3 = env3.robot.get_pos()[0].cpu().numpy()
    print(f"[lidar3d] mode={args.mode} vertical angles ({len(el)}): {np.round(el, 1).tolist()}  (center {el.mean():+.1f} deg, horizontal ray: "
          f"{'yes' if np.any(np.abs(el) < 1e-6) else 'no (symmetric about 0)'})")
    # 立位でレイの z 分布: 仰角 0 近傍の層のヒット点 z
    hit = d_all < env3.lidar_cfg["max_range"]
    z = pts_all[:, 2]
    print(f"[lidar3d] base z={base3[2]:.3f}, sensor z≈{base3[2] + 0.15:.3f}; hit points: {hit.sum()}/{len(hit)}; "
          f"class counts ground={int((cls_all == CLS_GROUND).sum())} body={int((cls_all == CLS_BODY).sum())} "
          f"overhead={int((cls_all == CLS_OVERHEAD).sum())} self={int((cls_all == CLS_SELF).sum())}")
    mr = env3.lidar_cfg["max_range"]
    rows = [("正面(低い箱、面 x=1.3)", IDX_FRONT, 1.3 - base[0]), ("右(テーブル天板の縁 y=−1.5、脚 y=−2.0±0.1)", IDX_RIGHT, 1.5 + base[1]),
            ("左(高い箱、面 y=1.5)", IDX_LEFT, 1.5 - base[1])]
    print("| 方向 | 幾何期待 [m] | 2D スキャン [m] | 3D 投影 [m] |\n|---|---|---|---|")
    for name, idx, exp in rows:
        w = 2
        s2 = scan2[idx - w:idx + w + 1].min()
        s3 = scan3[idx - w:idx + w + 1].min()
        print(f"| {name} | {exp:.2f} | {s2 if s2 < mr else mr:.2f} | {s3 if s3 < mr else mr:.2f} |")
    print(f"[lidar3d] cost 2D: step {ms_step2:.2f} + read {ms_read2:.2f} = {ms_step2 + ms_read2:.2f} ms/step; "
          f"3D: step {ms_step3:.2f} + read {ms_read3:.2f} = {ms_step3 + ms_read3:.2f} ms/step (delta {ms_step3 + ms_read3 - ms_step2 - ms_read2:+.2f})")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    th = np.deg2rad(ANGLES_DEG)
    fig = plt.figure(figsize=(15, 5))
    for i, (sc, title) in enumerate([(scan2, "2D scan (horizontal, z = sensor)"), (scan3, "3D -> body-band projection (72 az)")]):
        ax = fig.add_subplot(1, 3, i + 1, projection="polar")
        title = title.replace("72 az", f"{len(el)} layers")
        ax.set_theta_zero_location("N")
        ax.plot(th, np.minimum(sc, mr), "o", ms=3, color="tab:blue" if i == 0 else "tab:orange")
        ax.set_rmax(3.0)
        ax.set_title(title, fontsize=10)
    ax = fig.add_subplot(1, 3, 3, projection="3d")
    m = hit & (np.hypot(pts_all[:, 0] - base3[0], pts_all[:, 1] - base3[1]) < 3.0)
    colors = {CLS_GROUND: ("#bbbbbb", "ground z<0.05"), CLS_BODY: ("#eb6834", "body band 0.05..0.49"), CLS_OVERHEAD: ("#2a78d6", "overhead >0.49"), CLS_SELF: ("#1baf7a", "self (footprint)")}
    for c, (col, lab) in colors.items():
        mm = m & (cls_all == c)
        ax.scatter(pts_all[mm, 0], pts_all[mm, 1], pts_all[mm, 2], s=3, c=col, label=f"{lab} ({mm.sum()})")
    ax.set_xlim(-3, 3)
    ax.set_ylim(-3, 3)
    ax.set_zlim(0, 1.0)
    ax.view_init(elev=35, azim=-60)
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title("3D points by height class", fontsize=10)
    fig.suptitle(f"{args.mode} ({len(el)} layers): low box front (1.3 m, h 0.15), table right (edge 1.5 m, top 0.32-0.36 m), tall box left (1.5 m)", fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=130)
    print("[lidar3d] wrote", args.out)


if __name__ == "__main__":
    main()
