"""
scripts/make_video.py — 提出動画(1〜3 分、1280×720、30 fps、H.264、音声なし)を ffmpeg で組み立てる。

ショットリスト(tasks/08_video.md)に従い、カード(PNG)・図(PNG)・動画クリップ(必要なら 2 倍速 + 帯テロップ)を
個別に 1280×720 / 30 fps の中間クリップにしてから concat する。2 倍速の区間は帯に「2倍速」を入れる。

使い方(リポジトリ直下で): python scripts/make_video.py [--out videos/final/PAI最終課題_3164.mp4]
必要な素材: figs/*.png, figs/cards/*.png(scripts/make_figs.py, make_cards.py)、videos/raw/*.mp4(採用回)、
            videos/raw/foxglove_seed10.mov(無ければ results/t06_foxglove_seed10.png を 4 s の静止カットで代用)、
            videos/raw/foxglove_3d_seed103.mp4(T14: Foxglove の 3D 点群。無ければショット 12f を飛ばす)
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile

FPS = 30
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]
SCALE = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=white"


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def still(png, dur, out):
    """静止画を dur 秒の動画に"""
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", png, "-vf", SCALE + ",format=yuv420p"] + ENC + [out])


def side_by_side(left_png, right_png, dur, out):
    """左にカード、右に図(各 640×720 に縮小)"""
    vf = ("[0:v]scale=640:720:force_original_aspect_ratio=decrease,pad=640:720:(ow-iw)/2:(oh-ih)/2:color=0x141820[l];"
          "[1:v]scale=640:720:force_original_aspect_ratio=decrease,pad=640:720:(ow-iw)/2:(oh-ih)/2:color=white[r];"
          "[l][r]hstack=inputs=2,format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", left_png,
         "-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", right_png, "-filter_complex", vf] + ENC + [out])


def clip(src, out, start=0.0, dur=None, speed=1.0, banner=None):
    """動画クリップ。speed=2 で 2 倍速(setpts=0.5*PTS)、banner(PNG, 1280×90)を上に重ねる"""
    vf = [SCALE]
    if speed != 1.0:
        vf.append(f"setpts={1.0 / speed:.4f}*PTS")
    vf.append(f"fps={FPS}")
    cmd = ["ffmpeg", "-y", "-ss", str(start)]
    if dur is not None:
        cmd += ["-t", str(dur * speed)]       # 入力側の長さ(倍速前)。-i の前に置いて 1 つ目の入力に効かせる
    cmd += ["-i", src]
    if banner:
        cmd += ["-i", banner, "-filter_complex", f"[0:v]{','.join(vf)}[v];[v][1:v]overlay=0:0,format=yuv420p"]
    else:
        cmd += ["-vf", ",".join(vf) + ",format=yuv420p"]
    run(cmd + ENC + [out])


def hstack_clips(a, b, out, dur, speed=2.0, banner=None, start_a=0.0, start_b=0.0):
    """2 本の動画を左右に並べる(各 640×360 に縮小して中央配置)"""
    vf = (f"[0:v]setpts={1.0 / speed:.4f}*PTS,scale=640:360[a];[1:v]setpts={1.0 / speed:.4f}*PTS,scale=640:360[b];"
          f"[a][b]hstack=inputs=2,pad=1280:720:0:180:color=0x141820,fps={FPS}[v]")
    cmd = ["ffmpeg", "-y", "-ss", str(start_a), "-t", str(dur * speed), "-i", a, "-ss", str(start_b), "-t", str(dur * speed), "-i", b]
    if banner:
        cmd += ["-i", banner, "-filter_complex", vf + ";[v][2:v]overlay=0:0,format=yuv420p"]
    else:
        cmd += ["-filter_complex", vf + ";[v]format=yuv420p"]
    run(cmd + ENC + [out])


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate",
                        "-of", "json", path], capture_output=True, text=True)
    j = json.loads(p.stdout)
    return float(j["format"]["duration"]), j["streams"][0]["width"], j["streams"][0]["height"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="videos/final/PAI最終課題_3164.mp4")
    parser.add_argument("--raw", default="videos/raw")
    parser.add_argument("--foxglove", default="videos/raw/foxglove_seed10.mov")
    parser.add_argument("--foxglove3d", default="videos/raw/foxglove_3d_seed103.mp4", help="T14: Foxglove 3D 点群の収録(整形済み)")
    parser.add_argument("--v1-seed28-start", type=float, default=8.0, help="v1 seed28 の振動区間の開始秒")
    parser.add_argument("--v2-seed28-start", type=float, default=8.0)
    parser.add_argument("--v3-seed28-start", type=float, default=9.7, help="v3 seed28: Box 最接近(12.7 s)の 3 s 前")
    args = parser.parse_args()
    R = args.raw
    C = "figs/cards"
    tmp = tempfile.mkdtemp(prefix="mkvideo_")
    seq = []
    o = lambda n: os.path.join(tmp, f"{len(seq):02d}_{n}.mp4")
    p = o("C0"); still(f"{C}/C0.png", 5, p); seq.append(("1 C0 タイトル", p))
    p = o("arch"); still("figs/arch.png", 6, p); seq.append(("2 構成図", p))
    p = o("C1"); side_by_side(f"{C}/C1h.png", "figs/train_curve_half.png", 8, p); seq.append(("3 C1 + 学習曲線", p))
    p = o("script"); clip("videos/t01_script.mp4", p, start=0, dur=7, speed=2.0, banner=f"{C}/B4.png"); seq.append(("4 台本(2 倍速)", p))
    p = o("C2"); side_by_side(f"{C}/C2h.png", "results/t01_square_traj_compare.png", 8, p); seq.append(("5 C2 + 軌跡比較", p))
    p = o("follow"); clip(f"{R}/v2_seed10_follow.mp4", p, start=0, dur=12, speed=1.0, banner=f"{C}/B6.png"); seq.append(("6 seed10 追従(等速)", p))
    p = o("C3"); still(f"{C}/C3.png", 4, p); seq.append(("7 C3", p))
    p = o("close"); clip(f"{R}/v2_seed10_close.mp4", p, start=0, dur=12, speed=2.0, banner=f"{C}/B8.png"); seq.append(("8 seed10 俯瞰(2 倍速)", p))
    if os.path.exists(args.foxglove):
        p = o("fox"); clip(args.foxglove, p, start=2, dur=12, speed=2.0, banner=f"{C}/B9s.png" if os.path.exists(f"{C}/B9s.png") else f"{C}/B9.png")
        seq.append(("9 Foxglove 画面収録(2 倍速)", p))
    else:
        p = o("fox"); clip_png = "figs/foxglove_crop.png" if os.path.exists("figs/foxglove_crop.png") else "results/t06_foxglove_seed10.png"
        still(clip_png, 4, p + ".tmp.mp4"); clip(p + ".tmp.mp4", p, banner=f"{C}/B9.png"); os.remove(p + ".tmp.mp4")
        seq.append(("9 Foxglove 静止画(4 s、収録なしの代替)", p))
    p = o("v1_28"); clip(f"{R}/v1_seed28_close.mp4", p, start=args.v1_seed28_start, dur=10, speed=2.0, banner=f"{C}/B10a.png"); seq.append(("10a v1 seed28(2 倍速)", p))
    p = o("v2_28"); clip(f"{R}/v2_seed28_close.mp4", p, start=args.v2_seed28_start, dur=10, speed=2.0, banner=f"{C}/B10b.png"); seq.append(("10b v2 seed28(2 倍速)", p))
    if os.path.exists(f"{R}/v3_seed28_close.mp4"):
        p = o("v3_28"); clip(f"{R}/v3_seed28_close.mp4", p, start=args.v3_seed28_start, dur=10, speed=2.0, banner=f"{C}/B10c.png"); seq.append(("10c v3 seed28(2 倍速)", p))
    if os.path.exists("figs/traj_seed28.png"):
        p = o("traj28"); still("figs/traj_seed28.png", 6, p + ".tmp.mp4"); clip(p + ".tmp.mp4", p, banner=f"{C}/B10d.png"); os.remove(p + ".tmp.mp4")
        seq.append(("10d seed28 軌跡図(静止)", p))
    p = o("C4"); side_by_side(f"{C}/C4h.png", "figs/result_50_half.png", 10, p); seq.append(("11 C4 + 結果(4 条件)", p))
    p = o("C5"); still(f"{C}/C5.png", 7, p); seq.append(("12 C5", p))
    if os.path.exists(f"{R}/t12_3d_seed103_close.mp4") and os.path.exists(f"{C}/C7.png"):     # T13: 3D LiDAR のショット
        p = o("C7"); still(f"{C}/C7.png", 5, p); seq.append(("12b C7 3D LiDAR", p))
        p = o("s103_2d"); clip(f"{R}/t12_2d_seed103_close.mp4", p, start=0, dur=6, speed=1.0, banner=f"{C}/B12c.png"); seq.append(("12c 2D seed103(等速、転倒まで 6 s)", p))
        p = o("s103_3d"); clip(f"{R}/t12_3d_seed103_close.mp4", p, start=0, dur=10, speed=2.0, banner=f"{C}/B12d.png"); seq.append(("12d 3D seed103(2 倍速)", p))
        if os.path.exists(args.foxglove3d):     # T14: 素材が無ければ飛ばす(クリーンクローン)
            d3 = probe(args.foxglove3d)[0]
            p = o("fox3d"); clip(args.foxglove3d, p, start=0, dur=d3 / 2.0, speed=2.0, banner=f"{C}/B12f.png"); seq.append(("12f Foxglove 3D 点群(2 倍速)", p))
        p = o("C8"); side_by_side(f"{C}/C8h.png", "figs/result_3d_half.png", 7, p); seq.append(("12e C8h + 3D 結果", p))
    p = o("C6"); still(f"{C}/C6.png", 8, p); seq.append(("13 C6 まとめ", p))

    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for _, path in seq:
            f.write(f"file '{os.path.abspath(path)}'\n")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart", "-an", args.out])
    total = 0.0
    print("| # | ショット | 長さ [s] |\n|---|---|---|")
    for name, path in seq:
        d, w, h = probe(path)
        total += d
        print(f"| {name} | {d:.1f} |")
    d, w, h = probe(args.out)
    print(f"\n[make_video] wrote {args.out}: {d:.1f} s (sum of shots {total:.1f} s), {w}x{h}, {os.path.getsize(args.out) / 1e6:.1f} MB")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
