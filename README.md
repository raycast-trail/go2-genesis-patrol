# go2-genesis-patrol

Unitree Go2 の歩行方策を Genesis 上で強化学習し、その上に疑似 LiDAR を用いた巡回・障害物回避のナビゲーション層を載せて、ランダム配置の複数シーンで定量評価するプロジェクト(Physical AI 2026 応用編1 最終課題)。

```
ウェイポイント ─► 経路追従 + LiDAR 回避(古典制御, nav/) ─► 速度指令 (vx, vy, ωz)
                                                              │
                                   歩行方策(RL/PPO, 4096 env 並列学習) ─► 12 関節目標角 ─► PD
                                                              │
                                           Genesis 物理シミュレーション(Go2 + 障害物)
```

## 環境

- macOS Apple Silicon(Metal)で開発。Linux + CUDA でも動く想定
- Python 3.10–3.13、genesis-world 1.4.4、rsl-rl-lib ≥ 5.0

```bash
conda create -n py311_genesis python=3.11 -y
conda activate py311_genesis
pip install -r requirements.txt
```

## 使い方

```bash
# 1. 歩行方策の学習(指令範囲: vx 0–0.8, vy ±0.2, yaw ±0.8)。M1 Max で約 10 分
python go2_train_patrol.py -e go2-patrol -b 4096 --max-iterations 300

# 2. 台本に沿った指令で歩かせて録画(Viewer 不要)
python go2_record.py -e go2-patrol --ckpt 299 --out videos/walk.mp4 --follow

# 3. 正方形巡回(障害物シーン seed 指定、LiDAR 回避あり)
python go2_patrol.py -e go2-patrol --ckpt 299 --waypoints square --seed 3 --avoid --out videos/patrol.mp4

# 4. 定量評価(20 配置 × 4 条件)と集計
python eval/run_eval.py --policies go2-walking:100,go2-patrol:299 --avoid both --seeds 0-19
python eval/summarize.py
```

## 構成

| パス | 内容 |
|---|---|
| `go2_env.py` | Genesis 例題由来の Go2 環境(カメラ / LiDAR / 障害物の差し込み口を追加) |
| `go2_train.py`, `go2_train_patrol.py` | 既定例題の学習 / 指令範囲を広げた学習 |
| `go2_record.py`, `go2_patrol.py` | headless 録画 / ウェイポイント巡回 |
| `nav/` | LiDAR 処理、経路追従、障害物回避 |
| `eval/` | シーン生成、評価ループ、集計 |
| `results/`, `videos/` | 評価結果(CSV, 図)、代表動画 |
| `docs/` | 設計書、実現可能性調査 |
| `tasks/`, `reports/` | 作業タスクの仕様と報告(開発ログ) |

## ライセンス

Apache-2.0。`go2_env.py` と `go2_train.py` は [Genesis](https://github.com/Genesis-Embodied-AI/genesis-world)(Apache-2.0)の例題を改変・複製したもの。詳細は `NOTICE`。
