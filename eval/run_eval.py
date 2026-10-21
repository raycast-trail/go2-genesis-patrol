"""
eval/run_eval.py — 定量評価(T04): 20 配置 × (方策 2 種 × 回避あり/なし) = 80 エピソードを録画なしで回す。

  * seed 0〜4 は障害物なし(scene_seed = −1)、5〜19 は障害物あり(scene_seed = seed)
  * 成功 = 4/4 到達 かつ 転倒なし かつ 物理接触なし(60 s 以内)
  * 衝突 = 物理接触(robot と障害物の contact が 1 ステップでもある)。LiDAR 最小距離 < 0.25 m は「ニアミス」(副指標)
  * 1 エピソードごとに results/eval/episodes.csv に追記。済みの (policy, avoid, seed) はスキップ(再開可能)

使い方(リポジトリ直下で):
  python eval/run_eval.py --policies go2-walking:100,go2-patrol:299 --avoid both --seeds 0-19 --backend cpu
"""

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import genesis as gs  # noqa: E402

from go2_patrol import WAYPOINT_SETS, run_patrol  # noqa: E402

N_OBSTACLE_FREE_SEEDS = 5          # seed 0〜4 は障害物なし
STRAIGHT_LENGTH = {"square": 8.0}  # ウェイポイント間直線距離の合計 [m]

FIELDS = ["policy", "ckpt", "backend", "waypoints", "seed", "scene_seed", "n_placed", "avoid", "reached", "n_waypoints",
          "success", "fell", "end_reason", "contact", "contact_steps", "first_contact_s", "near_miss", "near_miss_steps",
          "first_near_miss_s", "min_lidar_m", "time_to_complete", "sim_s", "path_length_m", "path_efficiency",
          "wall_s", "raw_hit_steps", "raw_hits", "hits_after", "avoid_version", "lidar", "first_contact_type", "contact_types"]


def parse_seeds(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def load_done(path):
    """済みの (policy, avoid, seed, avoid_version) の集合。回避なしは avoid_version を '' として扱う"""
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {(r["policy"], int(r["avoid"]), int(r["seed"]), r.get("avoid_version", "") if int(r["avoid"]) else "",
                 r.get("lidar", "2d") or "2d")
                for r in csv.DictReader(f)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policies", type=str, default="go2-walking:100,go2-patrol:299", help="exp:ckpt をカンマ区切り")
    parser.add_argument("--avoid", choices=["both", "on", "off"], default="both")
    parser.add_argument("--seeds", type=str, default="0-19")
    parser.add_argument("--max-time", type=float, default=60.0)
    parser.add_argument("--no-video", action="store_true", default=True, help="録画しない(既定)")
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="cpu")
    parser.add_argument("--waypoints", choices=list(WAYPOINT_SETS), default="square")
    parser.add_argument("--out", type=str, default="results/eval/episodes.csv")
    parser.add_argument("--avoid-version", choices=["v1", "v2", "v3"], default="v2", help="回避則(nav/avoid.py)。T04 は v1、v3 = 地図 + A*(T09)")
    parser.add_argument("--t-commit", type=float, default=2.0)
    parser.add_argument("--t-clear", type=float, default=1.0)
    parser.add_argument("--camera-only", action="store_true", help="カメラを作るが録画しない(T07 の再現性対策)")
    parser.add_argument("--lidar", choices=["2d", "3d", "3d-dense", "3d-dense-only"], default="2d",
                        help="3d = 16 層 ±30°(既定の 3D)、3d-dense = 30 層(T13 試作)、3d-dense-only = 25 層 ±12°。高さ帯投影の 3D LiDAR")
    args = parser.parse_args()

    policies = [(p.split(":")[0], int(p.split(":")[1])) for p in args.policies.split(",")]
    avoids = {"both": [0, 1], "on": [1], "off": [0]}[args.avoid]
    seeds = parse_seeds(args.seeds)
    done = load_done(args.out)
    todo = [(seed, pol, ck, av) for seed in seeds for pol, ck in policies for av in avoids
            if (pol, av, seed, args.avoid_version if av else "", args.lidar) not in done]
    print(f"[run_eval] {len(todo)} episodes to run ({len(done)} already in {args.out}); avoid_version={args.avoid_version}")
    if not todo:
        return

    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, logging_level="warning")
    print(f"[run_eval] gs.backend={gs.backend} gs.device={gs.device}")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    straight = STRAIGHT_LENGTH[args.waypoints]
    t_start = time.time()
    for k, (seed, pol, ck, av) in enumerate(todo):
        scene_seed = -1 if seed < N_OBSTACLE_FREE_SEEDS else seed
        t0 = time.time()
        r = run_patrol(pol, ck, seed=scene_seed, avoid=bool(av), waypoints=args.waypoints, max_time=args.max_time,
                       out=None, verbose=False, avoid_version=args.avoid_version,
                       avoid_kwargs=dict(T_commit=args.t_commit, T_clear=args.t_clear), camera_only=args.camera_only,
                       lidar=args.lidar)
        wall = time.time() - t0
        fell = int(r["end_reason"] == "fell")
        contact = int(r["n_contact"] > 0)
        success = int(r["reached"] >= r["max_laps_idx"] and not fell and not contact and r["end_reason"] == "completed")
        row = dict(policy=pol, ckpt=ck, backend=f"{gs.backend}", waypoints=args.waypoints, seed=seed, scene_seed=scene_seed,
                   n_placed=r["n_placed"], avoid=av, reached=r["reached"], n_waypoints=r["max_laps_idx"],
                   success=success, fell=fell, end_reason=r["end_reason"], contact=contact, contact_steps=r["n_contact"],
                   first_contact_s="" if r["first_contact_t"] is None else f"{r['first_contact_t']:.2f}",
                   near_miss=int(r["n_collision"] > 0), near_miss_steps=r["n_collision"],
                   first_near_miss_s="" if r["first_collision_t"] is None else f"{r['first_collision_t']:.2f}",
                   min_lidar_m=f"{r['min_lidar']:.3f}", time_to_complete=f"{r['sim_s']:.2f}" if success else "",
                   sim_s=f"{r['sim_s']:.2f}", path_length_m=f"{r['path_length']:.3f}",
                   path_efficiency=f"{straight / r['path_length']:.3f}" if r["path_length"] > 0 else "",
                   wall_s=f"{wall:.1f}", raw_hit_steps=r["n_raw_hit_steps"], raw_hits=r["n_raw_hits"],
                   hits_after=r["n_hits_after"], avoid_version=args.avoid_version if av else "", lidar=args.lidar,
                   first_contact_type=r["first_contact_type"] or "", contact_types="+".join(r["contact_types"]))
        new = not os.path.exists(args.out)
        with open(args.out, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
        print(f"[run_eval] {k + 1}/{len(todo)} seed={seed:3d} scene={scene_seed:3d} n_obs={r['n_placed']} {pol:11s} "
              f"avoid={av} {args.avoid_version if av else '':2s} {args.lidar} -> reached {r['reached']}/{r['max_laps_idx']} "
              f"{r['end_reason']:9s} success={success} contact={contact}({r['n_contact']},{r['first_contact_type']}) "
              f"near_miss={int(r['n_collision'] > 0)} sim={r['sim_s']:.1f}s "
              f"wall={wall:.1f}s (total {time.time() - t_start:.0f}s)", flush=True)
    print(f"[run_eval] done: {len(todo)} episodes in {time.time() - t_start:.0f}s -> {args.out}")


if __name__ == "__main__":
    main()
