# T08 報告: 提出動画(1〜3 分)の素材作成と結合

対象タスク: `tasks/08_video.md`。実行日 2026-10-21、環境は CLAUDE.md のとおり(M1 Max / `py311_genesis` / genesis-world 1.4.4、ffmpeg 8.1 は導入済み)。新規収録は `--backend cpu`。

## 結論

- `videos/final/PAI最終課題_3164.mp4` を作成: **111.0 s、1280×720、30 fps、H.264、音声なし、3.4 MB**(要件 60〜180 s を満たす)
- 2 倍速の 5 ショットには帯テロップの右端に「2倍速」を常時表示。タイトルカードにも「一部 2 倍速(右上に表示)」と明記
- Foxglove の画面収録(`videos/raw/foxglove_seed10.mov`)は無かったので、仕様の代替どおり T06 のスクリーンショットを 6 s の静止カットにした。スクリーンショットは上部バー(アカウントのアイコンを含む)と左の設定パネルを切り落とし、3D パネルと Plot だけを使った
- 個人情報: カード・帯の文字列はすべて `scripts/make_cards.py` にあり、`@`・氏名・所属を grep して 0 件。動画中の文字はカードと帯のみ(シミュレーション映像と図に文字情報はない)。表示する識別子は `PAI最終課題_3164` と GitHub の URL だけ

| 受け入れ条件 | 判定 | 実測 |
|---|---|---|
| 最終 MP4 が 60〜180 s、1280×720、再生できる | ✅ | 111.0 s、1280×720、h264、30 fps(ffprobe)。QuickTime 互換の yuv420p + faststart |
| 2 倍速区間に「2倍速」の明記 | ✅ | ショット 4, 8, 10a, 10b の帯に表示(ショット 9 は静止画のため等速) |
| 個人情報なし | ✅ | カード文字列を grep、スクリーンショットのアイコン部分を切り落とし |
| 採用回の記録(seed、条件、到達、所要) | ✅ | §1 |
| ショットごとの長さ表、Foxglove 代替の記載 | ✅ | §3、§4 |

## 実行したコマンド

```bash
conda activate py311_genesis
# 1. 新規収録(各 3 テイク。採用回を videos/raw/ に再エンコード)
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 10 --avoid --avoid-version v2 --camera overhead-close --out <take>.mp4 --summary-csv ""
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 10 --avoid --avoid-version v2 --camera follow         --out <take>.mp4 --summary-csv ""
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 28 --avoid --avoid-version v2 --camera overhead-close --out <take>.mp4 --summary-csv ""
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 28 --avoid --avoid-version v1 --camera overhead-close --out <take>.mp4 --summary-csv ""
ffmpeg -i <採用テイク> -c:v libx264 -crf 23 -pix_fmt yuv420p -an videos/raw/<name>.mp4
# 2〜3. 図とカード
python scripts/make_figs.py      # figs/arch.png, train_curve(.png/_half.png), result_50(.png/_half.png), traj_*.png, foxglove_crop.png
python scripts/make_cards.py     # figs/cards/C0..C6.png, C1h/C2h/C4h.png(分割用 640×720), B*.png(帯)
# 5. 結合と確認
python scripts/make_video.py --v1-seed28-start 14 --v2-seed28-start 6
ffprobe -show_entries format=duration:stream=width,height,r_frame_rate,codec_name "videos/final/PAI最終課題_3164.mp4"
```

## 1. 新規収録(手順 1)と採用回

`go2_patrol.py` に `--camera overhead-close`(pos=(1, −3.2, 3.0), lookat=(1, 1, 0.3))を追加。各クリップを 3 テイク録り、報告(T07)どおりの結果になった回を採用した。非決定性(T07 §1)のため seed 28 v2 は 3 テイク中 1 回が失敗した。

| クリップ | seed | 回避則 | カメラ | テイク 1 | テイク 2 | テイク 3 | 採用 | 採用回の結果 |
|---|---|---|---|---|---|---|---|---|
| `videos/raw/v2_seed10_close.mp4` | 10 | v2 | 俯瞰寄せ | 4/4 26.9 s | 4/4 30.7 s | 4/4 27.4 s | 1 | 4/4、26.9 s、接触 0 |
| `videos/raw/v2_seed10_follow.mp4` | 10 | v2 | 追従 | 4/4 27.4 s | 4/4 27.1 s | 4/4 28.3 s | 2 | 4/4、27.1 s、接触 0 |
| `videos/raw/v2_seed28_close.mp4` | 28 | v2 | 俯瞰寄せ | 4/4 35.3 s | **3/4 timeout** | 4/4 34.1 s | 3 | 4/4、34.1 s、接触 0(WP0 5.8 s、WP1 17.0 s、WP2 28.3 s) |
| `videos/raw/v1_seed28_close.mp4` | 28 | v1 | 俯瞰寄せ | 3/4 timeout | 3/4 timeout | 3/4 timeout | 1 | 3/4、60 s timeout、接触 0(x = 2 の辺の Box の前で t = 14〜42 s に停止・旋回を反復) |

採用テイクは crf 23 で再エンコードし 0.5〜2.5 MB(各 20 MB 以下)。各テイクのログ CSV は `videos/raw/*_log.csv`(gitignore 対象、ローカルのみ)。

ショット 10 の切り出し区間はログから決めた: v1 は `cmd_vx ≈ 0` が続く t = 14〜42 s のうち 14〜34 s(2 倍速で 10 s)、v2 は同じ Box を右から回り込む t = 6〜26 s(WP1 到達 17.0 s を含む)。

## 2. 図とカード(手順 2, 3)

| ファイル | 内容 |
|---|---|
| `figs/arch.png` | 構成図(ウェイポイント → 経路追従 → 回避則 → 速度指令 → RL 方策 → Genesis、LiDAR はセクタ距離を回避則へ)。matplotlib |
| `figs/train_curve.png`, `figs/train_curve_half.png` | `logs/go2-patrol` の tfevents(`Episode/rew_tracking_lin_vel`, `Episode/rew_tracking_ang_vel`, `Train/mean_episode_length`)。横 3 面と、分割ショット用の縦 3 段 |
| `figs/result_50.png`, `figs/result_50_half.png` | `results/eval_50/episodes.csv` から成功率・接触率・所要時間(Wilson 95% CI)を大きな文字で再描画 |
| `figs/traj_compare.png`, `figs/traj_t03_seed0.png` | T01・T03 の軌跡図を 1280×720 にパディング(動画では `results/t01_square_traj_compare.png` を分割ショットに直接使用) |
| `figs/foxglove_crop.png` | T06 スクリーンショットの 3D + Plot 部分を切り出し(上部バーと左パネルを除外) |
| `figs/cards/C0..C6.png` | テロップカード 1280×720(PIL、ヒラギノ角ゴシック W6) |
| `figs/cards/C1h, C2h, C4h.png` | 左右分割用 640×720 カード(文字を自動折り返し) |
| `figs/cards/B4, B6, B8, B9, B10a, B10b, B11.png` | 動画の上に重ねる帯(1280×90、半透明)。2 倍速のものは右端に「2倍速」バッジ |

カードの文言はタスク指定どおり(C4 は 45 配置の実測値: 成功 9% → 91%、接触 91% → 0%、p < 0.0001。C5 は v2 の成功 91% → 96%、p = 0.69、経路効率 1.00 → 0.81)。

## 3. ショットリストと長さ(`scripts/make_video.py` の出力)

| # | 素材 | 長さ [s] | 速度 | 備考 |
|---|---|---|---|---|
| 1 | C0 タイトル | 5.0 | — | 「PAI最終課題_3164」「一部 2 倍速」 |
| 2 | figs/arch.png | 6.0 | — | |
| 3 | C1h + train_curve_half(左右分割) | 8.0 | — | |
| 4 | t01_script.mp4(先頭 14 s) | 7.0 | **2 倍速** | 帯 B4「台本どおりの速度指令…」 |
| 5 | C2h + t01_square_traj_compare(左右分割) | 8.0 | — | 既定方策は直進、拡張方策は正方形 |
| 6 | v2_seed10_follow.mp4(先頭 12 s) | 12.0 | 等速 | 帯 B6 |
| 7 | C3 | 4.0 | — | |
| 8 | v2_seed10_close.mp4(先頭 24 s) | 12.0 | **2 倍速** | 帯 B8 |
| 9 | foxglove_crop.png(静止画) | 6.0 | — | 収録なしの代替。帯 B9 |
| 10a | v1_seed28_close.mp4(14〜34 s) | 10.0 | **2 倍速** | 帯 B10a「v1: 停止 → 旋回 → 戻る を繰り返し時間切れ」 |
| 10b | v2_seed28_close.mp4(6〜26 s) | 10.0 | **2 倍速** | 帯 B10b「v2: 2 s コミットして Box の脇を抜け完走」 |
| 11 | C4h + result_50_half(左右分割) | 10.0 | — | |
| 12 | C5 | 5.0 | — | |
| 13 | C6 まとめ | 8.0 | — | |
| | **合計** | **111.0** | | |

タスクのショットリスト(約 160 s)より短いのは、Foxglove を 12 s の収録ではなく 6 s の静止画にしたことと、ショット 10 を左右分割ではなく連続 10 s + 10 s にしたため。要件(60〜180 s)の範囲内。

## 4. Foxglove 収録の代替

`videos/raw/foxglove_seed10.mov` は存在しなかったため、`results/t06_foxglove_seed10.png` を使った。画像の上部バーにはアプリのアカウントアイコンが写っているので、`scripts/make_figs.py::foxglove_crop` で 3D パネルと Plot 2 段だけ(元画像の x 28.7〜99.3%、y 8.5〜96%)を切り出して使用。後から `.mov` を置けば `make_video.py` が自動で 2 倍速 12 s の動画カットに差し替える(帯は B9 のまま。2 倍速バッジ付きの `B9s.png` があればそれを使う)。

## 5. 確認

- `ffprobe`: duration 111.0 s、1280×720、h264、30/1 fps、yuv420p。ファイル 3.4 MB
- 13 ショットから 1 フレームずつ抜き出して目視: 帯の文字が切れていないこと、分割カードの折り返し、2 倍速バッジ、Foxglove 切り出しにアイコンが無いことを確認(最初の組み立てではカード文字の切れと所要時間パネルのラベル重なりがあり、分割用カード・縦 3 段の図に作り直した)
- 個人情報: `grep -c` でメールアドレス・所属・氏名のパターンを検索 → 0

## 変更したファイルと理由

| ファイル | 変更 |
|---|---|
| `go2_patrol.py` | `--camera overhead-close` を追加 |
| `scripts/make_figs.py` | **新規**。図の生成(§2) |
| `scripts/make_cards.py` | **新規**。カードと帯(§2) |
| `scripts/make_video.py` | **新規**。ffmpeg で中間クリップを作って concat。`-ss/-t` で切り出し、`setpts=0.5*PTS` で 2 倍速、`overlay` で帯、`hstack` で左右分割。`--v1-seed28-start` / `--v2-seed28-start` で切り出し開始秒を指定 |
| `figs/`, `figs/cards/` | 図・カード・帯(§2) |
| `videos/raw/*.mp4` | 採用テイク 4 本(0.5〜2.5 MB) |
| `videos/final/PAI最終課題_3164.mp4` | 提出動画 |
| `tasks/08_video.md` | 本タスクの仕様(作業者作成) |

## 仮定したこと

- ショット 10 は「左右分割または連続」のうち連続(10 s + 10 s)にした。俯瞰寄せの映像を半分に縮めると障害物が見にくいため
- ショット 6 の追従カメラは T01 と同じ斜め後方からの追従(`--camera follow`)
- `-t` はクリップの入力側の長さ(2 倍速なら出力の 2 倍)で指定
- 最初の組み立てで `-t` を 2 つ目の入力(帯 PNG)に付けてしまい動画が全長で入った(144.6 s)。修正して 111.0 s になった
- 要項の「2 倍速可・明記」は帯の「2倍速」バッジとタイトルカードの注記で満たすと解釈

## うまくいかなかったこと

- Foxglove の画面収録が無く静止画で代用した(§4)
- seed 28 v2 は 3 テイク中 1 回失敗(非決定性)。採用回は成功したテイク 3

## 申し送り

1. Foxglove を QuickTime で収録したら `videos/raw/foxglove_seed10.mov` に置いて `python scripts/make_video.py --v1-seed28-start 14 --v2-seed28-start 6` を再実行するだけで差し替わる(長さは +6 s で 117 s)
2. 文言の修正は `scripts/make_cards.py` を編集して `make_cards.py` → `make_video.py` の順に再実行
3. 動画の数値はすべて T07(45 配置)の `results/eval_50/summary.md` と一致させてある。レポート PDF も同じ数値を使うこと
