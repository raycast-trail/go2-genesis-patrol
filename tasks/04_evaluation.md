# T04: 定量評価(20 配置 × 4 条件)— T03 完了後に着手

## 目的
「回避あり/なし」×「方策: 既定(前進のみ)/ 指令範囲拡張」の 2×2 で、巡回成功率・衝突率・所要時間・経路効率を集計する。設計書 §4。

## 手順
1. `eval/run_eval.py`:
   - 引数: `--policies go2-walking:100,go2-patrol:299`、`--avoid both|on|off`、`--seeds 0-19`、`--max-time 60`、`--no-video`(既定)
   - seed 0〜4 は障害物なし(`-1` 相当だが seed は記録)、5〜19 は障害物あり
   - 各エピソードで記録: policy, avoid, seed, n_obstacles, reached(0–4), success(4/4 かつ転倒なし かつ衝突なし), fell, collision, time_to_complete, path_length, path_efficiency(= 直線距離合計 / path_length)
   - 1 エピソードごとに `results/eval/episodes.csv` に追記(途中で落ちても再開できるよう、済みの (policy, avoid, seed) はスキップ)
   - 録画はしない(速度優先)。1 エピソード ≈ 3,000 steps、録画なしなら数十秒の見込み → 80 エピソードで 1 時間以内
2. `eval/summarize.py`: `episodes.csv` → 条件ごとの成功率・衝突率・平均所要時間・平均経路効率の表(`results/eval/summary.csv`、Markdown 表も出力)と、2×2 の棒グラフ(`results/eval/summary.png`。成功率と衝突率の 2 枚)
3. 失敗エピソードのうち代表 2 つ(回避ありで失敗したもの)を再実行して録画(`videos/t04_fail_*.mp4`)、失敗の型(転倒 / 行き止まり / 振動)を分類

## 受け入れ条件
- [ ] 80 エピソードの `episodes.csv`(欠損なし)
- [ ] `summary.csv` / `summary.png`
- [ ] `reports/04_evaluation.md`: 2×2 の表、結果の解釈(回避の効果、方策拡張の効果、交互作用の有無)、失敗の型と件数
- [ ] 期待される傾向(回避ありで衝突率が下がる、拡張方策で成功率が上がる)が出なかった場合は、**出なかった事実をそのまま報告**する(結論をねじ曲げない)

## 成果物
- `eval/run_eval.py`, `eval/summarize.py`
- `results/eval/episodes.csv`, `summary.csv`, `summary.png`
- `reports/04_evaluation.md`
