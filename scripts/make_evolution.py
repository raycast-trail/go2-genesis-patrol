"""v1 → v2 → v3 の改良の系譜(3 コマ)。各段階で足した部分を強調する。"""
import argparse, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 12.8, 6.3
for cand in ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"]:
    if os.path.exists(cand):
        font_manager.fontManager.addfont(cand)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cand).get_name(); break

C_PLAN, C_CMD = "#dcf1e3", "#e3ebf7"
NEW, EDGE, BAD, GOOD = "#e07b00", "#555555", "#b03a2e", "#1e7b45"


def main(out):
    fig = plt.figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

    def box(cx, y, w, h, text, fc, new=False, fs=11):
        ax.add_patch(FancyBboxPatch((cx - w / 2, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.10",
                                    fc=fc, ec=NEW if new else EDGE, lw=3.0 if new else 1.2))
        ax.text(cx, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.35)
        if new:
            ax.text(cx - w / 2 + 0.06, y + h + 0.03, "追加", fontsize=9.5, color="white", weight="bold", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.18", fc=NEW, ec="none"))

    def arrow(cx, y0, y1):
        ax.add_patch(FancyArrowPatch((cx, y0), (cx, y1), arrowstyle="-|>", mutation_scale=16, lw=1.8, color="#333", shrinkA=0, shrinkB=0))

    BW = 3.3
    rows = dict(plan=(4.55, 0.70), foll=(3.55, 0.62), avoid=(2.35, 0.82), commit=(1.45, 0.62))
    panels = [
        (2.25, "v1  反応的回避", [
            ("foll", "経路追従(ウェイポイントへ)", C_CMD, False),
            ("avoid", "反応的回避\n進路 ±0.4 m に障害物 → 減速・停止、\n近い障害物の反対側へ旋回", C_CMD, False)],
         ("× 正面の障害物の前で「止まる → 曲がる →\n   戻る」を繰り返して時間切れ(振動)", BAD), "成功 91%・所要 31.6 s・経路効率 1.00"),
        (6.40, "v2  + コミット区間", [
            ("foll", "経路追従(ウェイポイントへ)", C_CMD, False),
            ("avoid", "反応的回避(v1 と同じ)", C_CMD, False),
            ("commit", "コミット区間\n曲がる向きを 2 s 固定 → 空いたら 1 s 直進", C_CMD, True)],
         ("△ 振動は消えて抜けられるが、\n   易しい配置でも遠回りする", "#9a6a00"), "成功 96%・所要 31.7 s・経路効率 0.81"),
        (10.55, "v3  + 地図による経路計画", [
            ("plan", "地図による経路計画\nLiDAR で地図を描き、A* で最短経路", C_PLAN, True),
            ("foll", "経路追従(経路の 0.8 m 先へ)", C_CMD, False),
            ("avoid", "安全停止(v1 の反応的回避を\n下層に残す)", C_CMD, False)],
         ("○ 障害物の向こう側まで見て先回りする。\n   速さと確実さを両立", GOOD), "成功 100%・所要 24.2 s・経路効率 1.05"),
    ]
    for cx, title, items, (msg, mc), res in panels:
        ax.text(cx, 5.85, title, ha="center", va="center", fontsize=14, weight="bold")
        present = {k for k, *_ in items}
        if "plan" not in present:
            ax.text(cx, rows["plan"][0] + rows["plan"][1] / 2, "(地図なし。目の前しか見ない)", ha="center", va="center",
                    fontsize=10, color="#999")
        for k, t, fc, new in items:
            y, h = rows[k]
            box(cx, y, BW, h, t, fc, new)
        order = [k for k in ["plan", "foll", "avoid", "commit"] if k in present]
        for a, b in zip(order, order[1:]):
            arrow(cx, rows[a][0], rows[b][0] + rows[b][1])
        last = order[-1]
        arrow(cx, rows[last][0], 1.22)
        ax.text(cx + 0.12, 1.30 if last != "commit" else 1.29, "", fontsize=9)
        ax.text(cx, 1.10, "↓ 速度指令 → 歩行方策", ha="center", va="top", fontsize=9.5, color="#555")
        ax.text(cx - BW / 2, 0.72, msg, ha="left", va="center", fontsize=10.5, color=mc, linespacing=1.3)
        ax.text(cx - BW / 2, 0.18, res, ha="left", va="center", fontsize=10.5, weight="bold")
    for xs in (4.32, 8.47):
        ax.plot([xs, xs], [0.1, 6.1], color="#dddddd", lw=1)
    fig.savefig(out, dpi=100, facecolor="white"); print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="figs/evolution.png"); main(ap.parse_args().out)
