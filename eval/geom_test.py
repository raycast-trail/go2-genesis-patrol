"""
eval/geom_test.py — T12 手順 1: Go2 の幾何の実測(立位と台本歩行)。

  * 立位 100 ステップ後: base 原点 z、センサ z(base z + pos_offset z)、胴体の最高点 z(robot.get_AABB)、各リンクの AABB
  * 台本歩行(T01 の台本: 前進 → 左旋回 → 前進 → 右旋回 → 停止、14 s): 遊脚の最大高さ(calf リンクの AABB の最小 z = 足先の最大値)、
    歩行中の胴体最高点・base z の範囲
結果を results/t12_geometry.csv に書き、表を表示する。

使い方: python eval/geom_test.py --backend cpu
"""

import argparse
import csv
import os
import pickle
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import genesis as gs  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from go2_env import Go2Env  # noqa: E402
from go2_patrol import resolve_ckpt_dir  # noqa: E402

SCRIPT = [(3.0, 0.5, 0, 0), (3.0, 0.5, 0, 0.5), (3.0, 0.5, 0, 0), (3.0, 0.5, 0, -0.5), (2.0, 0.0, 0, 0)]
LIDAR_Z = 0.15


def aabb_np(x):
    return np.asarray(torch.as_tensor(x).detach().cpu().numpy(), dtype=np.float64)


def robot_aabb(env):
    a = aabb_np(env.robot.get_AABB()).reshape(-1, 2, 3)[0]     # (2, 3): min, max
    return a


def link_aabbs(env):
    out = {}
    for l in env.robot.links:
        a = aabb_np(l.get_AABB()).reshape(-1, 2, 3)[0]
        out[l.name] = a
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="cpu")
    parser.add_argument("-e", "--exp-name", default="go2-patrol")
    parser.add_argument("--ckpt", type=int, default=299)
    parser.add_argument("--out", default="results/t12_geometry.csv")
    args = parser.parse_args()
    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, precision="32", logging_level="warning")
    log_dir = resolve_ckpt_dir(args.exp_name)
    with open(f"{log_dir}/cfgs.pkl", "rb") as f:
        env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(f)
    reward_cfg["reward_scales"] = {}
    env_cfg["episode_length_s"] = 60.0
    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg, command_cfg=command_cfg, show_viewer=False)
    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    runner.load(os.path.join(log_dir, f"model_{args.ckpt}.pt"))
    policy = runner.get_inference_policy(device=gs.device)
    env._resample_commands = lambda envs_idx: None

    rows = []
    # --- 立位 ---
    obs = env.reset()
    zero = torch.zeros((1, 12), dtype=gs.tc_float, device=gs.device)
    for _ in range(100):
        env.step(zero)
    base = env.robot.get_pos()[0].cpu().numpy()
    rb = robot_aabb(env)
    la = link_aabbs(env)
    calves = [n for n in la if n.endswith("calf")]
    foot_z = min(la[n][0, 2] for n in calves)
    rows += [("standing", "base_z", base[2]), ("standing", "sensor_z (base z + %.2f)" % LIDAR_Z, base[2] + LIDAR_Z),
             ("standing", "robot_aabb_max_z", rb[1, 2]), ("standing", "robot_aabb_min_z", rb[0, 2]),
             ("standing", "base_link_aabb_max_z", la["base"][1, 2]), ("standing", "foot_bottom_z (min calf aabb z)", foot_z)]
    highest = max(la.items(), key=lambda kv: kv[1][1, 2])
    rows.append(("standing", f"highest_link ({highest[0]})", highest[1][1, 2]))
    print("[geom] standing: base z=%.3f sensor z=%.3f robot max z=%.3f (%s) foot bottom z=%.3f" %
          (base[2], base[2] + LIDAR_Z, rb[1, 2], highest[0], foot_z))
    for n, a in la.items():
        print(f"    {n:9s} z {a[0, 2]:.3f}..{a[1, 2]:.3f}  x {a[0, 0]:.2f}..{a[1, 0]:.2f}  y {a[0, 1]:.2f}..{a[1, 1]:.2f}")

    # --- 台本歩行 ---
    obs = env.reset()
    max_foot, max_top, base_zs, pitch = 0.0, 0.0, [], []
    n = 0
    with torch.no_grad():
        for dur, vx, vy, wz in SCRIPT:
            env.commands[:] = torch.tensor([vx, vy, wz], dtype=gs.tc_float, device=gs.device)
            for _ in range(int(dur / env.dt)):
                actions = policy(obs)
                obs, _, dones, _ = env.step(actions)
                n += 1
                if n < 10:
                    continue
                la = link_aabbs(env)
                max_foot = max(max_foot, max(la[c][0, 2] for c in calves))
                max_top = max(max_top, robot_aabb(env)[1, 2])
                base_zs.append(env.robot.get_pos()[0, 2].item())
                pitch.append(abs(env.base_euler[0, 1].item()))
                if bool(dones[0]):
                    print("[geom] fell during script at step", n)
    rows += [("walking", "swing_foot_max_z (max over time of calf aabb min z)", max_foot),
             ("walking", "robot_aabb_max_z_max", max_top), ("walking", "base_z_min", min(base_zs)), ("walking", "base_z_max", max(base_zs)),
             ("walking", "abs_pitch_max_deg", max(pitch)), ("walking", "steps", n)]
    print("[geom] walking (%d steps): swing foot max z=%.3f, robot max z=%.3f, base z %.3f..%.3f, |pitch| max %.1f deg" %
          (n, max_foot, max_top, min(base_zs), max(base_zs), max(pitch)))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["phase", "quantity", "value"])
        for r in rows:
            w.writerow([r[0], r[1], f"{r[2]:.4f}" if isinstance(r[2], float) else r[2]])
    print("[geom] wrote", args.out)


if __name__ == "__main__":
    main()
