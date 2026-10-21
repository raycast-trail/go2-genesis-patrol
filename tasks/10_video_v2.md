# T10: 提出動画 v2(v3 の反映 + テロップ余白の修正)と docs/report のコミット

## 目的
1. T09 の v3(占有格子 + A*)を動画に反映する。ショット 10 を **v1 → v2 → v3 の 3 連**にし、結果カードを 4 条件にする
2. **テロップの右端の余白が足りない**(人間のレビュー指摘: 画面内には収まっているが右端ギリギリ)。全カード・全バナーで **左右 100 px 以上の余白**を保証する
3. `docs/report/`(レポート PDF・HTML・図、人間が作成)を **このコミットに含める**

T08 の `scripts/make_cards.py` / `scripts/make_video.py` を改修して再生成する。素材の再収録は不要(`videos/raw/v3_seed28_close.mp4` は T09 で収録済み)。

## 手順

### 1. テロップの余白(`scripts/make_cards.py`)
- `card()`: 現状はタイトル・本文を折り返していない。`wrap()` を使って **幅 W − 2×100 = 1080 px** で折り返す。折り返しても縦に収まらない(最終行の y + 行高 > H − 120)場合は `title_size` / `line_size` を 2 px ずつ下げて収まるまで再試行。左端 x は 80 のままでよい(右端の余白を 100 px 以上にするため、折り返し幅は 1280 − 80 − 100 = 1100 px 以下)
- `half_card()`: 折り返し幅を `HW − 80` → `HW − 100` に
- `banner()`: `limit` を `W − 230`(2倍速あり)/ `W − 60` → それぞれ **`W − 260` / `W − 120`** に。自動縮小の下限 18 → 22 px とし、22 px でも収まらない文は 2 行にせず **文を短くする**(バナーは 1 行)
- 受け入れ確認用に `scripts/check_margins.py` を追加: `figs/cards/*.png` を読み、背景色以外のピクセルの x の最大値が **W − 100 以下**、最小値が 80 以下(左帯を除く)であることを全ファイルで検査して表にする(PIL + numpy)。バナーは半透明なのでアルファ > 0 かつ帯色以外で判定

### 2. 新しいカードとバナー(テキスト案。長ければ短くしてよいが数値は変えない。数値は `results/eval_50/summary.md` の 4 条件表に合わせる)
- C0〜C3: 変更なし(余白修正のみ)
- **B10c**(新規、2倍速): 「v3: 占有格子地図 + A* で経路を計画し、Box の脇を最短で抜ける(seed 28)」
- **B10d**(新規、等速扱い=速度表示なし): 「seed 28 の軌跡: v1 は振動、v2 は遠回り、v3 は計画経路(破線)に沿う」
- **C4 / C4h**: 「4. 45 配置で定量評価」/ 本文「回避なし 9% → v1 91% → v2 96% → v3 100%(成功率)」「接触 91% → 0%(p < 0.0001)」
- **B11**: 「45 配置 × 4 条件の集計(Wilson 95% CI、McNemar)」
- **C5**: タイトル「5. 系統的改良: v1 → v2 → v3」本文 3 行: 「v1 反応的回避: 速いが正面の障害物で振動(91%)」「v2 コミット区間: 抜けるが遠回り(96%、経路効率 0.81)」「v3 占有格子 + A*: 両立(100%、所要 24.2 s、経路効率 1.05)」
- **C6**: 「実機 Go2 の 自己位置 → 地図・計画 → 速度指令 → 歩行 と同じ 3 層構造をシムで再現」「限界: 真の姿勢を使用(SLAM なし)、静止障害物、非決定性」「コード: github.com/raycast-trail/go2-genesis-patrol」

### 3. 図(`scripts/make_figs.py`)
- `figs/result_50.png`, `figs/result_50_half.png`: `results/eval_50/summary.png`(4 条件版)から再生成
- `figs/arch.png`: 構成図に「占有格子地図 + A*(v3)」の箱を追加(LiDAR → 地図 → A* → ローカル目標 → 速度指令。反応的回避は下層として並記)
- `figs/traj_seed28.png`: `results/t09_traj_seed28.png` を 1280×720 にパディング(B10d 用)

### 4. ショットリスト v2(`scripts/make_video.py`)。合計 約 2 分 10 秒

| # | 素材 | 長さ | 変更 |
|---|---|---|---|
| 1〜9 | T08 と同じ | 74 s | 余白修正のみ |
| 10a | v1_seed28_close(2 倍速)+ B10a | 10 s | 同じ |
| 10b | v2_seed28_close(2 倍速)+ B10b | 10 s | 同じ |
| **10c** | **v3_seed28_close(2 倍速、先頭 10 s)+ B10c** | 10 s | 新規 |
| **10d** | **figs/traj_seed28.png(静止)+ B10d** | 6 s | 新規 |
| 11 | C4h + figs/result_50_half.png(4 条件) | 10 s | 差し替え |
| 12 | C5(v1→v2→v3) | 7 s | 差し替え、5 → 7 s |
| 13 | C6 | 8 s | 文言更新 |

- 10c の開始位置は v3 が Box に接近して脇を抜ける区間が入るように選ぶ(`videos/raw/v3_seed28_close_log.csv` から Box 最接近の時刻を取り、その 3 s 前から)。`--v3_seed28_start` 引数で指定
- 出力 `videos/final/PAI最終課題_3164.mp4` を **上書き**(旧版は `videos/final/` に残さない。git 履歴にある)

### 5. docs/report のコミット
- `docs/report/report.pdf`, `docs/report/report.html`, `docs/report/figs/*.png` を `git add` して **T10 のコミットに含める**(内容の編集はしない。人間がレポートを v3 対応に差し替えたら再度 add するので、無ければそのまま)
- PDF が 10 MB を超えていないことを確認

## 受け入れ条件
- [ ] `scripts/check_margins.py` の表で全カード・全バナーの右端余白 ≥ 100 px
- [ ] `videos/final/PAI最終課題_3164.mp4` が 60〜180 s、1280×720、再生できる。ショット 10c に v3 の回避が映っている(コンタクトシート `results/t10_contact.png` を `ffmpeg -vf "fps=1/5,scale=320:-1,tile=6x5"` で作って目視)
- [ ] 2 倍速区間に「2倍速」表示(B10c 含む)
- [ ] カードのテキストを grep して氏名・所属・メールなし
- [ ] `git status` で `docs/report/` が追跡済み
- [ ] `reports/10_video_v2.md`: ショット表(v2)、採用した 10c の開始位置、余白検査の表、変更したカード文言の一覧

## 調整候補(最大 2 つ)
1. 合計が 180 s を超える場合: ショット 6(追従、12 s)を 8 s に、ショット 9 を 8 s に
2. B10d の軌跡図が 720 p で読めない場合: 10d を省略し、10c を 14 s に

## 成果物
- `scripts/make_cards.py`, `scripts/make_figs.py`, `scripts/make_video.py`, `scripts/check_margins.py`
- `figs/cards/*.png`(更新), `figs/arch.png`, `figs/result_50*.png`, `figs/traj_seed28.png`
- `videos/final/PAI最終課題_3164.mp4`(上書き), `results/t10_contact.png`
- `docs/report/`(追跡開始)
- `reports/10_video_v2.md`
