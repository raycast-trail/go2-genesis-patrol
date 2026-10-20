"""
eval/plot_traj.py — go2_patrol.py が出力する *_log.csv(t,x,y,yaw_deg,cmd_vx,cmd_yaw)から xy 軌跡を描く。
ウェイポイント列(go2_patrol.WAYPOINT_SETS)を破線で重ね、到達判定円(reach_dist)も描く。

使い方(リポジトリ直下で):
  python eval/plot_traj.py --log videos/t01_square_log.csv --out results/t01_square_traj.png --waypoints square
  python eval/plot_traj.py --log videos/t01_square_log.csv videos/t01_square_baseline_log.csv \
      --label go2-patrol go2-walking --out results/t01_square_traj.png
"""

import argparse
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from go2_patrol import WAYPOINT_SETS  # noqa: E402

START = (0.0, 0.0)   # go2_env の base_init_pos(xy)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", nargs="+", required=True, help="go2_patrol.py の *_log.csv(複数可)")
    parser.add_argument("--label", nargs="*", default=None, help="凡例(--log と同数)")
    parser.add_argument("--waypoints", choices=list(WAYPOINT_SETS), default="square")
    parser.add_argument("--reach-dist", type=float, default=0.3)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--title", type=str, default=None)
    args = parser.parse_args()

    labels = args.label or [os.path.basename(p).replace("_log.csv", "") for p in args.log]
    assert len(labels) == len(args.log), "--label は --log と同数にする"

    wps = np.array([START] + WAYPOINT_SETS[args.waypoints], dtype=float)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(wps[:, 0], wps[:, 1], "k--", lw=1.2, label="target path")
    for i, (x, y) in enumerate(wps[1:]):
        ax.add_patch(plt.Circle((x, y), args.reach_dist, fill=False, ec="gray", ls=":", lw=0.8))
        ax.annotate(f"WP{i}", (x, y), textcoords="offset points", xytext=(6, 6), fontsize=9, color="gray")
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
    for k, (path, lab) in enumerate(zip(args.log, labels)):
        d = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
        t, x, y = d[:, 0], d[:, 1], d[:, 2]
        ax.plot(x, y, color=colors[k % len(colors)], lw=1.6, label=f"{lab} ({t[-1]:.1f}s)")
        ax.plot(x[0], y[0], "o", color=colors[k % len(colors)], ms=5)
        ax.plot(x[-1], y[-1], "x", color=colors[k % len(colors)], ms=8, mew=2)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(args.title or f"Go2 patrol trajectory ({args.waypoints})")
    lo, hi = wps.min() - 1.0, wps.max() + 1.0
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"[plot_traj] wrote {args.out}")


if __name__ == "__main__":
    main()
