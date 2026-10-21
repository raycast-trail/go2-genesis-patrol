"""
eval/summarize.py — results/eval/episodes.csv を条件ごとに集計し、summary.csv / summary.md / summary.png を出力する。

条件 = 方策(go2-walking / go2-patrol)× 回避(なし / あり)× 障害物(なし: scene_seed < 0 / あり)
指標 = 成功率、接触率(物理接触)、ニアミス率(LiDAR < 0.25 m)、転倒率、平均到達数、
       平均所要時間(成功分)、平均経路効率(成功分、= 8.0 m / 走行距離)

使い方: python eval/summarize.py --episodes results/eval/episodes.csv --out-dir results/eval
"""

import argparse
import math
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


# ---------------------------------------------------------------------------------------------------------------
# 統計(scipy 不使用)
# ---------------------------------------------------------------------------------------------------------------
def wilson_ci(k, n, z=1.96):
    """成功 k / n の Wilson 95% 信頼区間 (lo, hi)"""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact(b, c):
    """対応ありの 2 値比較。b = A だけ 1、c = B だけ 1 の配置数。両側の正確 p 値(二項検定、p=0.5)"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def paired_table(a, b, label_a, label_b, obstacles_only=True):
    """拡張方策 × 回避ありの 2 つの episodes を seed で結合し、seed ごとの比較表と検定結果を返す。
    a, b: DataFrame(policy == go2-patrol, avoid == 1 に絞ってから渡す)"""
    cols = ["seed", "scene_seed", "n_placed", "success", "contact", "reached", "end_reason", "sim_s", "path_efficiency",
            "contact_steps"]
    m = a[cols].merge(b[cols], on="seed", suffixes=("_a", "_b")).sort_values("seed")
    if obstacles_only:
        m = m[m.scene_seed_a >= 0]
    n = len(m)
    res = {}
    for metric in ["success", "contact"]:
        xa, xb = m[f"{metric}_a"].astype(int), m[f"{metric}_b"].astype(int)
        b_only = int(((xa == 1) & (xb == 0)).sum())   # A だけ 1
        c_only = int(((xa == 0) & (xb == 1)).sum())   # B だけ 1
        ka, kb = int(xa.sum()), int(xb.sum())
        res[metric] = dict(n=n, k_a=ka, k_b=kb, rate_a=ka / n, rate_b=kb / n, ci_a=wilson_ci(ka, n), ci_b=wilson_ci(kb, n),
                           b=b_only, c=c_only, p=mcnemar_exact(b_only, c_only))
    both = m[(m.success_a == 1) & (m.success_b == 1)]
    res["time"] = dict(n_both=len(both), mean_a=both.sim_s_a.mean() if len(both) else float("nan"),
                       mean_b=both.sim_s_b.mean() if len(both) else float("nan"),
                       mean_a_all=m[m.success_a == 1].sim_s_a.mean() if (m.success_a == 1).any() else float("nan"),
                       mean_b_all=m[m.success_b == 1].sim_s_b.mean() if (m.success_b == 1).any() else float("nan"),
                       faster_b=int((both.sim_s_b < both.sim_s_a - 0.5).sum()), slower_b=int((both.sim_s_b > both.sim_s_a + 0.5).sum()))
    lines = [f"| seed | 障害物 | {label_a} 到達 | 成功 | 接触 | 所要 [s] | {label_b} 到達 | 成功 | 接触 | 所要 [s] | 差 [s] |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in m.iterrows():
        diff = r.sim_s_b - r.sim_s_a
        lines.append(f"| {int(r.seed)} | {int(r.n_placed_a)} | {int(r.reached_a)}/4 | {int(r.success_a)} | {int(r.contact_a)} | "
                     f"{r.sim_s_a:.1f} | {int(r.reached_b)}/4 | {int(r.success_b)} | {int(r.contact_b)} | {r.sim_s_b:.1f} | "
                     f"{diff:+.1f} |")
    return m, res, "\n".join(lines)


def stats_markdown(res, label_a, label_b):
    out = []
    for metric, name in [("success", "成功"), ("contact", "接触")]:
        r = res[metric]
        out.append(f"- **{name}率** {label_a}: {r['k_a']}/{r['n']} = {r['rate_a']:.0%} (Wilson 95% CI {r['ci_a'][0]:.0%}–{r['ci_a'][1]:.0%}) "
                   f"vs {label_b}: {r['k_b']}/{r['n']} = {r['rate_b']:.0%} (CI {r['ci_b'][0]:.0%}–{r['ci_b'][1]:.0%})。"
                   f"不一致ペア: {label_a} のみ {r['b']}、{label_b} のみ {r['c']} → McNemar 正確検定 p = {r['p']:.4f}")
    t = res["time"]
    out.append(f"- **所要時間(両方成功した {t['n_both']} 配置)** {label_a} 平均 {t['mean_a']:.1f} s vs {label_b} 平均 {t['mean_b']:.1f} s"
               f"({label_b} が 0.5 s 以上速い配置 {t['faster_b']}、遅い配置 {t['slower_b']})。各自の成功分平均: "
               f"{t['mean_a_all']:.1f} s vs {t['mean_b_all']:.1f} s")
    return "\n".join(out)


def plot_compare(res_list, path):
    """v1 vs v2(と v1 vs 回避なし)の成功率・接触率・所要時間を並べた棒グラフ"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [r[0] for r in res_list]
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    for ax, (metric, title) in zip(axes, [("success", "Success rate"), ("contact", "Contact rate"), ("time", "Mean time to complete [s]")]):
        for i, (lab, res) in enumerate(res_list):
            if metric == "time":
                v = res["time"]["mean_all"]
                ax.bar(i, v, 0.6, color=colors[i % len(colors)])
                if not np.isnan(v):
                    ax.text(i, v + 0.5, f"{v:.1f}", ha="center", va="bottom", fontsize=9, color="#333333")
            else:
                r = res[metric]
                v = r["rate"]
                lo, hi = r["ci"]
                ax.bar(i, v, 0.6, color=colors[i % len(colors)])
                ax.errorbar(i, v, yerr=[[v - lo], [hi - v]], fmt="none", ecolor="#333333", capsize=4, lw=1)
                ax.text(i, min(hi, 1.0) + 0.03, f"{v:.0%}", ha="center", va="bottom", fontsize=9, color="#333333")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title(title, fontsize=11)
        if metric != "time":
            ax.set_ylim(0, 1.18)
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", alpha=0.25)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    fig.suptitle("Patrol policy, 15 obstacle scenes (seeds 5-19), 60 s limit. Error bars: Wilson 95% CI", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[summarize] wrote {path}")


def compare_main(args):
    """--compare v1.csv v2.csv [--rerun v1_rerun.csv]: 拡張方策 × 回避ありの v1 / v2 を seed ごとに比較、検定、再現性"""
    v1 = pd.read_csv(args.compare[0])
    v2 = pd.read_csv(args.compare[1])
    sel = lambda d, av: d[(d.policy == "go2-patrol") & (d.avoid == av)].copy()
    v1_on, v1_off, v2_on = sel(v1, 1), sel(v1, 0), sel(v2, 1)
    md = []
    # 2x2(v1 の既定方策・回避なしは流用)
    base = summarize(v1)
    s2 = summarize(v2)
    s2 = s2.assign(policy="go2-patrol (v2 avoid)")
    md.append("## 条件別の集計(v1 = T04、v2 = 本タスク。既定方策と回避なしは v1 の結果を流用)\n")
    md.append(to_markdown(pd.concat([base, s2], ignore_index=True)))
    # (a) v1 on vs v1 off
    _, res_a, tbl_a = paired_table(v1_off, v1_on, "v1 回避なし", "v1 回避あり")
    md.append("\n## (a) v1 回避なし vs v1 回避あり(障害物あり 15 配置、対応あり)\n")
    md.append(stats_markdown(res_a, "回避なし", "回避あり"))
    # (b) v2 on vs v1 on
    m_b, res_b, tbl_b = paired_table(v1_on, v2_on, "v1", "v2")
    md.append("\n## (b) v1 回避あり vs v2 回避あり(障害物あり 15 配置、対応あり)\n")
    md.append(stats_markdown(res_b, "v1", "v2"))
    md.append("\n### seed ごとの比較(v1 → v2)\n")
    md.append(tbl_b)
    # 再現性
    if args.rerun:
        rr = pd.read_csv(args.rerun)
        m_r, res_r, tbl_r = paired_table(v1_on, sel(rr, 1), "v1 (T04)", "v1 再実行")
        md.append("\n## 再現性: v1 回避あり の再実行(同一条件、障害物あり 15 配置)\n")
        md.append(stats_markdown(res_r, "T04", "再実行"))
        changed_s = int((m_r.success_a != m_r.success_b).sum())
        changed_c = int((m_r.contact_a != m_r.contact_b).sum())
        dt = (m_r.sim_s_b - m_r.sim_s_a).abs()
        md.append(f"- 成功が変わった配置: {changed_s}、接触が変わった配置: {changed_c}、所要時間が 1 s 以上変わった配置: "
                  f"{int((dt > 1.0).sum())}(最大 {dt.max():.1f} s、中央値 {dt.median():.1f} s)")
        md.append("\n" + tbl_r)
    text = "\n".join(md)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    pd.concat([base, s2], ignore_index=True).to_csv(os.path.join(args.out_dir, "summary.csv"), index=False, float_format="%.4f")
    print(text)
    # 図
    def pack(res, key):
        return dict(success=dict(rate=res["success"][f"rate_{key}"], ci=res["success"][f"ci_{key}"]),
                    contact=dict(rate=res["contact"][f"rate_{key}"], ci=res["contact"][f"ci_{key}"]),
                    time=dict(mean_all=res["time"][f"mean_{key}_all"]))
    res_list = [("v1\navoid off", pack(res_a, "a")), ("v1\navoid on", pack(res_b, "a")), ("v2\navoid on", pack(res_b, "b"))]
    if args.rerun:
        res_list.insert(2, ("v1 rerun\navoid on", pack(res_r, "b")))
    plot_compare(res_list, os.path.join(args.out_dir, "summary.png"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=str, default="results/eval/episodes.csv")
    parser.add_argument("--out-dir", type=str, default="results/eval")
    parser.add_argument("--compare", type=str, nargs=2, default=None, metavar=("V1_CSV", "V2_CSV"),
                        help="v1 と v2 の episodes.csv を seed ごとに比較し、McNemar / Wilson CI を出す")
    parser.add_argument("--rerun", type=str, default=None, help="v1 回避ありの再実行 episodes.csv(再現性の計測)")
    args = parser.parse_args()
    if args.compare:
        compare_main(args)
        return
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
