# T05: 回避則 v2(振動対策)と再評価、統計検定の組み込み

## 目的
T04 で見つかった唯一の失敗型「正面障害物の前で 停止 → その場旋回 → 回廊が空く → 経路追従が戻す → 再停止、の振動」(seed 12 失敗、seed 16 で 25 s 損失)を、回避側の**コミット区間**で抑える。改良前(v1)と改良後(v2)を**同じ 20 配置**で比較し、改良の効果を統計検定つきで示す。これがレポートの「系統的な改良」の柱になる。

## 前提
- T04 の結果(`results/eval/episodes.csv`, `summary.*`)は **v1 として保存したまま触らない**。v2 は別ファイルに出す(`results/eval_v2/`)
- 回避則の切り替えは `--avoid-version {v1,v2}`(既定 v2)。v1 の挙動は完全に再現できること(回帰確認: seed 12 を v1 で再実行して T04 と同じ結果になる)
- 評価は `--backend cpu --no-video`

## 手順
1. `nav/avoid.py` に v2 を追加(v1 のクラスは残す):
   - **コミット区間**: 回避が発動して旋回方向 `side` を決めたら、`T_commit`(既定 1.5 s = 75 ステップ)の間はその側に旋回し続け、経路追従の ωz を無視する(vx は回避則の減速に従う)。コミット中に `d_front` が `d_slow` を超えて正面が空いたら、残り時間に関わらず**さらに `T_clear`(既定 0.6 s)だけ直進**してから経路追従に戻す(「空いた瞬間に戻す」のが振動の原因)
   - コミット中に反対側が明らかに空いている(`side_hysteresis` 超)場合も**側は変えない**(振動の第 2 原因)。ただし正面 `d_front < d_stop` かつ回避側のセクタも `d_stop + side_margin` 未満のときだけ反転を許す(袋小路対策)
   - パラメータ `T_commit`, `T_clear` は引数。既定値は上記
2. 回帰確認: `python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --no-video --seed 12 --avoid --avoid-version v1` が T04 の seed 12 と同じ(未到達、60 s)になること
3. v2 の単体確認: seed 12 と 16 を v2 で実行(録画あり、俯瞰)。seed 12 が成功するか、seed 16 の所要時間が短くなるかを見る。成功しなければ `T_commit` を 1.0 / 2.0 s で試す(最大 2 回)
4. 再評価: `python eval/run_eval.py --policies go2-patrol:299 --avoid on --seeds 0-19 --avoid-version v2 --out results/eval_v2/episodes.csv`(20 本、約 4 分)。既定方策と回避なしは v1 の結果を流用する(回避則の変更は影響しないため)
4b. **再現性の計測**(T04/T06 で観察された CPU バックエンドの非決定性を数字にする): v1 回避あり・拡張方策を同じ 20 配置で**もう 1 回**実行(`results/eval_v1_rerun/episodes.csv`、約 4 分)。T04 の結果と seed ごとに比較し、成功/接触/所要時間が変わった配置の数を報告する。これが「同じ条件でも結果が揺れる幅」で、v1→v2 の差がこの幅より大きいかの判断材料になる
5. `eval/summarize.py` を拡張:
   - `--compare results/eval/episodes.csv results/eval_v2/episodes.csv` で、拡張方策 × 回避あり の v1 と v2 を seed ごとに並べ、成功・接触・所要時間の表を出す
   - **統計**: 対応ありの比較(同じ seed)に **McNemar 正確検定**(成功、接触)、成功率に **Wilson 95% 信頼区間**。scipy は使わず `math.comb` で実装(T04 報告の末尾に使った式でよい)。対象は (a) v1 回避あり vs v1 回避なし、(b) v2 回避あり vs v1 回避あり
   - `results/eval_v2/summary.md` に v1/v2 の 2×2 + 検定結果を出力
6. 代表動画: v2 の seed 12(成功した場合)と、v1/v2 で最も差が出た seed を俯瞰で録画(`videos/t05_v2_seedNN.mp4`)

## 受け入れ条件
- [ ] v1 の回帰確認が一致(seed 12 未到達、所要 60 s、接触 0)
- [ ] v2 で 20 配置の `episodes.csv` が揃い、障害物あり 15 配置の成功率が **v1(14/15)以上**、接触率 0% のまま、転倒 0
- [ ] 成功エピソードの平均所要時間が v1(33.6 s)より短い(振動が減れば短くなるはず。短くならなければその事実を報告)
- [ ] `summary.md` に v1/v2 の表と McNemar / Wilson CI
- [ ] 再現性: v1 の再実行で結果が変わった配置の数と、変わり方(成功↔失敗、所要時間の差)を表で
- [ ] `reports/05_avoid_v2.md`: v2 の規則の説明(v1 との差分)、seed ごとの比較表、検定結果、v2 で新たに悪化した配置があればその分析

## 調整候補(最大 2 つ)
1. `T_commit` 1.5 → 1.0 または 2.0 s
2. `T_clear` 0.6 → 1.0 s

## 成果物
- `nav/avoid.py`(v2 追加)、`go2_patrol.py` / `eval/run_eval.py`(`--avoid-version`)、`eval/summarize.py`(比較・検定)
- `results/eval_v2/`(episodes.csv, summary.md/csv/png, 軌跡図)
- `videos/t05_v2_seed*.mp4`
- `reports/05_avoid_v2.md`
