"""
eval/summarize.py — results/eval/episodes.csv を条件ごとに集計し、summary.csv / summary.md / summary.png を出力する。

条件 = 方策(go2-walking / go2-patrol)× 回避(なし / あり)× 障害物(なし: scene_seed < 0 / あり)
指標 = 成功率、接触率(物理接触)、ニアミス率(LiDAR < 0.25 m)、転倒率、平均到達数、
       平均所要時間(成功分)、平均経路効率(成功分、= 8.0 m / 走行距離)

使い方: python eval/summarize.py --episodes results/eval/episodes.csv --out-dir results/eval
"""

import argparse
import os

import numpy as np
import pandas as pd

POLICY_ORDER = ["go2-walking", "go2-patrol"]
POLICY_LABEL = {"go2-walking": "baseline policy (forward only)", "go2-patrol": "patrol policy (extended commands)"}
# dataviz 既定パレット(固定順): series-1 blue, series-2 orange
POLICY_COLOR = {"go2-walking": "#2a78d6", "go2-patrol": "#eb6834"}


def summarize(df):
    df = df.copy()
    df["obstacles"] = np.where(df["scene_seed"] >= 0, "with", "without")
    rows = []
    for obs in ["without", "with"]:
        for pol in POLICY_ORDER:
            for av in [0, 1]:
                g = df[(df.obstacles == obs) & (df.policy == pol) & (df.avoid == av)]
                if len(g) == 0:
                    continue
                succ = g[g.success == 1]
                rows.append(dict(
                    obstacles=obs, policy=pol, avoid=av, n=len(g),
                    success_rate=g.success.mean(), contact_rate=g.contact.mean(), near_miss_rate=g.near_miss.mean(),
                    fell_rate=g.fell.mean(), mean_reached=g.reached.mean(),
                    mean_time_success=succ.time_to_complete.astype(float).mean() if len(succ) else np.nan,
                    mean_efficiency_success=succ.path_efficiency.astype(float).mean() if len(succ) else np.nan,
                    mean_min_lidar=g.min_lidar_m.astype(float).mean(),
                ))
    return pd.DataFrame(rows)


def to_markdown(s):
    lines = ["| 障害物 | 方策 | 回避 | n | 成功率 | 接触率 | ニアミス率 | 転倒率 | 平均到達 | 所要 [s](成功分) | 経路効率(成功分) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in s.iterrows():
        t = "—" if np.isnan(r.mean_time_success) else f"{r.mean_time_success:.1f}"
        e = "—" if np.isnan(r.mean_efficiency_success) else f"{r.mean_efficiency_success:.2f}"
        lines.append(f"| {'あり' if r.obstacles == 'with' else 'なし'} | {r.policy} | {'あり' if r.avoid else 'なし'} | {r.n} | "
                     f"{r.success_rate:.0%} | {r.contact_rate:.0%} | {r.near_miss_rate:.0%} | {r.fell_rate:.0%} | "
                     f"{r.mean_reached:.2f} | {t} | {e} |")
    return "\n".join(lines)


def plot(s, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = [("success_rate", "Success rate (4/4, no fall, no contact)"), ("contact_rate", "Contact rate (physical)")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    groups = ["without", "with"]
    conds = [(pol, av) for pol in POLICY_ORDER for av in [0, 1]]
    width = 0.19
    for ax, (m, title) in zip(axes, metrics):
        for j, (pol, av) in enumerate(conds):
            vals, ns = [], []
            for obs in groups:
                r = s[(s.obstacles == obs) & (s.policy == pol) & (s.avoid == av)]
                vals.append(float(r[m].iloc[0]) if len(r) else np.nan)
                ns.append(int(r.n.iloc[0]) if len(r) else 0)
            x = np.arange(len(groups)) + (j - 1.5) * (width + 0.02)
            bars = ax.bar(x, vals, width, color=POLICY_COLOR[pol], alpha=1.0 if av else 0.45,
                          hatch="" if av else "///", edgecolor="white", linewidth=1.0,
                          label=f"{POLICY_LABEL[pol]}, avoid {'on' if av else 'off'}")
            for b, v in zip(bars, vals):
                if not np.isnan(v):
                    ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}", ha="center", va="bottom", fontsize=8,
                            color="#333333")
        ax.set_xticks(np.arange(len(groups)))
        ax.set_xticklabels(["no obstacles\n(seeds 0-4, n=5 each)", "with obstacles\n(seeds 5-19, n=15 each)"])
        ax.set_ylim(0, 1.12)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.set_title(title, fontsize=11)
        ax.grid(axis="y", alpha=0.25)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    axes[0].legend(loc="upper center", bbox_to_anchor=(1.05, -0.12), ncol=2, fontsize=8, frameon=False)
    fig.suptitle("Go2 square patrol: policy x avoidance (20 scenes, 60 s limit)", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[summarize] wrote {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=str, default="results/eval/episodes.csv")
    parser.add_argument("--out-dir", type=str, default="results/eval")
    args = parser.parse_args()
    df = pd.read_csv(args.episodes)
    print(f"[summarize] {len(df)} episodes, {df.groupby(['policy', 'avoid']).size().to_dict()}")
    s = summarize(df)
    os.makedirs(args.out_dir, exist_ok=True)
    s.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False, float_format="%.4f")
    md = to_markdown(s)
    with open(os.path.join(args.out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(md)
    plot(s, os.path.join(args.out_dir, "summary.png"))


if __name__ == "__main__":
    main()
