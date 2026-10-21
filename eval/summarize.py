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


# ---------------------------------------------------------------------------------------------------------------
# 3 条件比較(T07): v1 回避なし / v1 回避あり / v2 回避あり、拡張方策、障害物あり配置
# ---------------------------------------------------------------------------------------------------------------
def sign_test(n_pos, n_neg):
    """符号検定(両側、正確)。差が 0 のものは除く"""
    return mcnemar_exact(n_pos, n_neg)


def wilcoxon_signed_rank(diffs):
    """Wilcoxon 符号順位検定(正規近似、タイ補正、n ≥ 10 目安)。戻り値 (W+, z, p 両側)。差 0 は除く"""
    d = np.asarray([x for x in diffs if x != 0.0], dtype=float)
    n = len(d)
    if n < 5:
        return float("nan"), float("nan"), float("nan")
    absd = np.abs(d)
    order = np.argsort(absd)
    ranks = np.empty(n)
    # 平均順位(タイ)
    sorted_abs = absd[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_abs[j + 1] == sorted_abs[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    w_plus = float(ranks[d > 0].sum())
    mean = n * (n + 1) / 4.0
    # タイ補正
    _, counts = np.unique(sorted_abs, return_counts=True)
    tie = float(np.sum(counts ** 3 - counts))
    var = n * (n + 1) * (2 * n + 1) / 24.0 - tie / 48.0
    z = (w_plus - mean) / math.sqrt(var) if var > 0 else float("nan")
    p = math.erfc(abs(z) / math.sqrt(2)) if not math.isnan(z) else float("nan")
    return w_plus, z, p


def _parse_range(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def compare3_main(args):
    df = pd.read_csv(args.compare3)
    seeds = _parse_range(args.scenes)
    df = df[(df.policy == "go2-patrol") & (df.seed.isin(seeds))].copy()
    if "avoid_version" not in df.columns:
        df["avoid_version"] = "v1"
    df["avoid_version"] = df["avoid_version"].fillna("")
    conds = {
        "v1 回避なし": df[df.avoid == 0],
        "v1 回避あり": df[(df.avoid == 1) & (df.avoid_version == "v1")],
        "v2 回避あり": df[(df.avoid == 1) & (df.avoid_version == "v2")],
    }
    if (df.avoid_version == "v3").any():
        conds["v3 地図+A*"] = df[(df.avoid == 1) & (df.avoid_version == "v3")]
    md = [f"## 3 条件の集計(拡張方策、障害物あり配置 seed {args.scenes}、60 s 上限)\n",
          "| 条件 | n | 成功率 [95% CI] | 接触率 [95% CI] | ニアミス率 | 転倒 | 平均到達 | 所要 [s](成功分) | 経路効率(成功分) |",
          "|---|---|---|---|---|---|---|---|---|"]
    stats = {}
    for name, g in conds.items():
        n = len(g)
        ks, kc = int(g.success.sum()), int(g.contact.sum())
        succ = g[g.success == 1]
        cis, cic = wilson_ci(ks, n), wilson_ci(kc, n)
        t = succ.time_to_complete.astype(float).mean() if len(succ) else float("nan")
        e = succ.path_efficiency.astype(float).mean() if len(succ) else float("nan")
        stats[name] = dict(n=n, ks=ks, kc=kc, rate_s=ks / n if n else float("nan"), rate_c=kc / n if n else float("nan"),
                           ci_s=cis, ci_c=cic, time=t, eff=e)
        md.append(f"| {name} | {n} | {ks}/{n} = {ks / n:.0%} [{cis[0]:.0%}–{cis[1]:.0%}] | {kc}/{n} = {kc / n:.0%} "
                  f"[{cic[0]:.0%}–{cic[1]:.0%}] | {g.near_miss.mean():.0%} | {int(g.fell.sum())} | {g.reached.mean():.2f} | "
                  f"{t:.1f} | {e:.2f} |")
    # McNemar
    def paired(a, b):
        m = a[["seed", "success", "contact", "sim_s", "reached", "end_reason"]].merge(
            b[["seed", "success", "contact", "sim_s", "reached", "end_reason"]], on="seed", suffixes=("_a", "_b"))
        return m
    md.append("\n## 対応あり比較(同じ seed)\n")
    pairs = [("v1 回避なし", "v1 回避あり"), ("v1 回避あり", "v2 回避あり")]
    if "v3 地図+A*" in conds:
        pairs += [("v1 回避あり", "v3 地図+A*"), ("v2 回避あり", "v3 地図+A*")]
    for la, lb in pairs:
        m = paired(conds[la], conds[lb])
        for metric, mname in [("success", "成功"), ("contact", "接触")]:
            xa, xb = m[f"{metric}_a"].astype(int), m[f"{metric}_b"].astype(int)
            b_only, c_only = int(((xa == 1) & (xb == 0)).sum()), int(((xa == 0) & (xb == 1)).sum())
            md.append(f"- **{mname}** {la} vs {lb}(n = {len(m)}): {la} のみ {b_only}、{lb} のみ {c_only} → "
                      f"McNemar 正確検定 p = {mcnemar_exact(b_only, c_only):.4f}")
    # 所要時間の対応あり比較(v1 vs v2、v3 があれば v1 vs v3、v2 vs v3 も)
    time_pairs = [("v1 回避あり", "v2 回避あり")] + ([("v1 回避あり", "v3 地図+A*"), ("v2 回避あり", "v3 地図+A*")] if "v3 地図+A*" in conds else [])
    for la, lb in time_pairs:
        m = paired(conds[la], conds[lb])
        both = m[(m.success_a == 1) & (m.success_b == 1)]
        diffs = (both.sim_s_b - both.sim_s_a).to_numpy()
        if len(diffs) == 0:
            continue
        n_pos, n_neg = int((diffs > 0.5).sum()), int((diffs < -0.5).sum())
        w, z, p_w = wilcoxon_signed_rank(diffs)
        sa, sb = la.split()[0], lb.split()[0]
        md.append(f"\n## 所要時間: {la} vs {lb}(両方成功した {len(both)} 配置)\n")
        md.append(f"- {sa} 平均 {both.sim_s_a.mean():.1f} s、{sb} 平均 {both.sim_s_b.mean():.1f} s。差({sb} − {sa})の中央値 {np.median(diffs):+.1f} s、"
                  f"平均 {diffs.mean():+.1f} s、最小 {diffs.min():+.1f} s、最大 {diffs.max():+.1f} s")
        md.append(f"- {sb} が 0.5 s 以上速い配置 {n_neg}、遅い配置 {n_pos}、±0.5 s 以内 {len(diffs) - n_pos - n_neg} → "
                  f"符号検定 p = {sign_test(n_pos, n_neg):.4f}")
        md.append(f"- Wilcoxon 符号順位検定(正規近似、タイ補正): W+ = {w:.0f}, z = {z:+.2f}, p = {p_w:.4f}")
    m = paired(conds["v1 回避あり"], conds["v2 回避あり"])
    both = m[(m.success_a == 1) & (m.success_b == 1)]
    diffs = (both.sim_s_b - both.sim_s_a).to_numpy()
    # 失敗一覧
    md.append("\n## 失敗配置の一覧\n")
    md.append("| 条件 | seed | 到達 | 終了理由 | 接触ステップ | 所要 [s] |")
    md.append("|---|---|---|---|---|---|")
    for name, g in conds.items():
        for _, r in g[g.success == 0].sort_values("seed").iterrows():
            md.append(f"| {name} | {int(r.seed)} | {int(r.reached)}/4 | {r.end_reason} | {int(r.contact_steps)} | {r.sim_s:.1f} |")
    v1f_v2s = m[(m.success_a == 0) & (m.success_b == 1)].seed.tolist()
    v1s_v2f = m[(m.success_a == 1) & (m.success_b == 0)].seed.tolist()
    md.append(f"\n- v1 で失敗し v2 で成功: {v1f_v2s}\n- v1 で成功し v2 で失敗: {v1s_v2f}")
    if "v3 地図+A*" in conds:
        for la in ["v1 回避あり", "v2 回避あり"]:
            mm = paired(conds[la], conds["v3 地図+A*"])
            md.append(f"- {la} で失敗し v3 で成功: {mm[(mm.success_a == 0) & (mm.success_b == 1)].seed.tolist()}、"
                      f"{la} で成功し v3 で失敗: {mm[(mm.success_a == 1) & (mm.success_b == 0)].seed.tolist()}")
    text = "\n".join(md)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    pd.DataFrame([dict(cond=k, **{kk: (vv if not isinstance(vv, tuple) else f"{vv[0]:.3f}-{vv[1]:.3f}") for kk, vv in v.items()})
                  for k, v in stats.items()]).to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)
    print(text)
    # 図: 成功率・接触率・所要時間
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = ["v1\navoid off", "v1\navoid on", "v2\navoid on", "v3\nmap+A*"][:len(stats)]
    colors = ["#2a78d6", "#eb6834", "#eda100", "#1baf7a"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    for ax, (key, title) in zip(axes, [("rate_s", "Success rate"), ("rate_c", "Contact rate"), ("time", "Mean time to complete [s]")]):
        for i, (name, st) in enumerate(stats.items()):
            v = st[key]
            ax.bar(i, v, 0.6, color=colors[i])
            if key != "time":
                lo, hi = st["ci_s"] if key == "rate_s" else st["ci_c"]
                ax.errorbar(i, v, yerr=[[v - lo], [hi - v]], fmt="none", ecolor="#333333", capsize=4, lw=1)
                ax.text(i, min(hi, 1.0) + 0.03, f"{v:.0%}", ha="center", va="bottom", fontsize=9, color="#333333")
            elif not np.isnan(v):
                ax.text(i, v + 0.5, f"{v:.1f}", ha="center", va="bottom", fontsize=9, color="#333333")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title(title, fontsize=11)
        if key != "time":
            ax.set_ylim(0, 1.18)
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", alpha=0.25)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    n0 = stats["v1 回避なし"]["n"]
    fig.suptitle(f"Patrol policy, {n0} obstacle scenes (seeds {args.scenes}), 60 s limit. Error bars: Wilson 95% CI", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out_dir, "summary.png"), dpi=150, bbox_inches="tight")
    fig2, ax2 = plt.subplots(figsize=(6, 3.6))
    ax2.hist(diffs, bins=np.arange(-35, 36, 5), color="#eda100", edgecolor="white")
    ax2.axvline(0, color="#333333", lw=1)
    ax2.set_xlabel("time v2 - v1 [s] (both succeeded)")
    ax2.set_ylabel("scenes")
    ax2.set_title(f"Time difference v2 - v1 (n = {len(diffs)}, median {np.median(diffs):+.1f} s)", fontsize=10)
    for sp in ["top", "right"]:
        ax2.spines[sp].set_visible(False)
    fig2.tight_layout()
    fig2.savefig(os.path.join(args.out_dir, "time_diff_hist.png"), dpi=150)
    print(f"[summarize] wrote {args.out_dir}/summary.png, time_diff_hist.png")


def compare_lidar_main(args):
    """T12: 同じ episodes.csv 内の lidar 2d / 3d(拡張方策 × v3)を seed で対応づけて比較"""
    df = pd.read_csv(args.compare_lidar)
    seeds = _parse_range(args.scenes)
    df = df[(df.policy == "go2-patrol") & (df.seed.isin(seeds))].copy()
    df["lidar"] = df["lidar"].fillna("2d")
    df["first_contact_type"] = df["first_contact_type"].fillna("")
    conds = {"v3 + 2D LiDAR": df[df.lidar == "2d"], "v3 + 3D LiDAR": df[df.lidar == "3d"]}
    md = [f"## 2D / 3D LiDAR の比較(拡張方策 × v3、混合配置 seed {args.scenes}、60 s 上限)\n",
          "| 条件 | n | 成功率 [95% CI] | 接触率 [95% CI] | 転倒率 | 平均到達 | 所要 [s](成功分) | 経路効率(成功分) |",
          "|---|---|---|---|---|---|---|---|"]
    stats = {}
    for name, g in conds.items():
        n = len(g)
        ks, kc, kf = int(g.success.sum()), int(g.contact.sum()), int(g.fell.sum())
        succ = g[g.success == 1]
        cis, cic = wilson_ci(ks, n), wilson_ci(kc, n)
        t = succ.time_to_complete.astype(float).mean() if len(succ) else float("nan")
        e = succ.path_efficiency.astype(float).mean() if len(succ) else float("nan")
        stats[name] = dict(n=n, rate_s=ks / n, rate_c=kc / n, ci_s=cis, ci_c=cic, time=t)
        md.append(f"| {name} | {n} | {ks}/{n} = {ks / n:.0%} [{cis[0]:.0%}–{cis[1]:.0%}] | {kc}/{n} = {kc / n:.0%} "
                  f"[{cic[0]:.0%}–{cic[1]:.0%}] | {kf}/{n} | {g.reached.mean():.2f} | {t:.1f} | {e:.2f} |")
    a, b = conds["v3 + 2D LiDAR"], conds["v3 + 3D LiDAR"]
    cols = ["seed", "success", "contact", "fell", "sim_s", "reached", "end_reason", "first_contact_type", "contact_types"]
    m = a[cols].merge(b[cols], on="seed", suffixes=("_2d", "_3d"))
    md.append("\n## 対応あり比較(同じ seed)\n")
    for metric, name in [("success", "成功"), ("contact", "接触")]:
        x2, x3 = m[f"{metric}_2d"].astype(int), m[f"{metric}_3d"].astype(int)
        b_only, c_only = int(((x2 == 1) & (x3 == 0)).sum()), int(((x2 == 0) & (x3 == 1)).sum())
        md.append(f"- **{name}** 2D vs 3D(n = {len(m)}): 2D のみ {b_only}、3D のみ {c_only} → McNemar 正確検定 p = {mcnemar_exact(b_only, c_only):.4f}")
    both = m[(m.success_2d == 1) & (m.success_3d == 1)]
    if len(both):
        diffs = (both.sim_s_3d - both.sim_s_2d).to_numpy()
        n_pos, n_neg = int((diffs > 0.5).sum()), int((diffs < -0.5).sum())
        md.append(f"- **所要時間**(両方成功した {len(both)} 配置): 2D 平均 {both.sim_s_2d.mean():.1f} s、3D 平均 {both.sim_s_3d.mean():.1f} s、"
                  f"差(3D − 2D)の中央値 {np.median(diffs):+.1f} s。3D が速い {n_neg} / 遅い {n_pos} → 符号検定 p = {sign_test(n_pos, n_neg):.4f}")
    md.append("\n## 失敗の内訳(障害物タイプ別)\n")
    md.append("| 条件 | 低い箱に接触 | テーブル天板に接触 | テーブル脚に接触 | 高い障害物に接触 | 転倒 | 時間切れ(接触なし) | 成功 |")
    md.append("|---|---|---|---|---|---|---|---|")
    for name, g in conds.items():
        fc = g.first_contact_type.astype(str)
        ct = g.contact_types.fillna("").astype(str)
        low = int(ct.str.contains("lowbox").sum())
        top = int(ct.str.contains("table_top").sum())
        leg = int(ct.str.contains("table_leg").sum())
        high = int((ct.str.contains("box(?!_)|cylinder", regex=True) & ~ct.str.contains("lowbox")).sum())
        fell = int(g.fell.sum())
        to = int(((g.end_reason == "timeout") & (g.contact == 0)).sum())
        md.append(f"| {name} | {low} | {top} | {leg} | {high} | {fell} | {to} | {int(g.success.sum())} |")
    md.append("\n(接触は 1 エピソード内で複数タイプに当たることがあるので合計は接触エピソード数を超えうる)")
    md.append("\n## seed ごと\n")
    md.append("| seed | 2D 到達 | 成功 | 接触(最初の相手) | 所要 [s] | 3D 到達 | 成功 | 接触(最初の相手) | 所要 [s] |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in m.sort_values("seed").iterrows():
        md.append(f"| {int(r.seed)} | {int(r.reached_2d)}/4 | {int(r.success_2d)} | {int(r.contact_2d)} ({r.first_contact_type_2d or '—'}) | {r.sim_s_2d:.1f} | "
                  f"{int(r.reached_3d)}/4 | {int(r.success_3d)} | {int(r.contact_3d)} ({r.first_contact_type_3d or '—'}) | {r.sim_s_3d:.1f} |")
    text = "\n".join(md)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    pd.DataFrame([dict(cond=k, **{kk: (vv if not isinstance(vv, tuple) else f"{vv[0]:.3f}-{vv[1]:.3f}") for kk, vv in v.items()})
                  for k, v in stats.items()]).to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)
    print(text)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = ["v3 + 2D", "v3 + 3D"]
    colors = ["#2a78d6", "#1baf7a"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.2))
    for ax, (key, title) in zip(axes, [("rate_s", "Success rate"), ("rate_c", "Contact rate"), ("time", "Mean time to complete [s]")]):
        for i, (name, st) in enumerate(stats.items()):
            v = st[key]
            ax.bar(i, v, 0.6, color=colors[i])
            if key != "time":
                lo, hi = st["ci_s"] if key == "rate_s" else st["ci_c"]
                ax.errorbar(i, v, yerr=[[v - lo], [hi - v]], fmt="none", ecolor="#333333", capsize=4, lw=1)
                ax.text(i, min(hi, 1.0) + 0.03, f"{v:.0%}", ha="center", va="bottom", fontsize=9)
            elif not np.isnan(v):
                ax.text(i, v + 0.5, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(range(2))
        ax.set_xticklabels(labels)
        ax.set_title(title, fontsize=11)
        if key != "time":
            ax.set_ylim(0, 1.18)
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", alpha=0.25)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    fig.suptitle(f"Low obstacles and tables: 2D vs 3D LiDAR (v3, {stats['v3 + 2D LiDAR']['n']} mixed scenes). Error bars: Wilson 95% CI", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out_dir, "summary.png"), dpi=150, bbox_inches="tight")
    print(f"[summarize] wrote {args.out_dir}/summary.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=str, default="results/eval/episodes.csv")
    parser.add_argument("--out-dir", type=str, default="results/eval")
    parser.add_argument("--compare", type=str, nargs=2, default=None, metavar=("V1_CSV", "V2_CSV"),
                        help="v1 と v2 の episodes.csv を seed ごとに比較し、McNemar / Wilson CI を出す")
    parser.add_argument("--rerun", type=str, default=None, help="v1 回避ありの再実行 episodes.csv(再現性の計測)")
    parser.add_argument("--compare3", type=str, default=None, metavar="CSV",
                        help="1 つの episodes.csv 内の v1 回避なし / v1 回避あり / v2 回避あり を比較(T07)")
    parser.add_argument("--scenes", type=str, default="5-49", help="--compare3 / --compare-lidar で使う seed 範囲")
    parser.add_argument("--compare-lidar", type=str, default=None, metavar="CSV", help="T12: lidar 2d / 3d の比較(v3)")
    args = parser.parse_args()
    if args.compare_lidar:
        compare_lidar_main(args)
        return
    if args.compare3:
        compare3_main(args)
        return
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
