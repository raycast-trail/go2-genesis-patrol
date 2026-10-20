# T01: 指令範囲を広げた歩行方策の学習と正方形巡回

## 目的
既定例題(前進 0.5 m/s のみ)を、巡回に必要な「前進・減速・停止・旋回」の速度指令に追従する方策に置き換える。設計書 §3.1。

## 前提
- `logs/go2-walking/`(既定例題、101 it)は実現可能性調査で学習済み。無ければ `python go2_train.py -b 4096 --max-iterations 101 -e go2-walking` で再現(約 4 分)
- `go2_train_patrol.py` の `PATROL_COMMAND_CFG`: vx [0.0, 0.8], vy [-0.2, 0.2], ωz [-0.8, 0.8]

## 手順
1. 学習(約 10 分):
   ```bash
   time python go2_train_patrol.py -e go2-patrol -b 4096 --max-iterations 300
   ```
   最後のブロックの `Mean reward`, `Mean episode length`, `rew_tracking_lin_vel`, `rew_tracking_ang_vel`, `Iteration time`, 合計時間を記録
2. 台本録画(指令追従の目視確認)。`go2_record.py` の `SCRIPT` を次に書き換えて実行:
   ```python
   SCRIPT = [(3.0, 0.5, 0, 0), (3.0, 0.5, 0, 0.5), (3.0, 0.5, 0, 0), (3.0, 0.5, 0, -0.5), (2.0, 0.0, 0, 0)]
   ```
   ```bash
   python go2_record.py -e go2-patrol --ckpt 299 --out videos/t01_script.mp4 --follow
   ```
   `fell / reset` が出ないこと。出た場合はどの指令区間で出たかを記録
3. 正方形巡回:
   ```bash
   python go2_patrol.py -e go2-patrol --ckpt 299 --waypoints square --laps 1 --out videos/t01_square.mp4
   ```
   出力の `waypoints reached N/4`、`fell at` の有無、合計シミュレーション秒数を記録。`videos/t01_square_log.csv` から xy 軌跡を `results/t01_square_traj.png` に描く(正方形の目標経路を破線で重ねる)
4. 比較のため、**既定方策**でも同じ巡回を実行(旋回できないはず):
   ```bash
   python go2_patrol.py -e go2-walking --ckpt 100 --waypoints square --laps 1 --out videos/t01_square_baseline.mp4
   ```
   `waypoints reached` を記録(動画は保存するが提出用ではない)

## 受け入れ条件
- [ ] `logs/go2-patrol/model_299.pt` と `cfgs.pkl` が存在
- [ ] 最終イテレーションで `Mean episode length` ≥ 900(20 s エピソードをほぼ転倒なしで完走)
- [ ] 台本録画で `fell / reset` なし
- [ ] 正方形巡回で `waypoints reached 4/4` かつ転倒なし、60 s 以内
- [ ] `results/t01_square_traj.png` が正方形をなぞっている
- [ ] 既定方策の `waypoints reached` が 4 未満(比較として記録。満たさなくても失敗ではない)

## 受け入れ条件を満たせない場合の調整候補(上から順に、最大 2 つ)
1. イテレーション数を 300 → 600(`--max-iterations 600`、約 20 分)
2. `PATROL_COMMAND_CFG` の ωz を [-0.8, 0.8] → [-0.5, 0.5] に縮小し、`go2_patrol.py` の `WaypointFollower(yaw_max=0.5)` も合わせる
3. (参考・未実施でよい)`go2_train.py` の `reward_cfg["reward_scales"]["tracking_ang_vel"]` を 0.2 → 0.5 に上げる

## 成果物
- `logs/go2-patrol/`(コミットしない)、最終 `model_299.pt` と `cfgs.pkl` を `checkpoints/go2-patrol/` にコピーしてコミット
- `videos/t01_script.mp4`, `videos/t01_square.mp4`
- `results/t01_square_traj.png`, `results/t01_metrics.csv`(方策 × 指標の表)
- `reports/01_patrol_policy.md`
