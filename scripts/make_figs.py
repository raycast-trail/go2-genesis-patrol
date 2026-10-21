"""
scripts/make_figs.py — 提出動画用の図(figs/*.png、1280×720 に収まるようにパディング)。

  figs/arch.png          構成図(LiDAR → 回廊判定 → 回避則 → 速度指令 → RL 方策 → Genesis)
  figs/train_curve.png   logs/go2-patrol の tfevents から rew_tracking_lin_vel / rew_tracking_ang_vel
  figs/result_50.png     results/eval_50/episodes.csv から成功率・接触率・所要時間(文字を大きく再描画)
  figs/traj_compare.png  results/t01_square_traj_compare.png をパディング
  figs/traj_t03_seed0.png results/t03_traj_seed0.png をパディング
使い方: python scripts/make_figs.py
"""

import glob
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from PIL import Image

W, H = 1280, 720
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
if os.path.exists(FONT):
    font_manager.fontManager.addfont(FONT)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False
os.makedirs("figs", exist_ok=True)


def pad_to_frame(src, dst, bg=(255, 255, 255), top=0):
    """src を W×H に収めてパディング。top > 0 なら上 top px を空けて(帯テロップの下に)配置"""
    im = Image.open(src).convert("RGB")
    scale = min(W / im.width, (H - top) / im.height)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), bg)
    canvas.paste(im, ((W - im.width) // 2, top + (H - top - im.height) // 2))
    canvas.save(dst)
    print("wrote", dst)


def arch():
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 7.2)
    ax.axis("off")
    boxes = [
        (0.4, 4.6, 2.3, 1.3, "ウェイポイント列\n(2 m 角の正方形)", "#e8eef8"),
        (3.2, 4.6, 2.3, 1.3, "経路追従\n(P 制御)", "#e8eef8"),
        (6.0, 4.6, 2.6, 1.3, "反応的回避 v1 / v2\n(v3 では下層)", "#fde9df"),
        (9.3, 4.6, 3.1, 1.3, "速度指令 (vx, vy, ωz)\nvx 0–0.8, ωz ±0.8", "#e8eef8"),
        (9.3, 2.3, 3.1, 1.3, "歩行方策 (RL / PPO)\n4096 env 並列学習", "#e4f5ec"),
        (8.9, 0.3, 3.7, 1.3, "Genesis 物理シム\nGo2 + 障害物", "#f3f3f3"),
        (3.6, 1.9, 4.0, 1.7, "疑似 2D LiDAR (Raycaster)\n72 本 / 5° / 5 m\n地面除去 → セクタ最小距離", "#fde9df"),
        (0.2, 2.0, 3.1, 1.6, "占有格子 + A* (v3)\n0.05 m 格子、膨張 0.35 m\n1 s ごとに再計画", "#e4f5ec"),
    ]
    for x, y, w, h, text, fc in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15", fc=fc, ec="#333333", lw=1.5))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=15 if "A*" not in text else 13, linespacing=1.4)

    def arrow(p, q, text=None, color="#333333"):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=22, lw=2, color=color))
        if text:
            ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 0.18, text, ha="center", fontsize=12, color=color)
    arrow((2.7, 5.25), (3.2, 5.25))
    arrow((5.5, 5.25), (6.0, 5.25))
    arrow((8.6, 5.25), (9.3, 5.25))
    arrow((10.85, 4.6), (10.85, 3.6), "50 Hz")
    arrow((10.85, 2.3), (10.85, 1.6))
    ax.text(11.0, 1.85, "12 関節目標角", ha="left", fontsize=12)
    arrow((8.9, 1.1), (7.6, 2.4), None, "#c0504d")
    ax.text(8.55, 1.45, "レイキャスト", ha="left", fontsize=12, color="#c0504d")
    arrow((5.8, 3.6), (7.0, 4.6), None, "#c0504d")
    ax.text(5.95, 4.2, "セクタ距離", ha="left", fontsize=12, color="#c0504d")
    arrow((3.6, 2.6), (3.3, 2.6), None, "#2e8b57")
    ax.text(3.45, 2.2, "ヒット点", ha="center", fontsize=10, color="#2e8b57")
    arrow((1.75, 3.6), (3.6, 4.6), None, "#2e8b57")
    ax.text(1.3, 4.2, "ローカル目標 (0.8 m 先)", ha="left", fontsize=12, color="#2e8b57")
    arrow((8.9, 0.75), (0.1, 0.75), "", "#777777")
    ax.text(5.0, 0.95, "姿勢 (x, y, yaw)(真の姿勢、SLAM なし)", ha="center", fontsize=12, color="#777777")
    arrow((0.1, 0.75), (0.1, 4.6), "", "#777777")
    ax.text(0.55, 6.55, "構成: 実機 Go2 の「自己位置 → 地図・計画 → 速度指令 → 歩行」と同じ 3 層構造", fontsize=18, weight="bold")
    ax.text(0.55, 6.15, "学習は歩行方策だけ。ナビ層は決定的・説明可能。v1/v2 は地図なしの反応的回避、v3 は占有格子 + A* の大域計画", fontsize=14, color="#444444")
    fig.savefig("figs/arch.png", dpi=100, facecolor="white")
    print("wrote figs/arch.png")


def train_curve(half=False):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    ev = glob.glob("logs/go2-patrol/events.out.tfevents.*")[0]
    acc = EventAccumulator(ev, size_guidance={"scalars": 0})
    acc.Reload()
    tags = acc.Tags()["scalars"]
    def get(name):
        t = [x for x in tags if x.endswith(name)]
        if not t:
            return None, None
        s = acc.Scalars(t[0])
        return np.array([e.step for e in s]), np.array([e.value for e in s])
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 7.2), dpi=100) if half else plt.subplots(1, 3, figsize=(12.8, 7.2), dpi=100)
    for ax, (name, title, ymax) in zip(axes, [("rew_tracking_lin_vel", "rew_tracking_lin_vel(上限 1.0)", 1.05),
                                             ("rew_tracking_ang_vel", "rew_tracking_ang_vel(上限 0.2)", 0.21),
                                             ("Train/mean_episode_length", "Mean episode length(上限 1000)", 1050)]):
        x, y = get(name)
        if x is None:
            x, y = get(name.split("/")[-1])
        if x is None:
            ax.text(0.5, 0.5, f"{name}\nが見つからない", ha="center", transform=ax.transAxes)
            continue
        ax.plot(x, y, color="#eb6834", lw=2)
        ax.set_ylim(0, ymax)
        ax.set_xlabel("iteration", fontsize=14)
        ax.set_title(title, fontsize=15)
        ax.tick_params(labelsize=12)
        ax.grid(alpha=0.3)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.annotate(f"{y[-1]:.3f}" if ymax < 10 else f"{y[-1]:.0f}", (x[-1], y[-1]), textcoords="offset points", xytext=(-40, -18), fontsize=13)
    if half:
        fig.suptitle("学習曲線(4096 env × 300 it)", fontsize=14)
        for ax in axes[:-1]:
            ax.set_xlabel("")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig("figs/train_curve_half.png", dpi=100, facecolor="white")
        print("wrote figs/train_curve_half.png")
        return
    fig.suptitle("歩行方策の学習曲線(go2-patrol: 4096 env × 300 it、約 9 分、M1 Max / Metal)", fontsize=17)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig("figs/train_curve.png", dpi=100, facecolor="white")
    print("wrote figs/train_curve.png", "tags:", [t for t in tags if "tracking" in t or "episode" in t][:6])


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


def result_50(half=False):
    import pandas as pd
    df = pd.read_csv("results/eval_50/episodes.csv")
    df = df[(df.policy == "go2-patrol") & (df.seed >= 5)].copy()
    df["avoid_version"] = df["avoid_version"].fillna("")
    conds = [("回避なし", df[df.avoid == 0]), ("回避 v1", df[(df.avoid == 1) & (df.avoid_version == "v1")]),
             ("回避 v2", df[(df.avoid == 1) & (df.avoid_version == "v2")])]
    if (df.avoid_version == "v3").any():
        conds.append(("v3 地図+A*", df[(df.avoid == 1) & (df.avoid_version == "v3")]))
    colors = ["#2a78d6", "#eb6834", "#eda100", "#1baf7a"]
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 7.2), dpi=100) if half else plt.subplots(1, 3, figsize=(12.8, 7.2), dpi=100)
    for ax, (key, title) in zip(axes, [("success", "成功率(4/4・転倒なし・接触なし)"), ("contact", "接触率(物理接触)"), ("time", "所要時間 [s](成功分の平均)")]):
        for i, (name, g) in enumerate(conds):
            n = len(g)
            if key == "time":
                v = g[g.success == 1].time_to_complete.astype(float).mean()
                ax.bar(i, v, 0.6, color=colors[i])
                ax.text(i, v + 0.6, f"{v:.1f}", ha="center", va="bottom", fontsize=15)
            else:
                k = int(g[key].sum())
                v = k / n
                lo, hi = wilson(k, n)
                ax.bar(i, v, 0.6, color=colors[i])
                ax.errorbar(i, v, yerr=[[v - lo], [hi - v]], fmt="none", ecolor="#333333", capsize=5, lw=1.5)
                ax.text(i, min(hi, 1.0) + 0.03, f"{v:.0%}", ha="center", va="bottom", fontsize=15)
        ax.set_xticks(range(len(conds)))
        ax.set_xticklabels([c[0] for c in conds], fontsize=14 if len(conds) <= 3 else 12)
        ax.set_title(title, fontsize=15)
        ax.tick_params(axis="y", labelsize=13)
        if key != "time":
            ax.set_ylim(0, 1.18)
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", alpha=0.3)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
    if half:
        for ax in axes:
            ax.set_title(ax.get_title(), fontsize=12)
            ax.tick_params(labelsize=11)
        axes[2].set_ylim(0, 42)
        fig.suptitle(f"45 配置 × {len(conds)} 条件(誤差棒 = Wilson 95% CI)", fontsize=13)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig("figs/result_50_half.png", dpi=100, facecolor="white")
        print("wrote figs/result_50_half.png")
        return
    fig.suptitle(f"定量評価: 障害物あり 45 配置 × {len(conds)} 条件(拡張方策、60 s 上限、誤差棒 = Wilson 95% CI)", fontsize=17)
    fig.text(0.5, 0.015, "回避なし → v1: 成功 9% → 91%、接触 91% → 0%(McNemar p < 0.0001)。v3 は 100%、所要 24.2 s は v1/v2 より短い(p < 0.0001)",
             ha="center", fontsize=13, color="#444444")
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig("figs/result_50.png", dpi=100, facecolor="white")
    print("wrote figs/result_50.png")


def foxglove_crop(src="results/t06_foxglove_seed10.png", dst="figs/foxglove_crop.png"):
    """Foxglove のスクリーンショットから 3D パネルと Plot だけを切り出す(上部バーと左の設定パネルを除く)"""
    if not os.path.exists(src):
        print("skip", src)
        return
    im = Image.open(src).convert("RGB")
    w, h = im.size
    box = (int(w * 0.287), int(h * 0.085), int(w * 0.993), int(h * 0.96))
    im.crop(box).save(dst)
    print("wrote", dst, im.crop(box).size)


if __name__ == "__main__":
    foxglove_crop()
    arch()
    train_curve()
    train_curve(half=True)
    result_50()
    result_50(half=True)
    pad_to_frame("results/t01_square_traj_compare.png", "figs/traj_compare.png")
    pad_to_frame("results/t03_traj_seed0.png", "figs/traj_t03_seed0.png")
    if os.path.exists("results/t09_traj_seed28.png"):
        pad_to_frame("results/t09_traj_seed28.png", "figs/traj_seed28.png", top=90)   # 帯(90 px)の下に置く
