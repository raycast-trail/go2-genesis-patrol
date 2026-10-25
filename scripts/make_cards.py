"""
scripts/make_cards.py — 提出動画のテロップカード(1280×720 PNG)を PIL で作る。氏名・所属・メールは入れない。

使い方: python scripts/make_cards.py   → figs/cards/C0.png ... C6.png、および動画クリップ用の帯ラベル
"""

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
OUT = "figs/cards"
os.makedirs(OUT, exist_ok=True)
BG, FG, SUB, ACC = (20, 24, 32), (240, 240, 236), (190, 190, 184), (235, 104, 52)


def font(size):
    return ImageFont.truetype(FONT, size)


MARGIN = 100          # 左右の余白の下限 [px](T10)


def card(name, title, lines=(), footer=None, title_size=54, line_size=36, accent_first=False):
    """1280×720 のカード。幅 W − 80 − MARGIN で折り返し、縦に収まらなければ文字を 2 px ずつ小さくする"""
    width = W - 80 - MARGIN
    ts, ls = title_size, line_size
    while True:
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 14, H], fill=ACC)
        y = 110
        for t in title.split("\n"):
            for tt in wrap(d, t, font(ts), width):
                d.text((80, y), tt, font=font(ts), fill=FG)
                y += ts + 18
        y += 30
        for i, t in enumerate(lines):
            col = ACC if (accent_first and i == 0) else SUB
            for tt in wrap(d, t, font(ls), width):
                d.text((80, y), tt, font=font(ls), fill=col)
                y += ls + 22
        if footer:
            d.text((80, H - 80), footer, font=font(26), fill=SUB)
        if y <= H - 120 or ts <= 24:
            break
        ts, ls = ts - 2, ls - 2
    path = os.path.join(OUT, f"{name}.png")
    im.save(path)
    print("wrote", path, f"(title {ts}px, lines {ls}px)")


def wrap(d, text, f, width):
    """幅 width に収まるように文字単位で折り返す(日本語用)"""
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def half_card(name, title, lines=(), title_size=38, line_size=27, accent_first=False):
    """左右 2 分割用の 640×720 カード(右に図を置く)"""
    HW = 640
    im = Image.new("RGB", (HW, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12, H], fill=ACC)
    y = 90
    for t in wrap(d, title, font(title_size), HW - 40 - MARGIN):
        d.text((40, y), t, font=font(title_size), fill=FG)
        y += title_size + 12
    y += 26
    for i, t in enumerate(lines):
        col = ACC if (accent_first and i == 0) else SUB
        for tt in wrap(d, t, font(line_size), HW - 40 - MARGIN):
            d.text((40, y), tt, font=font(line_size), fill=col)
            y += line_size + 10
        y += 12
    path = os.path.join(OUT, f"{name}.png")
    im.save(path)
    print("wrote", path)


def banner(name, text, speed=False):
    """動画の上に重ねる帯(1280×90、半透明)。1 行。右端の余白は MARGIN 以上(2倍速バッジも W − MARGIN まで)。
    文字は 34 px から縮め、22 px でも収まらなければエラー(文を短くする)"""
    im = Image.new("RGBA", (W, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 90], fill=(20, 24, 32, 200))
    d.rectangle([0, 0, 14, 90], fill=ACC + (255,))
    badge_x0 = W - MARGIN - 160
    limit = (badge_x0 - 40) if speed else (W - MARGIN - 20)      # 文字の右端の上限
    size = 34
    while size > 22 and 40 + d.textlength(text, font=font(size)) > limit:
        size -= 1
    if 40 + d.textlength(text, font=font(size)) > limit:
        raise ValueError(f"banner {name}: text too long even at {size}px: {text}")
    d.text((40, 45 - size // 2 - 2), text, font=font(size), fill=FG)
    if speed:
        d.rounded_rectangle([badge_x0, 20, W - MARGIN - 1, 70], radius=10, fill=ACC + (255,))   # PIL は終端座標を含む
        d.text((badge_x0 + 20, 26), "2倍速", font=font(32), fill=FG)
    path = os.path.join(OUT, f"{name}.png")
    im.save(path)
    print("wrote", path, f"({size}px)")


card("C0", "Go2 の RL 歩行 + LiDAR 巡回・障害物回避\n(Genesis シミュレーション)",
     ["PAI最終課題_3164", "音声なし・テロップで説明。一部 2 倍速(右上に表示)"], title_size=50, line_size=34, accent_first=True)
card("C1", "1. 歩行方策を強化学習で獲得",
     ["4096 体並列・300 イテレーション・約 9 分(M1 Max, Metal)", "PPO(rsl-rl)、報酬: 速度指令への追従 + 姿勢の安定",
      "最終: エピソード長 991 / 1000、lin_vel 追従 0.97"])
card("C2", "2. 速度指令への追従",
     ["既定例題の方策は「前進 0.5 m/s」しか学んでいない → 旋回できず直進", "指令範囲を広げて再学習: vx 0〜0.8 m/s、ωz ±0.8 rad/s",
      "→ 正方形の巡回経路を 16 s で 1 周"])
card("C3", "3. 疑似 LiDAR(72 本)で反応的に回避",
     ["Genesis の Raycaster を胴体に取付(5° 刻み、5 m)。地面除去あり", "進路幅 ±0.4 m の回廊に入った障害物だけに反応し、減速・旋回",
      "地図なし・障害物位置は未使用(実機の LiDAR 回避と同じ入力)"])
card("C4", "4. 45 配置で定量評価(障害物 3〜5 個を乱数配置)",
     ["回避なし 9% → v1 91% → v2 96% → v3 100%(成功率)", "接触 91% → 0%(p < 0.0001)",
      "既定方策(前進のみ)は全条件で成功 0%"], accent_first=True)
card("C5", "5. 比較: 地図なし(v1・v2)と地図あり(v3)",
     ["v1 反応的回避: 正面の障害物で振動(成功 91%)", "v2 + コミット区間: 抜けるが遠回り(96%、経路効率 0.81)",
      "v3 地図による経路計画: 速さと確実さを両立", "(100%、所要 24.2 s、経路効率 1.05)"])
card("C6", "まとめ",
     ["実機 Go2 の 自己位置 → 地図・計画 → 速度指令 → 歩行 と同じ 3 層構造をシムで再現(2D → 3D LiDAR)",
      "限界: 真の姿勢を使用(SLAM なし)、静止障害物、非決定性", "コード: github.com/raycast-trail/go2-genesis-patrol"], line_size=33)
card("C7", "6. 3D LiDAR: 2D では見えない障害物",
     ["低い箱(0.15 m)と テーブルの天板(0.32〜0.36 m)は", "センサ面(0.44 m)の 2D スキャンに映らない",
      "3D(72 × 16 層、±30°)→ 胴体の高さ帯で切って 2D 地図に投影", "(実機の voxel layer と同じ処理)"])
banner("B4", "台本どおりの速度指令: 前進 → 左旋回 → 前進 → 右旋回 → 停止", speed=True)
banner("B6", "障害物 5 個の配置(seed 10)を回避しながら 1 周(追従カメラ、等速)")
banner("B8", "同じ巡回を俯瞰で。回廊に入った障害物だけ減速・旋回(seed 10, v2)", speed=True)
banner("B9", "Foxglove(MCAP): LiDAR 点群が障害物の側面をなぞる。軌跡・TF・指令も記録")
banner("B10a", "v1: Box の前で 停止 → 旋回 → 戻る を繰り返し時間切れ(seed 28)", speed=True)
banner("B10b", "v2: 回避側へ 2 s コミットして Box の脇を抜け完走(seed 28)", speed=True)
banner("B10c", "v3: 地図による経路計画(占有格子 + A*)で Box の脇を最短で抜ける(seed 28)", speed=True)
banner("B10d", "seed 28 の軌跡: v1 は振動、v2 は遠回り、v3 は計画経路(緑)に沿う")
banner("B11", "45 配置 × 4 条件の集計(Wilson 95% CI、McNemar)")
banner("B12c", "2D: 低い箱が見えず踏んで転倒(seed 103、等速)")
banner("B12d", "3D: 低い箱とテーブルを地図に入れて迂回、完走(seed 103)", speed=True)
banner("B12f", "Foxglove: 3D 点群(高さで色分け)が低い箱・天板・円柱をなぞる(seed 103)", speed=True)

# 左右 2 分割用(640×720)
half_card("C1h", "1. 歩行方策を強化学習で獲得",
          ["4096 体並列・300 イテレーション・約 9 分(M1 Max, Metal)", "PPO(rsl-rl)。報酬: 速度指令への追従 + 姿勢の安定",
           "最終: エピソード長 991 / 1000、lin_vel 追従 0.97"])
half_card("C2h", "2. 速度指令への追従",
          ["既定例題の方策は「前進 0.5 m/s」しか学んでいない → 旋回できず直進(橙)", "指令範囲を広げて再学習: vx 0〜0.8 m/s、ωz ±0.8 rad/s",
           "→ 正方形の巡回経路を 16 s で 1 周(青)"])
half_card("C4h", "4. 45 配置で定量評価",
          ["障害物 3〜5 個を乱数配置、60 s 上限", "成功率: 回避なし 9% → v1 91%", "→ v2 96% → v3 100%",
           "接触 91% → 0%(p < 0.0001)", "既定方策(前進のみ)は全条件で 0%"])
half_card("C8h", "3D LiDAR の効果",
          ["30 配置(低い箱 + テーブル + 高い障害物)", "成功 3% → 100%、接触 97% → 0%(p < 0.0001)", "追加コスト +1 ms/step"])
