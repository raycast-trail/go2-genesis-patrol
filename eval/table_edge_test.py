"""
eval/table_edge_test.py — T13: テーブルへ接近するときの「投影距離」と「真の縁までの距離」の時系列(seed 101、v3)。
3d(25 層)と 3d-coarse(16 層)で run_patrol を on_step フックつきで実行し、テーブル中心の方位の投影距離と、
base から天板の矩形までの真の距離を毎ステップ記録して描く。

使い方: python eval/table_edge_test.py --seed 101 --out results/t13_table_edge_seed101.png
"""

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import genesis as gs  # noqa: E402

from go2_patrol import run_patrol  # noqa: E402
from nav.lidar import ANGLES_DEG  # noqa: E402


def rect_dist(px, py, cx, cy, half):
    dx = max(abs(px - cx) - half, 0.0)
    dy = max(abs(py - cy) - half, 0.0)
    return math.hypot(dx, dy)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--modes", nargs="+", default=["3d", "3d-dense"])
    parser.add_argument("--out", default="results/t13_table_edge_seed101.png")
    args = parser.parse_args()
    gs.init(backend=gs.cpu, logging_level="warning")
    meta = json.load(open(f"results/scenes/seed_{args.seed}.json"))
    table = [o for o in meta["obstacles"] if o["type"] == "table"][0]
    cx, cy, half = table["pos"][0], table["pos"][1], table["top_size"] / 2
    series = {}
    for mode in args.modes:
        rec = []

        def on_step(n, pos, yaw, scan, rec=rec):
            bearing = math.degrees(math.atan2(cy - pos[1], cx - pos[0]) - yaw)
            bearing = (bearing + 180) % 360 - 180
            k = int(np.argmin(np.abs(ANGLES_DEG - bearing)))
            kk = [(k + j) % 72 for j in (-1, 0, 1)]
            rec.append((n * 0.02, float(min(scan[kk])), rect_dist(pos[0], pos[1], cx, cy, half), abs(bearing)))
        r = run_patrol("go2-patrol", 299, seed=args.seed, avoid=True, out=None, verbose=False, avoid_version="v3", lidar=mode,
                       on_step=on_step)
        series[mode] = (np.array(rec), r)
        print(f"[table_edge] {mode}: reached {r['reached']}/4 {r['end_reason']} {r['sim_s']:.1f}s contact={r['n_contact']}")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(series), 1, figsize=(9, 3.2 * len(series)), sharex=False)
    axes = np.atleast_1d(axes)
    stats = {}
    for ax, (mode, (a, r)) in zip(axes, series.items()):
        t, proj, true, bear = a.T
        facing = (bear < 45) & (true < 2.5)             # テーブルが前方 ±45° かつ 2.5 m 以内のステップだけ
        err = proj[facing] - true[facing]
        seen = proj[facing] < 4.9
        stats[mode] = dict(n=int(facing.sum()), median_err=float(np.median(err[seen])) if seen.any() else float("nan"),
                           p90_err=float(np.percentile(err[seen], 90)) if seen.any() else float("nan"), seen_frac=float(seen.mean()))
        ax.plot(t, np.minimum(proj, 5.0), color="tab:orange", lw=1.2, label="projected distance toward table (min of 3 azimuths)")
        ax.plot(t, true, color="k", lw=1.2, ls="--", label="true distance to table-top edge")
        ax.fill_between(t, 0, 5, where=facing, color="tab:green", alpha=0.08, label="facing table (<45°, <2.5 m)")
        ax.set_ylim(0, 5.2)
        ax.set_ylabel("distance [m]")
        ax.set_title(f"{mode}: reached {r['reached']}/4, {r['sim_s']:.1f} s; median error {stats[mode]['median_err']:+.2f} m, "
                     f"90th pct {stats[mode]['p90_err']:+.2f} m (facing steps n={stats[mode]['n']})", fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="upper right")
    axes[-1].set_xlabel("time [s]")
    fig.suptitle(f"seed {args.seed}: table-edge detection error (projected − true)", fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=140)
    print("[table_edge] wrote", args.out, stats)


if __name__ == "__main__":
    main()
