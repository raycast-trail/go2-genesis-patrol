"""
scripts/make_arch.py — 構成図 figs/arch.png(1280×720)を描く。make_figs.py の arch() の置き換え(T11)。

方針: 矢印はすべて直交(縦・横)にし、ラベルは矢印の脇(重ねない)。左右の余白 ≥ 100 px。
フォント: macOS ならヒラギノ、無ければ Noto Sans CJK JP(レポート用のコンテナ描画と同じ)。
使い方: python scripts/make_arch.py [--out figs/arch.png]
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 12.8, 7.2  # 1 unit = 100 px

for cand in ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
             "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"]:
    if os.path.exists(cand):
        font_manager.fontManager.addfont(cand)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cand).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

BLUE, ORANGE, GREEN, GRAY = "#e8eef8", "#fde9df", "#e4f5ec", "#f3f3f3"
RED, GRN, GRY, INK = "#c0504d", "#2e8b57", "#777777", "#333333"


def main(out):
    fig, ax = plt.subplots(figsize=(W, H), dpi=100)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    # (x, y, w, h, text, color, fontsize)
    boxes = {
        "wp":    (0.35, 4.5, 2.3, 1.2, "ウェイポイント列\n(2 m 角の正方形)", BLUE, 14),
        "foll":  (3.1,  4.5, 2.0, 1.2, "経路追従\n(P 制御)", BLUE, 14),
        "avoid": (5.55, 4.5, 2.8, 1.2, "反応的回避 v1 / v2\n(v3 では下層)", ORANGE, 14),
        "cmd":   (8.8,  4.5, 3.0, 1.2, "速度指令 (vx, vy, ωz)\nvx 0–0.8, ωz ±0.8", BLUE, 14),
        "map":   (1.7,  2.35, 3.1, 1.3, "占有格子 + A* (v3)\n0.05 m 格子、膨張 0.35 m\n1 s ごとに再計画", GREEN, 12.5),
        "lidar": (5.7,  2.35, 2.8, 1.3, "疑似 2D LiDAR\n72 本 / 5° / 5 m\n地面除去 → セクタ最小距離", ORANGE, 12.5),
        "pol":   (8.8,  2.35, 3.0, 1.3, "歩行方策 (RL / PPO)\n4096 env 並列学習", GREEN, 14),
        "sim":   (5.7,  0.35, 6.1, 1.1, "Genesis 物理シム(Go2 + 障害物)", GRAY, 14),
    }
    for x, y, w, h, text, fc, fs in boxes.values():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.14", fc=fc, ec=INK, lw=1.5))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.35)

    def arrow(p, q, color=INK, lw=2):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=20, lw=lw, color=color,
                                     shrinkA=0, shrinkB=0))

    def line(p, q, color=INK, lw=2):
        ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, solid_capstyle="round")

    def label(x, y, text, color=INK, ha="left", fs=12):
        ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color)

    # 上段の横方向パイプライン
    arrow((2.65, 5.1), (3.1, 5.1))
    arrow((5.1, 5.1), (5.55, 5.1))
    arrow((8.35, 5.1), (8.8, 5.1))

    # 速度指令 → 歩行方策 → Genesis(縦)、ラベルは矢印の右
    arrow((10.3, 4.5), (10.3, 3.65))
    label(10.45, 4.08, "50 Hz")
    arrow((10.3, 2.35), (10.3, 1.45))
    label(10.45, 1.9, "12 関節目標角")

    # Genesis → LiDAR(レイキャスト、縦)、LiDAR → 回避(セクタ距離、縦)
    arrow((6.95, 1.45), (6.95, 2.35), RED)
    label(7.1, 1.9, "レイキャスト", RED)
    arrow((6.95, 3.65), (6.95, 4.5), RED)
    label(7.1, 4.08, "セクタ距離", RED)

    # LiDAR → 占有格子(ヒット点、横)、占有格子 → 経路追従(ローカル目標、縦)
    arrow((5.7, 3.0), (4.8, 3.0), GRN)
    label(5.25, 3.3, "ヒット点", GRN, ha="center", fs=10.5)
    arrow((4.6, 3.65), (4.6, 4.5), GRN)
    label(4.75, 4.08, "ローカル目標 (0.8 m 先)", GRN, fs=10)   # ヒラギノでは 11 だと右の「セクタ距離」に接近するため 10 に(T11)

    # Genesis → 姿勢(真の姿勢)→ 経路追従・占有格子(灰、直交の折れ線)
    px = 0.8
    line((5.7, 0.9), (px, 0.9), GRY)
    line((px, 0.9), (px, 4.1), GRY)
    line((px, 4.1), (3.4, 4.1), GRY)
    arrow((3.4, 4.1), (3.4, 4.5), GRY)        # → 経路追従
    arrow((px, 3.0), (1.7, 3.0), GRY)          # → 占有格子
    label(3.25, 1.12, "姿勢 (x, y, yaw) — 真の姿勢、SLAM なし", GRY, ha="center")

    # 見出し
    ax.text(0.35, 6.62, "構成: 実機 Go2 の「自己位置 → 地図・計画 → 速度指令 → 歩行」と同じ 3 層構造",
            fontsize=18, weight="bold", va="center")
    ax.text(0.35, 6.18, "学習は歩行方策だけ。ナビ層は決定的・説明可能。v1/v2 は地図なしの反応的回避、v3 は占有格子 + A* の大域計画",
            fontsize=13, color="#444444", va="center")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, dpi=100, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="figs/arch.png")
    main(ap.parse_args().out)
