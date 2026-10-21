# T13: 3D LiDAR の層を密にする(天板の検出遅れ対策)+ 動画 v3 + README 反映

## 目的
1. T12 §6 の「張り出し物の検出遅れ」を直す。seed 101・118 が 58〜60 s で上限ぎりぎり(seed 101 はテイク 1 が時間切れ)なので、30/30 が非決定性で崩れうる。**垂直視野を ±12°、25 層(1° 刻み)** にして、天板の縁が層の粗さの分だけ奥にずれる問題を解消する
2. 3D の結果を提出動画(v3)と README に反映する
3. レポートは人間が別途書く(`docs/report/` は触らない)

v1/v2/v3 の既存結果・動画(`results/eval_50/`、seed 0〜49、T10/T11 のショット)は変えない。3D は引き続き `--lidar 3d` のときだけ。

## 手順

### 1. 密な層への変更(`nav/lidar.py`)
- `make_lidar_cfg(mode="3d")` のパターンを `SphericalPattern(fov=(360, 24), n_points=(72, 25))`(垂直 −12°〜+12°、1° 刻み)に変更。T12 の 16 層(±30°)は `mode="3d-coarse"` として残す(T12 の結果の再現用)
- 高さ分類・胴体帯・自己ヒット除外は変更しない。地面の層は −12° で 2.06 m 先に着地する(センサ高さ 0.438 m)ので地面分類は従来どおり
- `eval/lidar3d_test.py` を再実行: **テーブルの投影距離が縁(1.50 m)に対して +0.10 m 以内**になること(T12 は 1.79 m)。per-step コストを 16 層と 25 層で比較して表に
- 接近時の検出距離の時系列: seed 101 の 3D 巡回ログからテーブル方位の投影距離と真の縁までの距離を時系列で描く(`results/t13_table_edge_seed101.png`)。16 層(T12 のログ `videos/t12_3d_seed101_log.csv` に方位別距離が無ければ省略し、縁誤差は単体テストの値で代用)

### 2. 再評価
- 30 配置(seed 100〜129)× v3 + 3D(25 層)を `results/eval_3d/episodes.csv` に **追加**(条件名 `3d` → `3d-dense` のように区別。T12 の 2D・16 層の行は残す)。`summarize.py --compare-lidar` を 3 条件(2D / 3D 16 層 / 3D 25 層)に対応
- 受け入れ: 25 層で 成功 30/30、接触 0、**seed 101・118 の所要が 45 s 未満**、成功分の平均所要が 16 層以下
- seed 101 と 103 の 3D を 25 層で再録画(`--camera overhead-close --mcap`)。`videos/raw/t12_3d_seed103_close.mp4` と `results/mcap/t12_3d_seed103.mcap` は **25 層版で上書き**(動画・MCAP の提出素材は最終構成で揃える)。2D 側は変更なし。`results/t12_traj_seed103.png` を 25 層版で描き直し、**タイトルが切れないよう短く**(例: `seed 103: v3 + 2D vs 3D LiDAR`、凡例に「hatched = 低い箱、dashed = テーブル」)

### 3. 動画 v3(`scripts/make_cards.py`, `scripts/make_video.py`)
T11 の 16 ショットの **ショット 12(C5)の後**に次を挿入。合計 129 + 約 26 = 約 155 s(≤ 180 s)。余白検査(`check_margins.py`)は新カードも対象:
| # | 素材 | 長さ | 内容 |
|---|---|---|---|
| 12b | C7(新規カード) | 5 s | 「6. 3D LiDAR: 2D では見えない障害物」本文: 「低い箱(0.15 m)と テーブルの天板(0.32〜0.36 m)は センサ面(0.44 m)の 2D スキャンに映らない」「3D(72 × 25 層)→ 胴体の高さ帯で切って 2D 地図に投影(実機の voxel layer と同じ)」 |
| 12c | t12_2d_seed103_close(2 倍速、先頭 〜8 s)+ B12c | 6 s | 「2D: 低い箱が見えず踏んで転倒(seed 103)」 |
| 12d | t12_3d_seed103_close(2 倍速、先頭 20 s)+ B12d | 10 s | 「3D: 低い箱とテーブルを地図に入れて迂回、完走(seed 103)」 |
| 12e | C8h(新規半カード)+ `figs/result_3d_half.png`(`results/eval_3d/summary.png` から 2D / 3D 25 層の 2 条件を再描画。16 層は図に入れない) | 7 s | 「30 配置(低い箱 + テーブル + 高い障害物)」「成功 3% → 100%、接触 97% → 0%(p < 0.0001)」「追加コスト +1 ms/step」 |
- C6(まとめ)の「限界」行を更新: 「真の姿勢を使用(SLAM なし)、静止障害物、非決定性」はそのまま。1 行目を「実機 Go2 の 自己位置 → 地図・計画 → 速度指令 → 歩行 と同じ 3 層構造をシムで再現(2D → 3D LiDAR)」程度に(長さは余白検査が通る範囲)
- `videos/final/PAI最終課題_3164.mp4` を上書き、`results/t10_contact.png` を更新、長さ・個人情報の確認は T10 と同じ

### 4. README
- 「結果」に 3D の節(30 配置 × 2D / 3D の表、`results/eval_3d/summary.png`)を追加。構成図の説明に「`--lidar 3d` で 3D 点群 → 高さ帯 → 2D 投影」を 1〜2 行
- 再現手順に `--lidar 3d`、`eval/scenes.py --profile mixed`、`eval/run_eval.py --lidar`、`summarize.py --compare-lidar` を追加
- 限界の「2D LiDAR に簡略化」を「3D は垂直 ±12°・25 層の疑似 LiDAR。崖・段差・斜面は未対応」に更新
- 開発ログに T12・T13 の行を追加
- `figs/arch.png` は **変えない**(構成図は 2D/3D 共通。レポート側で説明する)

### 5. コミット
- 1 コミット。`docs/report/` は含めない(人間が後で更新する)

## 受け入れ条件
- [ ] 単体テスト: 25 層でテーブルの投影距離が縁 +0.10 m 以内。コスト表(72 本 / 16 層 / 25 層)
- [ ] 30 配置 × 3D 25 層: 30/30、接触 0、seed 101・118 < 45 s、平均所要 ≤ 16 層。3 条件の表と検定
- [ ] 動画 v3: 60〜180 s、新ショット 12b〜12e が入り、2 倍速表示、余白 ≥ 100 px、個人情報なし
- [ ] README 更新、`git status` クリーン、push 済み
- [ ] `reports/13_lidar3d_dense_integrate.md`: 縁誤差の前後比較、3 条件の表、ショット表 v3、README の変更点

## 調整候補(最大 2 つ)
1. 25 層でも seed 101/118 が 45 s を超える場合: 垂直視野を ±8°・17 層(1° 刻み)に絞る(低い箱は −8° で 2.1 m 先から見える)
2. 動画が 180 s を超える場合: ショット 6(追従、12 s)を 8 s、ショット 9 を 4 s に

## 成果物
- `nav/lidar.py`、`eval/lidar3d_test.py`、`eval/summarize.py`(3 条件)
- `results/eval_3d/`(25 層の行と 3 条件の集計)、`results/t12_lidar3d_test.png`(25 層版。16 層版は `results/t12_lidar3d_test_16.png` に改名して残す)、`results/t12_traj_seed{101,103}.png`、`results/t13_table_edge_seed101.png`
- `videos/t12_3d_seed{101,103}.mp4`、`videos/raw/t12_3d_seed103_close.mp4`、`results/mcap/t12_3d_seed{101,103}.mcap`(25 層版)
- `figs/cards/C7.png, C8h.png, B12c.png, B12d.png`、`figs/result_3d_half.png`、`videos/final/PAI最終課題_3164.mp4`、`results/t10_contact.png`
- `README.md`、`reports/13_lidar3d_dense_integrate.md`
