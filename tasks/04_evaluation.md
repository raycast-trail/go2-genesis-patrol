# T04: 定量評価(20 配置 × 4 条件)— T03 完了後に着手

## 目的
「回避あり/なし」×「方策: 既定(前進のみ)/ 指令範囲拡張」の 2×2 で、巡回成功率・衝突率・所要時間・経路効率を集計する。設計書 §4。

## T03 の申し送りを反映した前提
- 評価はすべて `--backend cpu`。録画はしない(`go2_patrol.py` に `--no-video` を追加し、`camera_cfg=None` で環境を作る)
- **衝突 = 物理接触**(`robot.get_contacts(with_entity=障害物)` が 1 ステップでもあれば `contact=1`)。LiDAR 最小距離 < 0.25 m は「ニアミス」として副指標で併記(T03 で正面押し付けを検出できないことが判明したため。設計書 §4 の定義からの変更として報告に明記)
- **成功 = 4/4 到達 かつ 転倒なし かつ 物理接触なし**(60 s 以内)
- 障害物の個数は `n_placed`(実際に置けた数)を記録。6 個指定でも 5 個になることがある
- 既定方策(go2-walking)は旋回できないので、回避あり/なしに関わらず WP0 止まりになる見込み。それも結果として記録する(2×2 の片側が低いのは想定どおり)
- 要約 CSV は T03 の `results/t03_metrics.csv` と同じ列構成を流用し、`policy`, `avoid`, `success`, `path_length_m`, `path_efficiency`, `min_lidar_m` を追加

## 手順
1. `eval/run_eval.py`:
   - 引数: `--policies go2-walking:100,go2-patrol:299`、`--avoid both|on|off`、`--seeds 0-19`、`--max-time 60`、`--no-video`(既定)
   - seed 0〜4 は障害物なし(`-1` 相当だが seed は記録)、5〜19 は障害物あり
   - 各エピソードで記録: policy, ckpt, avoid, seed, n_placed, reached(0–4), success(上の定義), fell, end_reason, contact(0/1), contact_steps, first_contact_s, near_miss(LiDAR < 0.25 m の有無), min_lidar_m, time_to_complete, path_length_m, path_efficiency(= 直線距離合計 8.0 m / path_length)
   - 1 エピソードごとに `results/eval/episodes.csv` に追記(途中で落ちても再開できるよう、済みの (policy, avoid, seed) はスキップ)
   - 録画はしない(速度優先)。1 エピソード ≈ 3,000 steps、録画なしなら数十秒の見込み → 80 エピソードで 1 時間以内
2. `eval/summarize.py`: `episodes.csv` → 条件ごとの成功率・接触率・ニアミス率・平均所要時間(成功分)・平均経路効率の表(`results/eval/summary.csv`、Markdown 表も出力)と、2×2 の棒グラフ(`results/eval/summary.png`。成功率と接触率の 2 枚)。障害物なし(seed 0–4)とあり(5–19)は分けて集計する
3. 失敗エピソードのうち代表 2 つ(**拡張方策 × 回避あり**で失敗したもの。無ければ最も所要時間が長かったもの)を再実行して録画(`videos/t04_fail_*.mp4`、俯瞰)、失敗の型(転倒 / 行き止まり / 振動 / 接触)を分類。あわせて成功例を 1 つ録画(`videos/t04_success_seedNN.mp4`、最終動画の素材)

## 受け入れ条件
- [ ] 80 エピソードの `episodes.csv`(欠損なし)
- [ ] `summary.csv` / `summary.png`
- [ ] `reports/04_evaluation.md`: 2×2 の表、結果の解釈(回避の効果、方策拡張の効果、交互作用の有無)、失敗の型と件数
- [ ] 期待される傾向(回避ありで接触率が下がる、拡張方策で成功率が上がる)が出なかった場合は、**出なかった事実をそのまま報告**する(結論をねじ曲げない)
- [ ] 所要時間: 80 本で 30 分以内(T03 実測 9〜20 s/本から)。超える場合は原因を報告

## 成果物
- `eval/run_eval.py`, `eval/summarize.py`
- `results/eval/episodes.csv`, `summary.csv`, `summary.png`
- `reports/04_evaluation.md`
