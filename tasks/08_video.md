# T08: 提出動画(1〜3 分)の素材作成と結合

## 目的
要項の提出動画(MP4、1〜3 分、2 倍速可・明記)を作る。構成は `docs/設計書.md` §5 を実データに合わせて更新した下記ショットリスト。音声なし、日本語テロップのカードで説明する。**氏名・所属・メールを一切出さない**(タイトルは `PAI最終課題_3164`)。

## 前提
- 結合は ffmpeg(無ければ `brew install ffmpeg`)。テロップ用カードは Python(PIL / matplotlib)で 1280×720 の PNG を作り、`ffmpeg -loop 1 -t N` で動画化。日本語フォントは macOS の `/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc` など、存在を確認して使う
- 既存素材(すべて 1280×720 / 50 fps): `videos/t01_script.mp4`(14 s、追従)、`t01_square.mp4`(16 s、追従)、`t03_seed0.mp4`(29 s、俯瞰)、`t04_success_seed10.mp4`(22 s)、`t04_fail_seed12.mp4`(60 s)、`t05_v2_seed12.mp4`、`t05_v2_seed16.mp4`
- 新規収録が必要なもの(手順 1)
- Foxglove の画面収録は **ユーザーが QuickTime で行う**(`videos/raw/foxglove_seed10.mov`、再生 22 s + 前後 2 s)。無い場合はスクリーンショット `results/t06_foxglove_seed10.png` を 6 s の静止カットで代用

## 手順
1. 新規収録(`--backend cpu`、v2 回避あり、俯瞰は **寄せたカメラ** `pos=(1,-3.2,3.0), lookat=(1,1,0.3)` を `go2_patrol.py` の `--camera overhead-close` として追加):
   - `videos/raw/v2_seed10_close.mp4`(成功例、俯瞰寄せ)
   - `videos/raw/v2_seed10_follow.mp4`(同じ seed、追従カメラ)
   - `videos/raw/v2_seed28_close.mp4`(v1 で失敗・v2 で成功した配置。経路を塞ぐ障害物を抜ける)
   - `videos/raw/v1_seed28_close.mp4`(同じ配置を v1 で。振動して時間切れになる様子)
   - 非決定性があるので、各 2〜3 回録って「報告どおりの結果」になった回を採用し、採用回の到達数・所要時間を記録
2. 図の素材(PNG, 1280×720 に収まるようにパディング):
   - `figs/arch.png`: 構成図(LiDAR → 回廊判定 → 回避則 → 速度指令 → RL 方策 → Genesis)。matplotlib の箱と矢印で簡素に
   - `figs/train_curve.png`: `logs/go2-patrol` の tfevents から `rew_tracking_lin_vel` と `rew_tracking_ang_vel` の学習曲線(tensorboard の `EventAccumulator` で読む)
   - `figs/result_50.png`: `results/eval_50/summary.png` を流用(必要なら文字を大きく再描画)
   - `figs/traj_compare.png`: `results/t01_square_traj_compare.png`
   - `figs/traj_t03_seed0.png`: `results/t03_traj_seed0.png`
3. テロップカード(各 3〜5 s):
   - C0 タイトル: 「Go2 の RL 歩行 + LiDAR 巡回・障害物回避(Genesis)」「PAI最終課題_3164」「一部 2 倍速」
   - C1 「1. 歩行方策を強化学習で獲得 — 4096 体並列、9 分(M1 Max, Metal)」
   - C2 「2. 速度指令への追従 — 既定例題は前進のみ。指令範囲を広げて再学習」
   - C3 「3. 疑似 LiDAR(72 本)で反応的に回避 — 地図なし、障害物位置は未使用」
   - C4 「4. 45 配置で定量評価 — 成功 9% → 91%、接触 91% → 0%(p < 0.0001)」
   - C5 「5. 改良 v2: 正面の障害物を抜けるが、遠回りになる(経路効率 1.00 → 0.81)」
   - C6 まとめ: 「実機 Go2 の LiDAR → 速度指令 → 歩行、と同じ層構造をシムで再現」「限界: 真の姿勢を使用(SLAM なし)、静止障害物、非決定性」「コード: github.com/raycast-trail/go2-genesis-patrol」
4. ショットリスト(合計 約 2 分 40 秒。各クリップは必要なら `setpts=0.5*PTS` で 2 倍速にし、カードに「2倍速」を入れる):

| # | 素材 | 長さ | 備考 |
|---|---|---|---|
| 1 | C0 | 5 s | |
| 2 | figs/arch.png | 6 s | |
| 3 | C1 + figs/train_curve.png(左右 2 分割) | 8 s | |
| 4 | t01_script.mp4(2 倍速) | 7 s | 前進→旋回→停止の台本 |
| 5 | C2 + figs/traj_compare.png | 8 s | 既定方策は直進、拡張方策は正方形 |
| 6 | v2_seed10_follow.mp4(等速、先頭 12 s) | 12 s | 歩容を見せる |
| 7 | C3 | 4 s | |
| 8 | v2_seed10_close.mp4(2 倍速) | 12 s | 回避の俯瞰 |
| 9 | foxglove_seed10.mov(2 倍速、無ければ静止画 6 s) | 12 s | LiDAR 点群が障害物をなぞる |
| 10 | v1_seed28_close(2 倍速、振動部分 10 s)→ v2_seed28_close(2 倍速、同区間) | 20 s | 左右分割または連続。カード「v1: 振動して時間切れ / v2: 抜ける」 |
| 11 | C4 + figs/result_50.png | 10 s | |
| 12 | C5 | 5 s | |
| 13 | C6 | 8 s | |

5. 結合: `scripts/make_video.sh`(または Python)で上記を順に `concat`、出力 `videos/final/PAI最終課題_3164.mp4`(H.264, 1280×720, 30 fps, AAC 無音トラック不要)。`ffprobe` で長さが 60〜180 s に収まることを確認
6. 動画内に氏名・所属・メールが無いことを目視確認(カードは全部自作なので、テキストを grep でも確認)

## 受け入れ条件
- [ ] `videos/final/PAI最終課題_3164.mp4` が 60〜180 s、1280×720、再生できる
- [ ] 2 倍速の区間にはテロップで「2倍速」と明記(要項)
- [ ] 個人情報なし
- [ ] `videos/raw/` の採用回の記録(seed、条件、到達、所要)が `reports/08_video.md` にある
- [ ] ショットごとの長さ表と、Foxglove 収録が無い場合の代替をどうしたかの記載

## 成果物
- `scripts/make_video.sh`(または `.py`)、`figs/*.png`、`videos/raw/*.mp4`(採用回のみコミット、各 20 MB 以下)、`videos/final/*.mp4`
- `reports/08_video.md`
