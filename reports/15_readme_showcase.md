# T15 報告: README を実績紹介向けに仕上げる(冒頭 GIF・英語要約・トピック・ソーシャルプレビュー)

## 受け入れ条件の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| `hero.gif`: 左右同期(末尾のずれ量)、英語ラベル、2 倍速表示、8 MB 以下、ループ | ✅ | 同じ実行の録画と MCAP。末尾のずれ 0.24〜0.26 s(< 0.5 s なので伸縮なし)。1.41 MB、`-loop 0` |
| `v1_v2_v3_seed28.gif`: 3 分割、ラベル、8 MB 以下 | ✅ | 960×226、1.29 MB |
| `social_preview.png`: 1280×640 | ✅ | 1280×640、0.18 MB |
| README 冒頭に GIF と英語要約、数値が summary.md と一致、日本語本文は維持、個人情報 grep 0 件 | ✅ | §4。既存の日本語本文は 1 行も変えていない(追加のみ) |
| リポジトリの説明文とトピック | ✅ | `gh` が認証済みだったので実行し、`gh repo view` で確認(§5) |
| `docs/report/` を含めて push、`git status` は `videos/t01_square_baseline.mp4` 以外クリーン | ✅ | §6 |
| 本報告 | ✅ | |

## 実行したコマンド

```bash
conda activate py311_genesis
python -c "from mcap.reader import make_reader; ..."      # MCAP の長さ(27.76 s)
ffprobe videos/raw/t12_3d_seed103_close.mp4                # 27.78 s
python scripts/make_gifs.py                                # GIF 2 本 + ソーシャルプレビュー
gh repo edit raycast-trail/go2-genesis-patrol --description "..." --add-topic ...   # §5
gh api repos/raycast-trail/go2-genesis-patrol/readme            # push 後の確認
```

## 1. 冒頭 GIF `docs/media/hero.gif`

### 同じ実行かの確認

| 素材 | 長さ | 更新時刻 | 出典 |
|---|---|---|---|
| `videos/raw/t12_3d_seed103_close.mp4`(Genesis 俯瞰、50 fps) | 27.78 s | 10/21 18:31 | reports/13 §採用テイク: 「4/4、27.8 s、接触 0 → `videos/t12_3d_seed103.mp4`, `videos/raw/t12_3d_seed103_close.mp4`, `results/mcap/t12_3d_seed103.mcap`」(`--out` と `--mcap` を同時に指定した 1 回の実行) |
| `videos/t12_3d_seed103_log.csv`(同じ実行のログ) | 最終行 t = 27.76 s | 10/21 18:31 | |
| `results/mcap/t12_3d_seed103.mcap` | 27.76 s(message start 0.00 → end 27.76) | 10/21 18:31 | `mcap` ライブラリの summary から |
| `videos/raw/foxglove_3d_seed103.mp4`(T14、MCAP の再生を収録) | 27.50 s(収録の 0.80〜28.30 s) | | T14 で再生後の静止の始まりを 28.32 s(= クリップの 27.52 s)と測定 |

→ 長さ・更新時刻・報告の記録が一致し、**同じ実行**と判定。

### 時刻合わせ

- 両方の先頭を t = 0 に揃えた(Foxglove 側は T14 で再生開始の位置で切ってある)
- 末尾: Genesis の完走 27.76 s(MCAP の終端)に対し、Foxglove の動きが止まるのは 27.52 s → **ずれ 0.24 s**(クリップ長 27.50 s との差は 0.26 s)。0.5 s 未満なので `setpts` での伸縮はしていない(`--fox-stretch 1.0`。伸縮が必要な場合のためにこの引数を残した)
- 目視: GIF の 2.5 / 7 / 12.5 / 14.6 s のフレームで、ロボットの位置(スタート直後 → 低い箱とテーブルの間 → 奥の円柱 → スタート地点)が左右で対応していることを確認。カメラの向きは左右で違う(Foxglove は収録時の視点)。途中の 0.3〜0.4 s の描画の止まりは残っているが、末尾で揃っているので累積のずれは 0.3 s 以下

### 仕様表

| 項目 | hero.gif | v1_v2_v3_seed28.gif |
|---|---|---|
| 大きさ | 960×322(上の帯 30 + 映像 270 + 下の帯 22) | 960×226(上の帯 26 + 映像 180 + 下の帯 20) |
| 区画 | 480×270 × 2 | 320×180 × 3 |
| 長さ | 14.89 s(2 倍速で 13.89 s + 末尾 1 s 静止) | 15.43 s(v3 の完走 29.86 s + 1 s をシム時間で、2 倍速) |
| fps | 12 | 12 |
| サイズ | **1.41 MB** | **1.29 MB** |
| ループ | 無限(`-loop 0`) | 無限 |
| 帯のラベル | 左「Simulation (Genesis)」、右「3D LiDAR point cloud (Foxglove)」、下「Unitree Go2 · RL locomotion + LiDAR navigation · 2× speed」 | 「v1 reactive」「v2 + commit」「v3 map + A*」、下「Same scene (seed 28) · 2× speed」 |
| 色数・ディザ | palettegen 128 色(stats_mode=diff)、paletteuse bayer(scale 4) | 同左 |

- 帯は背景 0x141820、白文字(Helvetica)、文字は各区画の左端から 16 px(比較 GIF は 12 px)
- Foxglove 側は T14 のクリップから左右のパディング(96 px)を除き、上下を 612 px に切って(`crop=1088:612:96:54`)16:9 にした。上は空、下は地面だけの部分を落とし、円柱の上端とテーブルの脚は残っている
- 比較 GIF の下の帯「Same scene (seed 28) · 2× speed」は仕様にない追加(2 倍速であることを示すため)。各素材の先頭 t = 0 で揃え、v1 は振動中、v2 は遠回り中のまま終わる
- 調整候補は使っていない(どちらも 8 MB を大きく下回った)

## 3. ソーシャルプレビュー `docs/media/social_preview.png`

1280×640、背景 0x141820。左に `results/t14_foxglove3d_seed103.png` を縮小(角丸 16 px、左余白 60 px、右端は幅の 55% の位置)、右にタイトル「Go2 Patrol / in Genesis」(2 行)、サブ「RL locomotion · 3D LiDAR · occupancy map + A*」(2 行)、数値「45 scenes: success 9% → 100%」「Low obstacles: 2D 3% → 3D 100%」。右余白 約 130 px、上下余白 ≥ 60 px。Helvetica に「→」が無かったので矢印だけ Arial Bold で描いた。

数値の出典: 9% = `results/eval_50/summary.md` の「v1 回避なし 4/45」、100% = 「v3 地図+A* 45/45」。3% / 100% = `results/eval_3d/summary.md` の「v3 + 2D LiDAR 1/30」「v3 + 3D LiDAR 30/30」。

**人間がやること**: GitHub のリポジトリ → Settings → General → Social preview → Edit → Upload an image… で `docs/media/social_preview.png` を選ぶ。

## 4. README 冒頭の差分

````diff
 # go2-genesis-patrol

+![hero](docs/media/hero.gif)
+
+**Unitree Go2 patrol in the Genesis simulator — RL locomotion + LiDAR navigation, evaluated on randomized scenes.**
+
+- A walking policy trained with PPO (4,096 parallel envs, 9 min on an M1 Max) follows velocity commands; a deterministic navigation stack on top of it patrols a square route.
+- Navigation was improved step by step — reactive avoidance (v1) → commit phase (v2) → occupancy grid + A* (v3) — raising patrol success from 9% to 100% with zero contacts over 45 randomized scenes.
+- A 3D pseudo-LiDAR projected onto the body-height band detects low boxes and table tops that a 2D scan misses (success 3% → 100% over 30 scenes).
+- Everything runs on a single Mac (Metal / CPU); logs export to MCAP for Foxglove.
+
+📄 Report (Japanese): [docs/report/report.pdf](docs/report/report.pdf) · 🎬 Full video: (提出後に URL を記載)
+
+---
+
 Unitree Go2 の歩行方策を Genesis 上で強化学習し、…(既存の日本語本文、変更なし)
````

結果の節(v1/v2/v3 の表の直後):

````diff
+![v1 v2 v3](docs/media/v1_v2_v3_seed28.gif)
+
+同じ配置(seed 28)の v1 / v2 / v3(2 倍速、v3 の完走 + 1 s まで)。v1 は Box の前で振動、v2 は遠回り、v3 は計画経路で脇を抜ける。
````

その他の追記(仕様外だが既存の慣例に合わせた小さな追加): 再現手順 6 に `python scripts/make_gifs.py`、リポジトリ構成の `docs/` に `media/`、開発ログに T15。

### 英文の数値の照合

| 英文の記述 | 出典 | 一致 |
|---|---|---|
| success from 9% to 100%, zero contacts, 45 randomized scenes | eval_50: v1 回避なし 4/45 = 9%、v3 45/45 = 100%、接触 0/45、n = 45 | ✅ |
| success 3% → 100% over 30 scenes | eval_3d: v3 + 2D 1/30 = 3%、v3 + 3D 30/30 = 100%、n = 30 | ✅ |
| 4,096 parallel envs, 9 min on an M1 Max | summary.md には無い。既存 README の構成表「4096 env × 300 it(M1 Max / Metal で約 9 分)」から(新しい主張ではない) | ✅(既存記述) |

仕様の英文案から数値の修正は不要だった。キャプションの「v1 は振動、v2 は遠回り、v3 は計画経路」は動画の帯 B10a〜B10d と同じ内容。

### 個人情報

README と `scripts/make_gifs.py` をメールアドレスの形・所属名で grep して 0 件。表示する識別子は従来どおり提出ファイル名 `PAI最終課題_3164`(PDF のファイル名)と GitHub の URL のみ。GIF・プレビュー画像の文字は上記の英語ラベルだけ。

## 5. リポジトリの説明文とトピック

`gh auth status` で認証済み(リポジトリ所有者のアカウント)だったので、仕様のコマンドをそのまま実行した。

| 項目 | 変更前 | 変更後 |
|---|---|---|
| description | RL locomotion + LiDAR-based patrol and obstacle avoidance for Unitree Go2 in Genesis (Physical AI 2026 final project) | Unitree Go2 patrol in Genesis: RL locomotion + 2D/3D LiDAR navigation (reactive → map + A*), evaluated on randomized scenes. Runs on a Mac. |
| topics | なし | foxglove, genesis, legged-robots, lidar, navigation, occupancy-grid, physical-ai, reinforcement-learning, robotics, unitree-go2 |

## 6. 確認とコミット

- push 後に `gh api repos/raycast-trail/go2-genesis-patrol/readme` で README が取得でき、GIF のパスが相対パス(`docs/media/hero.gif`、`docs/media/v1_v2_v3_seed28.gif`)で、そのパスのファイルがリポジトリにあることを `gh api repos/.../contents/docs/media` で確認した
- `docs/report/`(人間が更新した v3.1: `report.html`、`figs/foxglove3d_seed103.jpg`)を内容を変えずに含めた。PDF は作業開始時点で変更なし(T14 のコミットと同一)だったのでこのコミットには入らない

## 変更したファイル

| ファイル | 理由 |
|---|---|
| `scripts/make_gifs.py`(新規) | GIF 2 本とソーシャルプレビューの生成(再現用) |
| `docs/media/hero.gif`, `docs/media/v1_v2_v3_seed28.gif`, `docs/media/social_preview.png`(新規) | 成果物 |
| `README.md` | 冒頭の GIF・英語要約、比較 GIF、再現手順・構成・開発ログの 1 行ずつ |
| `docs/report/report.html`, `docs/report/figs/foxglove3d_seed103.jpg` | 人間が更新したレポート v3.1(内容は変えていない) |
| `tasks/15_readme_showcase.md` | タスク仕様 |

## うまくいかなかったこと・仮定

- Helvetica に「→」のグリフが無く、初回のプレビュー画像で豆腐(□)になった → 矢印だけ Arial Bold で描くように修正
- hero.gif の Foxglove 側は 16:9 に合わせるため上下を切った(仕様に指定なし)。代わりに縮小 + パディングにすると右の区画の左右に 36 px ずつ余白が入る
- 同期の確認は末尾の時刻と 4 フレームの目視。フレーム単位の厳密な照合はしていない(Foxglove の描画の止まりがあるため ±0.3 s 程度の局所的なずれはありうる)

## 次タスクへの申し送り

- YouTube の URL が決まったら、英語要約の行「🎬 Full video: (提出後に URL を記載)」と日本語の「提出動画」の行を差し替え、サムネイルのリンクを入れる
- ソーシャルプレビューの登録(§3)は人間の作業
