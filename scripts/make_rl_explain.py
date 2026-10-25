"""強化学習(PPO)による歩行方策の学習ループと、方策ネットワークの入出力。値は checkpoints/go2-patrol/cfgs.pkl と go2_env.py から。"""
import argparse, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 13.0, 6.2
for cand in ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"]:
    if os.path.exists(cand):
        font_manager.fontManager.addfont(cand)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cand).get_name(); break

C_SIM, C_RL, C_DATA, C_UPD, C_IN, C_OUT = "#f0f0f0", "#ebe2f6", "#fff1c9", "#dcf1e3", "#e3ebf7", "#fbdfd6"
EDGE = "#444444"


def main(out):
    fig = plt.figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

    def box(x, y, w, h, t, fc, fs=11, weight="normal", ha="center"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.10", fc=fc, ec=EDGE, lw=1.2))
        tx = x + w / 2 if ha == "center" else x + 0.15
        ax.text(tx, y + h / 2, t, ha=ha, va="center", fontsize=fs, linespacing=1.35, weight=weight)

    def arrow(p, q, c="#333", text=None, tx=None, ty=None, ha="left", rad=0.0):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, lw=1.8, color=c, shrinkA=0, shrinkB=0,
                                     connectionstyle=f"arc3,rad={rad}"))
        if text:
            ax.text(tx, ty, text, ha=ha, va="center", fontsize=10, color=c)

    # ---------------- 左: 学習ループ ----------------
    ax.text(0.30, 5.88, "(a) 学習: シミュレーションで試行錯誤し、報酬が増えるように方策を直す", fontsize=13, weight="bold", va="center")
    box(0.40, 3.85, 2.45, 1.20, "シミュレーション\n4096 体の Go2 を\n同時に動かす(Metal)", C_SIM, 11)
    box(4.35, 3.85, 2.25, 1.20, "方策ネットワーク\n(いまの歩き方)", C_RL, 11.5)
    arrow((2.85, 4.75), (4.35, 4.75), text="観測\n(45 個の数値)", tx=3.60, ty=5.17, ha="center")
    arrow((4.35, 4.15), (2.85, 4.15), text="行動\n(12 関節の目標角)", tx=3.60, ty=3.70, ha="center")
    box(0.40, 1.95, 2.45, 1.15, "経験データ\n4096 体 × 24 ステップ\n= 約 9.8 万組(観測・行動・報酬)", C_DATA, 10.5)
    arrow((1.625, 3.85), (1.625, 3.10), text="報酬(指令どおりに\n歩けたか)", tx=1.78, ty=3.48)
    box(4.35, 1.95, 2.25, 1.15, "PPO で方策を更新\n価値ネットワークで\n行動の良し悪しを見積もる", C_UPD, 10.5)
    arrow((2.85, 2.52), (4.35, 2.52))
    arrow((5.475, 3.10), (5.475, 3.85), text="少しだけ\n直す", tx=5.62, ty=3.48)
    ax.text(0.40, 1.45, "この 1 周を 300 回(M1 Max で約 9 分)。", fontsize=10.5, va="center")
    ax.text(0.40, 1.08, "合計 約 2,950 万ステップ = 1 体なら約 164 時間分の歩行経験", fontsize=10.5, va="center")
    ax.text(0.40, 0.62, "倒れたら(前後・左右に 10° 超)その 1 体だけやり直し。\n速度指令は 4 秒ごとにランダムに変わる", fontsize=10, va="center", color="#555")

    # 区切り
    ax.plot([6.85, 6.85], [0.25, 6.05], color="#dddddd", lw=1)

    # ---------------- 右: 方策ネットワークの入出力 ----------------
    ax.text(7.05, 5.88, "(b) 推論: 巡回中は学習済みの方策を 50 Hz で呼ぶ", fontsize=13, weight="bold", va="center")
    inputs = ["胴体の角速度 3", "重力の向き(傾き)3", "速度指令 vx, vy, ωz 3", "関節角(標準姿勢との差)12",
              "関節の角速度 12", "前回の行動 12"]
    y0 = 5.20
    for i, t in enumerate(inputs):
        fc = "#c9d9f2" if "速度指令" in t else C_IN
        box(7.05, y0 - i * 0.55, 2.35, 0.42, t, fc, 9.8, ha="left")
    ax.text(8.22, y0 - 6 * 0.55 + 0.22, "入力 計 45 個", ha="center", fontsize=10, weight="bold", va="center")
    ax.text(8.22, y0 - 6 * 0.55 - 0.13, "(色の濃い 3 個を\nナビゲーション層が書き換える)", ha="center", fontsize=9, va="top", color="#2f5597")
    # MLP
    box(9.75, 2.45, 1.30, 2.70, "方策\nネットワーク\n\n全結合 3 層\n512 → 256\n→ 128\n(約 19 万\nパラメータ)", C_RL, 10)
    for i in range(6):
        y = y0 - i * 0.55 + 0.21
        ax.annotate("", xy=(9.75, 3.80), xytext=(9.40, y), arrowprops=dict(arrowstyle="-", color="#999", lw=0.8))
    box(11.35, 3.45, 1.45, 0.72, "行動 12 個\n(目標角の補正)", C_OUT, 9.8)
    arrow((11.05, 3.80), (11.35, 3.80))
    box(11.35, 2.20, 1.45, 0.82, "× 0.25 + 標準姿勢\n→ PD 制御\n→ 関節トルク", C_SIM, 9.3)
    arrow((12.075, 3.45), (12.075, 3.02))
    ax.text(9.75, 1.70, "胴体の速度は入力にない。関節の動き\nと傾きから自分の歩き方を推し量り、\n指令に合わせる",
            fontsize=9.8, va="center", color="#555")
    ax.text(9.75, 0.75, "学習後は重みを固定。巡回中は 20 ms\nごとに入力を作って 1 回通すだけ(推論)",
            fontsize=9.8, va="center", color="#555")
    fig.savefig(out, dpi=100, facecolor="white"); print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="figs/rl_explain.png"); main(ap.parse_args().out)
