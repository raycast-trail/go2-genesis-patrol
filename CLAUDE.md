# CLAUDE.md — go2-genesis-patrol

Physical AI 2026 応用編1 最終課題。Genesis 上で Unitree Go2 を強化学習で歩かせ、その上に疑似 LiDAR を使った巡回・障害物回避のナビゲーション層を載せ、ランダム配置の複数シーンで定量評価する。設計の全体像は `docs/設計書.md`、環境検証の記録は `docs/実現可能性調査.md`。

## 作業の進め方(最重要)

1. タスクは `tasks/NN_*.md` に 1 つずつ書かれている。**番号順に、指定されたものだけ**を実施する。スコープを勝手に広げない
2. 着手前にそのタスクの「受け入れ条件」を読み、最後に必ずその確認コマンドを実行して結果を貼る
3. 完了したら `reports/NN_*.md` に報告を書く。書くこと: 実行したコマンド、計測値(表)、受け入れ条件の判定、変更したファイルと理由、うまくいかなかったこと、次タスクへの申し送り。推測と実測を区別する
4. 仕様が曖昧なときは、最も素直な解釈で進め、**何を仮定したかを報告に明記**する。止まって質問するより、仮定を書いて進める方を優先
5. 受け入れ条件を満たせない場合、タスクに書かれた「調整候補」を **上から最大 2 つまで**試し、それでも駄目なら理由と計測値を報告して止める。それ以上の試行錯誤はしない(人間が判断する)
6. 1 タスク = 1 つの git commit(複数でも可)。コミットメッセージは英語で `T01: train patrol policy (300 it, 4096 env)` のように

## 環境

- macOS(Apple Silicon M1 Max 32GB)、Genesis は **Metal バックエンド**(`gs.init(backend=gs.gpu)` → `gs.metal`, torch device `mps`)
- conda 環境 `py311_genesis`(Python 3.11)。コマンドは必ず `conda activate py311_genesis` 後に実行。`(base)` で実行しない
- パッケージ: genesis-world **1.4.4**(固定)、rsl-rl-lib ≥ 5.0、torch 2.14。`requirements.txt` 参照。**バージョンを変えない**
- Genesis の例題は v1.4.4 tag(commit a649105)由来。`go2_env.py` と `go2_train.py` は NOTICE に記載のとおり Apache-2.0 の派生物。改変するときは NOTICE の「modified:」行を更新
- スクリプトはリポジトリ直下で実行する(`python go2_train_patrol.py ...`)。`logs/` に学習ログ、`videos/` に代表動画、`results/` に評価 CSV と図

## 実測済みの性能(目安)

- 初回実行は JIT コンパイルで 1〜3 分無言になる(正常)
- 学習: 4096 env で約 67,000 steps/s、既定例題 101 it = 約 4 分。300 it なら約 10 分
- 録画: 1280×720 で約 39 steps/s(1 分の動画 = 3,000 steps ≈ 80 秒)
- 無害な警告: `QuadrantsWarning: Assign may lose precision`、`GLD_TEXTURE_INDEX_CUBE_MAP is unloadable`、`qpos0 exceeds joint limits`。これらは対処不要

## API の注意(docs と実装のずれ)

- 録画: `cam.start_recording(save_to_filename=..., fps=...)` → `scene.step()` ごとに自動描画 → `cam.stop_recording()`(引数なし)。docs「latest」の `stop_recording(save_to_filename=...)` は旧 API で TypeError
- `scene.add_camera()` / `scene.add_sensor()` / `scene.add_entity()` は **`scene.build()` の前**に呼ぶ。`Go2Env.__init__` に `camera_cfg` のような差し込み口を足す形で対応する
- `env.base_pos` / `env.base_euler` は `step()` 内で更新されるため、`reset()` 直後は未定義。姿勢は `env.robot.get_pos()` / `get_quat()` から読む(`go2_patrol.py` 参照)
- `base_euler` は度(deg)、`quat_to_xyz(..., degrees=False)` はラジアン
- **エピソード上限**: `go2_env.py` は `episode_length_s=20` を超えると `reset_buf` を立ててリセットする(学習用の仕様)。評価・巡回スクリプトでは `cfgs.pkl` 読込後に `env_cfg["episode_length_s"]` を十分大きく上書きし、`dones` は `infos["time_outs"]` で転倒と区別する(T01 申し送り)
- 疑似 LiDAR: `gs.options.sensors.Raycaster(pattern=gs.options.sensors.SphericalPattern(...), entity_idx=..., link_idx_local=..., pos_offset=..., max_range=..., return_points=False)` を `scene.add_sensor()` で追加し、`sensor.read()` で距離配列。**Metal での動作は未検証**(T02 で確認)

## 制約(提出要件)

- **個人情報を入れない**(要項の明文): 氏名・所属・メールアドレスをコード・コメント・README・コミットメッセージ・動画・図に書かない。git の author 設定(name/email)はグローバル設定のまま(既存の公開リポジトリと同じ扱い。要項で明示的に禁止されていないため)。`git config` を触らない
- 講座の配布教材(講義 PDF、宿題ノートブック、`pai_training` 等)をこのリポジトリに入れない
- リポジトリは public。秘密情報(API キー等)を置かない
- 他のコードを取り込むときはライセンスを確認し、NOTICE に追記する(GPL は不可)

## コード規約

- Python 3.11、型ヒントは任意、docstring は日本語可。関数は小さく、`if __name__ == "__main__":` でスクリプト化
- 乱数は seed を引数で受ける。評価系は必ず seed を記録する
- 計測値は `results/*.csv` に書き、報告には表で転記する。図は `results/*.png`(matplotlib)
- 既存スクリプトの引数名・ログ形式を踏襲する(`-e/--exp-name`, `--ckpt`, `--out`, `--backend`)
