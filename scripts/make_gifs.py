"""
scripts/make_gifs.py — README 用のアニメーション GIF とソーシャルプレビュー画像を作る(T15)。

  docs/media/hero.gif              Genesis 俯瞰(左)と Foxglove の 3D 点群(右)を同期して横並び、2 倍速、末尾 1 s 静止してループ
  docs/media/v1_v2_v3_seed28.gif   seed 28 の v1 / v2 / v3 を 3 分割、2 倍速、v3 の完走 + 1 s で切る
  docs/media/social_preview.png    1280×640(GitHub の Social preview 用)

帯の文字は PIL で PNG にしてから ffmpeg で重ねる(ffmpeg の drawtext に依存しない)。GIF は palettegen / paletteuse(bayer)。

使い方(リポジトリ直下で): python scripts/make_gifs.py [--fps 12] [--width 960] [--fox-stretch 1.0]
必要な素材: videos/raw/t12_3d_seed103_close.mp4, videos/raw/foxglove_3d_seed103.mp4(T14), videos/raw/v{1,2,3}_seed28_close.mp4,
            videos/raw/v3_seed28_close_log.csv(完走時刻), results/t14_foxglove3d_seed103.png
"""

import argparse
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

BG = (20, 24, 32)                      # 0x141820(動画のパディングと同じ)
FG, SUB, ACC = (240, 240, 236), (170, 174, 180), (235, 104, 52)
FONT = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD_INDEX = 1                    # Helvetica.ttc の Bold
ARROW_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"     # Helvetica に → が無いので矢印だけこれで描く
OUT = "docs/media"


def font(size, bold=False):
    return ImageFont.truetype(FONT, size, index=FONT_BOLD_INDEX if bold else 0)


def text_arrow(d, xy, text, size, fill):
    """太字の 1 行。「→」だけ ARROW_FONT で描く"""
    x, y = xy
    f, fa = font(size, True), ImageFont.truetype(ARROW_FONT, size)
    for i, part in enumerate(text.split("→")):
        if i:
            d.text((x, y), " → ", font=fa, fill=fill)
            x += d.textlength(" → ", font=fa)
        d.text((x, y), part.strip() if i else part.rstrip(), font=f, fill=fill)
        x += d.textlength(part.strip() if i else part.rstrip(), font=f)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def band(path, w, h, labels, size, bold=True, color=FG, pad=16):
    """背景色の帯に文字を置く。labels = [(x0, text), ...]、x0 は各区画の左端(文字は x0 + pad から)"""
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    f = font(size, bold)
    for x0, text in labels:
        top = d.textbbox((0, 0), text, font=f)
        d.text((x0 + pad, (h - (top[3] - top[1])) // 2 - top[1]), text, font=f, fill=color)
    im.save(path)


def to_gif(src_mp4, out, fps, width):
    """palettegen / paletteuse で GIF に(ループ無限)"""
    flt = f"fps={fps},scale={width}:-1:flags=lanczos"
    pal = out + ".palette.png"
    run(["ffmpeg", "-y", "-i", src_mp4, "-vf", f"{flt},palettegen=max_colors=128:stats_mode=diff", pal])
    run(["ffmpeg", "-y", "-i", src_mp4, "-i", pal, "-lavfi", f"{flt}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
         "-loop", "0", out])
    os.remove(pal)


def probe_dur(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def last_t(log_csv):
    with open(log_csv) as f:
        return float(f.readlines()[-1].split(",")[0])


def hero(tmp, args):
    """左: Genesis(1280×720 → 480×270)、右: Foxglove(左右のパディングを除き、上下を 612 px に切って 480×270)。
    両方の先頭を t = 0 に揃え、Foxglove 側は --fox-stretch 倍に伸縮(既定 1.0 = 伸縮なし)"""
    W, H, TOP, BOT = 480, 270, 30, 22
    sim, fox = "videos/raw/t12_3d_seed103_close.mp4", "videos/raw/foxglove_3d_seed103.mp4"
    top, bot = os.path.join(tmp, "hero_top.png"), os.path.join(tmp, "hero_bot.png")
    band(top, 2 * W, TOP, [(0, "Simulation (Genesis)"), (W, "3D LiDAR point cloud (Foxglove)")], 17)
    band(bot, 2 * W, BOT, [(0, "Unitree Go2 · RL locomotion + LiDAR navigation · 2× speed")], 13, bold=False, color=SUB)
    dur = probe_dur(sim) / 2.0                       # 2 倍速での長さ(完走まで)
    f = 0.5 * args.fox_stretch
    vf = (f"[0:v]setpts=0.5*PTS,scale={W}:{H},fps=30,trim=duration={dur:.3f},tpad=stop_mode=clone:stop_duration=1[a];"
          f"[1:v]crop=1088:612:96:54,setpts={f:.5f}*PTS,scale={W}:{H},fps=30,tpad=stop_mode=clone:stop_duration=5,"
          f"trim=duration={dur + 1:.3f}[b];"
          f"[a][b]hstack=inputs=2[m];[2:v][m][3:v]vstack=inputs=3,format=yuv420p")
    mp4 = os.path.join(tmp, "hero.mp4")
    run(["ffmpeg", "-y", "-i", sim, "-i", fox, "-loop", "1", "-i", top, "-loop", "1", "-i", bot,
         "-filter_complex", vf, "-t", f"{dur + 1:.3f}", "-c:v", "libx264", "-crf", "16", "-an", mp4])
    out = os.path.join(OUT, "hero.gif")
    to_gif(mp4, out, args.fps, args.width)
    return out, dur + 1


def compare(tmp, args):
    """seed 28 の v1 / v2 / v3 を 320×180 で横並び。先頭 t = 0 で揃え、v3 の完走時刻 + 1 s(シム時間)で切る"""
    W, H, TOP, BOT = 320, 180, 26, 20
    srcs = [f"videos/raw/{v}_seed28_close.mp4" for v in ("v1", "v2", "v3")]
    t_end = (last_t("videos/raw/v3_seed28_close_log.csv") + 1.0) / 2.0       # 2 倍速での長さ
    top, bot = os.path.join(tmp, "cmp_top.png"), os.path.join(tmp, "cmp_bot.png")
    band(top, 3 * W, TOP, [(0, "v1 reactive"), (W, "v2 + commit"), (2 * W, "v3 map + A*")], 15, pad=12)
    band(bot, 3 * W, BOT, [(0, "Same scene (seed 28) · 2× speed")], 12, bold=False, color=SUB, pad=12)
    parts = [f"[{i}:v]setpts=0.5*PTS,scale={W}:{H},fps=30,tpad=stop_mode=clone:stop_duration=5,trim=duration={t_end:.3f}[p{i}]"
             for i in range(3)]
    vf = ";".join(parts) + ";[p0][p1][p2]hstack=inputs=3[m];[3:v][m][4:v]vstack=inputs=3,format=yuv420p"
    mp4 = os.path.join(tmp, "cmp.mp4")
    cmd = ["ffmpeg", "-y"]
    for s in srcs:
        cmd += ["-i", s]
    cmd += ["-loop", "1", "-i", top, "-loop", "1", "-i", bot, "-filter_complex", vf, "-t", f"{t_end:.3f}",
            "-c:v", "libx264", "-crf", "16", "-an", mp4]
    run(cmd)
    out = os.path.join(OUT, "v1_v2_v3_seed28.gif")
    to_gif(mp4, out, args.fps, 3 * W)
    return out, t_end


def social_preview():
    """1280×640。左 55% に Foxglove の 3D 点群、右にタイトル・サブ・数値(results/eval_50, eval_3d の summary.md から)"""
    W, H, M = 1280, 640, 60
    im = Image.new("RGB", (W, H), BG)
    pic = Image.open("results/t14_foxglove3d_seed103.png").convert("RGB")
    box_w = int(W * 0.55) - M                       # 左余白 60 px から 55% の位置まで
    s = min(box_w / pic.width, (H - 2 * M) / pic.height)
    pic = pic.resize((int(pic.width * s), int(pic.height * s)), Image.LANCZOS)
    mask = Image.new("L", pic.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pic.width - 1, pic.height - 1], radius=16, fill=255)
    im.paste(pic, (M, (H - pic.height) // 2), mask)
    d = ImageDraw.Draw(im)
    x = int(W * 0.55) + 40
    d.rectangle([x, 178, x + 6, 248], fill=ACC)
    d.text((x + 24, 170), "Go2 Patrol", font=font(46, True), fill=FG)
    d.text((x + 24, 222), "in Genesis", font=font(32, True), fill=FG)
    d.text((x, 290), "RL locomotion · 3D LiDAR ·", font=font(24), fill=SUB)
    d.text((x, 322), "occupancy map + A*", font=font(24), fill=SUB)
    text_arrow(d, (x, 392), "45 scenes: success 9% → 100%", 25, FG)
    text_arrow(d, (x, 432), "Low obstacles: 2D 3% → 3D 100%", 25, FG)
    out = os.path.join(OUT, "social_preview.png")
    im.save(out)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=960, help="hero.gif の幅(8 MB を超えたら 800)")
    parser.add_argument("--fox-stretch", type=float, default=1.0,
                        help="Foxglove 側の時間伸縮率(末尾の完走時刻が 0.5 s 以上ずれる場合に シム長 / 収録長)")
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="mkgif_")
    print("| ファイル | 長さ [s] | fps | 大きさ | MB |\n|---|---|---|---|---|")
    for out, dur in (hero(tmp, args), compare(tmp, args)):
        w, h = Image.open(out).size
        print(f"| {out} | {dur:.2f} | {args.fps} | {w}×{h} | {os.path.getsize(out) / 1e6:.2f} |")
    out = social_preview()
    print(f"| {out} | — | — | {Image.open(out).size[0]}×{Image.open(out).size[1]} | {os.path.getsize(out) / 1e6:.2f} |")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
