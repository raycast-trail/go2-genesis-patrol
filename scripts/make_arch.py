"""構成図(最終形 v3 のみ)。層ごとに上から下へ。矢印は直交、ラベルは矢印の脇。"""
import argparse, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

W, H = 12.8, 7.2
for cand in ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"]:
    if os.path.exists(cand):
        font_manager.fontManager.addfont(cand)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cand).get_name(); break

C_PLAN, C_CMD, C_RL, C_SIM, C_SENS = "#dcf1e3", "#e3ebf7", "#ebe2f6", "#f0f0f0", "#fff1c9"
A_CMD, A_SENS, A_POSE, EDGE = "#333333", "#c98500", "#8a8a8a", "#444444"


def main(out):
    fig = plt.figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

    # 層の帯(薄い背景)とラベル
    bands = [(5.05, 1.10, "① 地図・計画", C_PLAN), (3.55, 1.10, "② 速度指令", C_CMD),
             (2.05, 1.10, "③ 歩行", C_RL), (0.65, 1.00, "環境", C_SIM)]
    for y, h, t, c in bands:
        ax.add_patch(Rectangle((1.05, y), 10.75, h, fc=c, ec="none", alpha=0.35, zorder=0))
        ax.text(1.20, y + h / 2, t, va="center", fontsize=12.5, weight="bold", color="#333", zorder=1)

    def box(x, y, w, h, text, fc, fs=12.5):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.12", fc=fc, ec=EDGE, lw=1.3, zorder=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.35, zorder=3)

    def arrow(p, q, c=A_CMD):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=18, lw=2, color=c, shrinkA=0, shrinkB=0, zorder=4))

    def line(p, q, c):
        ax.plot([p[0], q[0]], [p[1], q[1]], color=c, lw=2, solid_capstyle="round", zorder=4)

    def label(x, y, t, c="#333", ha="left", fs=10.5):
        ax.text(x, y, t, ha=ha, va="center", fontsize=fs, color=c, zorder=5)

    # ① 地図・計画
    box(2.85, 5.20, 1.70, 0.80, "ウェイポイント列\n(2 m 角の正方形)", C_PLAN, 11.5)
    box(5.20, 5.15, 3.90, 0.90, "地図による経路計画\nLiDAR で占有格子地図(5 cm 角)を描き\nA* で最短経路を探す(1 s ごと)", C_PLAN, 11)
    arrow((4.55, 5.60), (5.20, 5.60)); label(4.875, 5.83, "次の目標", ha="center", fs=9.5)
    # ② 速度指令
    box(5.20, 3.65, 1.85, 0.90, "経路追従\n経路の 0.8 m 先へ", C_CMD, 11.5)
    box(7.35, 3.65, 1.75, 0.90, "安全停止\n(反応的回避)", C_CMD, 11.5)
    arrow((6.125, 5.15), (6.125, 4.55)); label(6.27, 4.85, "経路", fs=10)
    arrow((7.05, 4.10), (7.35, 4.10))
    # ③ 歩行
    box(5.20, 2.15, 3.90, 0.90, "歩行方策(強化学習・PPO)\n速度指令に追従して 12 関節を動かす", C_RL, 11.5)
    arrow((8.225, 3.65), (8.225, 3.05)); label(8.37, 3.35, "速度指令 vx, vy, ωz\n(50 Hz)", fs=10)
    # 環境
    box(5.20, 0.75, 3.90, 0.80, "Genesis 物理シミュレータ(Go2 + 障害物)", C_SIM, 11.5)
    arrow((7.15, 2.15), (7.15, 1.55)); label(7.30, 1.85, "関節の目標角", fs=10)
    # センサ(右の列)
    box(9.95, 2.15, 1.65, 2.40, "疑似 LiDAR\n\n2D: 72 本\n3D: 72 × 16 層\n(胴体の高さの\n 点だけ使う)", C_SENS, 11)
    line((9.10, 1.15), (10.775, 1.15), A_SENS); arrow((10.775, 1.15), (10.775, 2.15), A_SENS)
    label(9.25, 0.95, "レイキャスト", A_SENS, fs=10)
    arrow((9.95, 4.10), (9.10, 4.10), A_SENS); label(9.525, 4.33, "距離", A_SENS, ha="center", fs=10)
    line((10.775, 4.55), (10.775, 5.60), A_SENS); arrow((10.775, 5.60), (9.10, 5.60), A_SENS)
    label(9.95, 5.83, "当たった点", A_SENS, ha="center", fs=10)
    # 自己位置(左の縦線)
    px = 4.85
    line((5.20, 1.15), (px, 1.15), A_POSE); line((px, 1.15), (px, 5.35), A_POSE)
    arrow((px, 5.35), (5.20, 5.35), A_POSE); arrow((px, 4.10), (5.20, 4.10), A_POSE)
    label(4.72, 2.60, "自己位置 x, y, yaw\n(真値。実機では\nSLAM の出力)", A_POSE, ha="right", fs=10)

    # 見出し・凡例
    ax.text(1.05, 6.82, "構成(最終形 v3): 実機 Go2 の「自己位置 → 地図・計画 → 速度指令 → 歩行」と同じ層構造",
            fontsize=15.5, weight="bold", va="center")
    ax.text(1.05, 6.44, "学習するのは ③ の歩行方策だけ。① ② は決定的な規則なので、失敗の原因をログから追える",
            fontsize=12, color="#444", va="center")
    for lx, c, t in [(1.20, A_CMD, "指令の流れ"), (3.00, A_SENS, "LiDAR のデータ"), (5.10, A_POSE, "自己位置")]:
        ax.add_patch(FancyArrowPatch((lx, 0.32), (lx + 0.45, 0.32), arrowstyle="-|>", mutation_scale=13, lw=2, color=c, shrinkA=0, shrinkB=0))
        ax.text(lx + 0.55, 0.32, t, va="center", fontsize=10.5)
    fig.savefig(out, dpi=100, facecolor="white"); print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="figs/arch.png"); main(ap.parse_args().out)
