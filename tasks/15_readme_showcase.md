# T15: README を実績紹介向けに仕上げる(冒頭 GIF・英語要約・トピック・ソーシャルプレビュー)

## 目的
このリポジトリは課題提出物であると同時に、Physical AI の実績紹介としても使う。README を開いた瞬間に何をしたリポジトリか伝わるようにする。
1. 冒頭に自動再生されるアニメーション GIF(シミュレータ映像と Foxglove の点群を同期して横並び)
2. 結果の節に v1 → v2 → v3 の比較 GIF
3. 冒頭に英語の要約(本文は日本語のまま)
4. リポジトリの説明文とトピック、ソーシャルプレビュー画像(登録は人間)

YouTube の URL はまだ無い。README の「動画」の行は既存のプレースホルダ `(提出後に URL を記載)` のまま残し、YouTube サムネイルのリンクは次のタスクで入れる。数値は `results/eval_50/summary.md`・`results/eval_3d/summary.md` から転記し、新しい主張を書かない。個人情報(氏名・所属・メール)は入れない。

## 手順

### 1. 冒頭 GIF `docs/media/hero.gif`
- 素材: `videos/raw/t12_3d_seed103_close.mp4`(Genesis 俯瞰、3D LiDAR、seed 103)と `videos/raw/foxglove_3d_seed103.mp4`(T14 で整形した Foxglove 収録)
- **同じ実行の録画か確認する**: `reports/12`・`reports/13` の記録から、`t12_3d_seed103_close.mp4` と `results/mcap/t12_3d_seed103.mcap` が同じ実行(`--out` と `--mcap` を同時に指定)で作られたかを確認。所要時間(Genesis 側の完走時刻と MCAP の長さ 27.7 s)が一致するかで判定する
- **時刻合わせ**: Genesis 側はシミュレーション時間どおり。Foxglove 側は先頭を再生開始に合わせてあるが、途中に 0.3〜0.4 s の描画の止まりがある。両方の先頭を t = 0 に合わせ、**末尾(完走時刻)で 0.5 s 以上ずれる場合は、Foxglove 側を `setpts` で線形に伸縮して末尾を合わせる**。ずれ量を報告に書く。同じ実行でなかった場合は同期をやめ、Genesis → Foxglove の順に縦ではなく **時間で連結**(各 6 s)にする
- レイアウト: 左右 2 分割(各 480×270 程度、全体 960×300 前後)、上に細い帯で左「Simulation (Genesis)」右「3D LiDAR point cloud (Foxglove)」の英語ラベル(帯は背景色 `0x141820`、白文字、余白 ≥ 16 px)。下端に小さく「Unitree Go2 · RL locomotion + LiDAR navigation · 2× speed」
- 2 倍速、約 12〜14 s(完走まで)、末尾 1 s 静止してからループ。**10〜12 fps、幅 960 px、8 MB 以下**(ffmpeg の `palettegen` / `paletteuse`、`dither=bayer` などで調整。超える場合は幅 800 px → fps 10 の順で下げる)

### 2. 比較 GIF `docs/media/v1_v2_v3_seed28.gif`
- 素材: `videos/raw/v1_seed28_close.mp4`、`v2_seed28_close.mp4`、`v3_seed28_close.mp4`
- 3 分割の横並び(各 320×180、全体 960×200 前後)、上の帯に「v1 reactive」「v2 + commit」「v3 map + A*」、2 倍速、各素材の先頭 t = 0 で揃え、**v3 が完走した時刻 + 1 s で切る**(v1 は振動中、v2 は遠回り中のまま終わってよい)。8 MB 以下

### 3. ソーシャルプレビュー画像 `docs/media/social_preview.png`(1280×640)
- 背景 `0x141820`。左 55% に `results/t14_foxglove3d_seed103.png` を縮小して配置(角を少し丸める程度で可)、右にタイトル「Go2 Patrol in Genesis」、サブ「RL locomotion · 3D LiDAR · occupancy map + A*」、数値 2 行「45 scenes: success 9% → 100%」「Low obstacles: 2D 3% → 3D 100%」。フォントは英語なのでヒラギノ以外(Helvetica など)でよい。余白 ≥ 60 px
- GitHub への登録は人間が行う(Settings → General → Social preview)。報告に手順を 1 行書く

### 4. README の冒頭を再構成
既存の 9 章構成は維持し、その **前** に次を置く:
```
# go2-genesis-patrol

![hero](docs/media/hero.gif)

**Unitree Go2 patrol in the Genesis simulator — RL locomotion + LiDAR navigation, evaluated on randomized scenes.**

- A walking policy trained with PPO (4,096 parallel envs, 9 min on an M1 Max) follows velocity commands; a deterministic navigation stack on top of it patrols a square route.
- Navigation was improved step by step — reactive avoidance (v1) → commit phase (v2) → occupancy grid + A* (v3) — raising patrol success from 9% to 100% with zero contacts over 45 randomized scenes.
- A 3D pseudo-LiDAR projected onto the body-height band detects low boxes and table tops that a 2D scan misses (success 3% → 100% over 30 scenes).
- Everything runs on a single Mac (Metal / CPU); logs export to MCAP for Foxglove.

📄 Report (Japanese): docs/report/report.pdf · 🎬 Full video: (提出後に URL を記載)

---
(以下、既存の日本語の概要 → 結果 → …)
```
- 英文は上の案を基本に、数値が `summary.md` と一致するか確認する(一致しなければ数値を直して報告)
- 「結果」の節の v1/v2/v3 の表の直後に `![v1 v2 v3](docs/media/v1_v2_v3_seed28.gif)` とキャプション 1 行
- 既存の構成図・結果図はそのまま

### 5. リポジトリの説明文とトピック(`gh`)
```bash
gh repo edit raycast-trail/go2-genesis-patrol \
  --description "Unitree Go2 patrol in Genesis: RL locomotion + 2D/3D LiDAR navigation (reactive → map + A*), evaluated on randomized scenes. Runs on a Mac." \
  --add-topic unitree-go2 --add-topic genesis --add-topic reinforcement-learning --add-topic legged-robots \
  --add-topic lidar --add-topic navigation --add-topic occupancy-grid --add-topic foxglove --add-topic physical-ai --add-topic robotics
```
- `gh` が未認証・権限不足なら実行せず、コマンドを報告に残す(人間が実行する)

### 6. 確認とコミット
- README を GitHub 上と同じ見え方で確認する: push 後に `gh browse` は使わず、`gh api repos/raycast-trail/go2-genesis-patrol/readme` で取得できること、GIF のパスが相対パスで正しいことを確認。GIF 2 本のサイズ(MB)と長さ・fps を報告に表で
- `docs/report/`(人間が更新した v3.1: PDF・report.html・`figs/foxglove3d_seed103.jpg`)を内容を変えずに含める
- 1 コミットで push

## 受け入れ条件
- [ ] `docs/media/hero.gif`: 左右同期(末尾のずれ量を報告)、英語ラベル、2 倍速表示、8 MB 以下、ループ
- [ ] `docs/media/v1_v2_v3_seed28.gif`: 3 分割、ラベル、8 MB 以下
- [ ] `docs/media/social_preview.png`: 1280×640
- [ ] README 冒頭に GIF と英語要約、数値が summary.md と一致、日本語の本文は維持、個人情報 grep 0 件
- [ ] リポジトリの説明文とトピックが設定済み(または実行コマンドを報告)
- [ ] `docs/report/` を含めて push 済み、`git status` は `videos/t01_square_baseline.mp4` 以外クリーン
- [ ] `reports/15_readme_showcase.md`(GIF の仕様表、同期の確認方法と結果、README の冒頭の差分、人間がやること: ソーシャルプレビューの登録)

## 調整候補(最大 2 つ)
1. hero.gif が 8 MB を超える: 幅 800 px → fps 10 → 長さを完走の手前で切る、の順
2. 同期がうまくいかない(同じ実行でない、ずれが大きい): 時間で連結する形にする

## 成果物
- `docs/media/hero.gif`、`docs/media/v1_v2_v3_seed28.gif`、`docs/media/social_preview.png`
- `scripts/make_gifs.py`(GIF とプレビュー画像の生成。再現できるように)
- `README.md`、`docs/report/`(更新)
- `reports/15_readme_showcase.md`
