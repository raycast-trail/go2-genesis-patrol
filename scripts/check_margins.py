"""
scripts/check_margins.py — figs/cards/*.png の左右の余白を検査する(T10。T14 の帯 B12f も glob で対象)。
背景色(カード: BG、帯: 半透明の帯色)と左のアクセント帯(x < 20)を除いた描画ピクセルの x の最小・最大から、
右端の余白 = 幅 − max_x − 1 が 100 px 以上、左端の描画が x ≤ 85(文字は x = 80 から)であることを全ファイルで確認して表にする。\n--extra の図(既定 figs/arch.png)は左右とも余白 ≥ 100 px を要求する。

使い方: python scripts/check_margins.py [--min-margin 100]
"""

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

BG = (20, 24, 32)


def measure(path):
    """背景色は右下のピクセル(カード: BG、帯: 半透明の帯色、白背景の図: 白)から取る"""
    im = Image.open(path)
    w, h = im.size
    a = np.asarray(im.convert("RGBA")).astype(int)
    rgb, alpha = a[:, :, :3], a[:, :, 3]
    bg = rgb[h - 1, w - 1]
    drawn = (alpha > 0) & (np.abs(rgb - bg).sum(axis=2) > 30)
    drawn[:, :20] = False                     # 左のアクセント帯を除く
    cols = np.nonzero(drawn.any(axis=0))[0]
    if len(cols) == 0:
        return w, h, None, None
    return w, h, int(cols.min()), int(cols.max())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="figs/cards")
    parser.add_argument("--min-margin", type=int, default=100)
    parser.add_argument("--extra", nargs="*", default=["figs/arch.png"], help="追加で検査する図(左右とも余白 ≥ min-margin)")
    args = parser.parse_args()
    rows, ok_all = [], True
    print("| ファイル | 幅 | 描画 x 最小 | 描画 x 最大 | 左余白 [px] | 右余白 [px] | 判定 |")
    print("|---|---|---|---|---|---|---|")
    files = [(p, "card") for p in sorted(glob.glob(os.path.join(args.dir, "*.png")))]
    files += [(p, "fig") for p in args.extra if os.path.exists(p)]
    for path, kind in files:
        w, h, x0, x1 = measure(path)
        right = w - x1 - 1 if x1 is not None else w
        left = x0 if x0 is not None else w
        if kind == "card":
            ok = right >= args.min_margin and (x0 is None or x0 <= 85)   # 文字は x=80 から(グリフの側面余白で数 px 右に出る)
        else:
            ok = right >= args.min_margin and left >= args.min_margin
        ok_all &= ok
        print(f"| {os.path.basename(path)} | {w} | {x0} | {x1} | {left} | {right} | {'OK' if ok else 'NG'} |")
    print(f"\n[check_margins] {'all OK' if ok_all else 'NG found'} (min right margin {args.min_margin} px)")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
