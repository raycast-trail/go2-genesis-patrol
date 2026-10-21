# T06 報告: 巡回ログの MCAP 書き出し(Foxglove で 3D 可視化)

対象タスク: `tasks/06_foxglove_mcap.md`。実行日 2026-10-21、環境は CLAUDE.md のとおり(M1 Max / `py311_genesis` / genesis-world 1.4.4)。`foxglove-sdk` 0.30.1 を追加インストール(`requirements.txt` に追記)。T05(回避則 v2)は未実施のため、seed 12 は T04 の v1 回避則で書き出した。

## 結論

- `go2_patrol.py --mcap PATH` で、LiDAR(raw / 地面除去後)・点群・TF・軌跡・障害物・ナビ状態を MCAP に書き出せるようにした。書き方は `docs/foxglove_example.py` と同じ(`foxglove.open_mcap` → `*Channel` → `channel.log(msg, log_time=ns)` → `writer.close()`)
- `results/mcap/t06_seed10.mcap`(0.47 MB、22 s)と `t06_seed12.mcap`(1.24 MB、60 s)を出力。見込み(10〜30 MB)より大幅に小さい(SDK が圧縮するため。非圧縮の合計は 2.8 MB / 11.5 MB)
- 書き出しコストは **0.06 ms/step**。`--mcap` なしの実行時間は同一(seed 10: 3.4 s vs 3.4 s)で回帰なし
- Foxglove アプリでの表示は **未確認**(作業者は GUI を使えない)。`docs/foxglove_layout.json` は手書きしたので、読み込み確認とスクリーンショットをお願いしたい(§5)
- 受け入れ条件のうち「点群が障害物表面をなぞる」「d_front と vx の連動」は MCAP をプログラムで読み戻して数値で確認した(§3)

| 受け入れ条件 | 判定 | 実測 |
|---|---|---|
| `t06_seed10.mcap` が Foxglove で開け、点群・軌跡・障害物・TF が出る | ⏳ ユーザー確認待ち | ファイルは `mcap` ライブラリで読み戻せ、全チャンネルのスキーマ・件数が正常(§3)。GUI 表示は未確認 |
| `/lidar/points` が障害物の表面をなぞる(床の点がない) | ✅(数値) | 点の z は 0.35〜0.52 m(センサ高さ 0.44 m 付近)、z < 0.05 の点なし |
| `/nav/state` の d_front 低下時に vx が下がる | ✅(数値) | d_front < 1.0 のステップで vx 平均 0.14、それ以外 0.45(seed 10)。相関 0.72 |
| `--mcap` なしの速度が T04 と同等 | ✅ | seed 10: `--mcap` あり 3.4 s / なし 3.4 s(T04 のバッチ内では 6.4 s、別プロセス条件) |
| 本報告(チャンネル一覧、サイズ、書き出しコスト) | ✅ | §2〜§3 |

## 実行したコマンド

```bash
conda activate py311_genesis
pip install foxglove-sdk                      # 0.30.1
python docs/foxglove_example.py               # API 確認(smoke.mcap 76 KB)
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 10 --avoid --no-video --summary-csv "" --mcap results/mcap/t06_seed10.mcap
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 12 --avoid --no-video --summary-csv "" --mcap results/mcap/t06_seed12.mcap
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 10 --avoid --no-video --summary-csv ""   # 回帰確認(--mcap なし)
pip install mcap                              # 検証の読み戻し用(requirements には入れていない)
```

## 1. 実装(`nav/mcap_logger.py`)

`McapLogger(path, scene_obstacles, lidar_pos_offset, max_range)`:

| トピック | スキーマ | frame | 内容 | 頻度 |
|---|---|---|---|---|
| `/obstacles` | `foxglove.SceneUpdate` | world | Box → `CubePrimitive`、Cylinder → `CylinderPrimitive`。寸法は scene JSON、色はグレー | 開始時 1 回 |
| `/tf` | `foxglove.FrameTransform` | world → base | `robot.get_pos()` / `get_quat()`。Genesis の (w,x,y,z) を Foxglove の `Quaternion(x,y,z,w)` に並べ替え | 毎ステップ(50 Hz) |
| `/lidar/scan_raw` | `foxglove.LaserScan` | base | 地面除去前の 72 本。`pose` は取付位置 z = 0.15、`start_angle` −π、`end_angle` +175° | 着地後(5 ステップ目から)毎ステップ |
| `/lidar/scan` | `foxglove.LaserScan` | base | 地面除去・min_range 除去後 | 同上 |
| `/lidar/points` | `foxglove.PointCloud` | world | 地面除去後のヒット点(max_range 未満のみ)。xyz float32、`point_stride=12` | 同上 |
| `/trajectory` | `foxglove.PosesInFrame` | world | これまでの姿勢列。姿勢は 10 ステップ間隔に間引き | 5 ステップに 1 回 |
| `/nav/state` | json(`NavState` jsonschema) | — | `vx, yaw_rate, d_front, avoid_side, committed, reached, min_dist, contact` | 毎ステップ |

- `log_step(t, base_pos, base_quat, scan_raw, scan_filtered, hit_points_world, cmd, nav_state)`。着地前(`scan_raw=None`)は TF・軌跡・状態だけ書く
- `/nav/state` は JSON なので `inf` を書けない。`d_front` が無限大(正面に何もない)のときは `max_range`(5.0)に置き換えた
- `committed` は T05(回避則 v2)の状態量で、v1 には存在しないため常に 0
- `reached` は「そのステップ開始時点の到達数」。4 つ目に到達した瞬間にループを抜けるので、最終値は 3 になる(成功エピソードでも)
- `stats()` で書き出しに費やした時間と点数を返す。`go2_patrol.py` が `--mcap` 指定時に表示

`nav/lidar.py` には `read_scan_full(env) → (scan, raw, points_world)` を追加し、`read_scan` はこれを呼ぶ形にした(挙動は変わらない)。`go2_patrol.run_patrol(..., mcap=None)` は `mcap` 指定時だけ `McapLogger` を作り、LiDAR 読み出し後の姿勢と一緒に `log_step` を呼ぶ。

## 2. ファイルサイズと書き出しコスト

| ファイル | seed | 条件 | sim 秒 | ステップ | 点数 | サイズ | 非圧縮合計 | 書き出し [ms/step] | wall [s] |
|---|---|---|---|---|---|---|---|---|---|
| `results/mcap/t06_seed10.mcap` | 10 | 成功例(T04) | 22.1 | 1107 | 14,150 | **0.47 MB** | 2.8 MB | 0.06 | 3.4 |
| `results/mcap/t06_seed12.mcap` | 12 | 失敗例(T04、v1 回避則) | 60.0 | 3000 | 38,596 | **1.24 MB** | 11.5 MB | 0.06 | 8.5 |

チャンネル別(メッセージ数 / 非圧縮バイト):

| トピック | seed 10 | seed 12 |
|---|---|---|
| `/obstacles` | 1 / 0.00 MB | 1 / 0.00 MB |
| `/tf` | 1107 / 0.10 MB | 3000 / 0.27 MB |
| `/trajectory` | 222 / 0.86 MB | 600 / **6.22 MB** |
| `/nav/state` | 1107 / 0.20 MB | 3000 / 0.54 MB |
| `/lidar/scan_raw` | 1102 / 0.70 MB | 2995 / 1.91 MB |
| `/lidar/scan` | 1102 / 0.70 MB | 2995 / 1.91 MB |
| `/lidar/points` | 1102 / 0.25 MB | 2995 / 0.67 MB |

- 最大は `/trajectory`(姿勢列を毎回全部送るため二次関数的に増える)。60 s でも 6 MB(非圧縮)なので間引きはこのままでよい。50 MB の閾値には遠く、`/lidar/scan_raw` の間引きは不要
- 書き出し 0.06 ms/step は、`env.step` + LiDAR(CPU で約 2 ms)に対して無視できる

## 3. 内容の検証(`mcap` ライブラリで読み戻し)

- 全 7 トピックがスキーマ付きで読め、時刻範囲は seed 10 が 22.12 s、seed 12 が 59.98 s
- **点群の z**: seed 10 の先頭 3 フレームの全点で min 0.349、max 0.516、mean 0.445 m。センサ高さ(base 約 0.29 + 0.15)付近に収まり、床(z < 0.05)の点は無い。障害物の高さ 0.6〜0.7 m の側面に当たった点だけが残っていることと整合
- **`/nav/state` の連動**: seed 10 で d_front < 1.0 m のステップが 423/1107。そのときの vx 平均 0.14 m/s、正面が空いているときは 0.45 m/s。`vx` と `min(d_front, 1.0)` の相関 0.72(seed 12 は 0.62)。Plot パネルでは `d_front` が 1.0 を割ると `vx` が落ちる様子が見えるはず
- `min_dist` の最小値 0.40 m(seed 10)、0.38 m(seed 12)。`contact` は両方 0
- seed 12 は今回 3/4(T04 評価時は 2/4、録画時も 2/4)。T04 で記した CPU バックエンドの非決定性(所要時間が数秒ずれる)がここでも出た。失敗の型(正面障害物の前での振動)は同じ

## 4. Foxglove レイアウト(`docs/foxglove_layout.json`)

GUI が使えないため手書き。構成:
- 3D パネル(`3D!go2patrol`): 表示フレーム `world`、`/lidar/points` 点サイズ 5・減衰 3 s(オレンジ)、`/trajectory` を線(青、幅 0.04)、`/obstacles`、`/lidar/scan`(緑)、`/lidar/scan_raw` は非表示、world グリッド 8 m
- Plot パネル(`Plot!navstate`): `/nav/state.vx`, `.yaw_rate`, `.d_front`(y 0〜5)
- Plot パネル(`Plot!navstate2`): `/nav/state.min_dist`, `.contact`, `.reached`
- 配置: 左 65% に 3D、右に Plot 2 段

Foxglove のレイアウト JSON はバージョンでキー名が変わることがあるので、読み込めない場合はパネルを手で作る(3D パネルの表示フレームを `world` にし、上記トピックを有効化するだけ)。

## 5. ユーザーへの確認依頼

1. Foxglove アプリで `results/mcap/t06_seed10.mcap` を開き(Open local file)、`docs/foxglove_layout.json` を Layout → Import で読み込む。読み込めない場合は 3D パネルの表示フレームを `world` にして `/lidar/points`, `/trajectory`, `/obstacles`, `/tf` を表示
2. 3D パネルに「点群が障害物の側面をなぞる」「軌跡が正方形に沿う」「base フレームが動く」ことを確認し、**スクリーンショットを 1 枚**(最終動画・レポート用)
3. Plot パネルで `/nav/state.d_front` が下がるときに `.vx` が下がることを確認
4. 気になる点(点群の色・大きさ、軌跡の太さなど)があれば `docs/foxglove_layout.json` を調整する

## 変更したファイルと理由

| ファイル | 変更 |
|---|---|
| `nav/mcap_logger.py` | **新規**。§1 |
| `nav/lidar.py` | `read_scan_full()` を追加(ヒット点の world 座標を返す)。`read_scan` は内部でこれを呼ぶ |
| `go2_patrol.py` | `run_patrol(..., mcap=None)`、CLI `--mcap PATH`。指定時だけ `McapLogger` を使う。戻り値に `mcap_stats` |
| `docs/foxglove_example.py` | タスクと一緒に置かれた合成データの書き出し例(そのまま。本タスクでこの書き方を流用) |
| `docs/foxglove_layout.json` | **新規**。§4 |
| `README.md` | 使い方 5 として `--mcap` と Foxglove での開き方を追記 |
| `requirements.txt` | `foxglove-sdk>=0.30` を追記 |
| `results/mcap/t06_seed10.mcap`, `t06_seed12.mcap` | 成果物(0.47 MB / 1.24 MB、コミット) |
| `tasks/06_foxglove_mcap.md` | 本タスクの仕様(作業者作成)を本コミットに含めた |

## 仮定したこと

- `committed` は T05 未実施のため常に 0(T05 実施後に v2 の状態を入れる)
- `/lidar/scan` の `pose` は base フレーム内の取付位置(z = 0.15)で、`frame_id="base"` とした(例題と同じ)
- 点群は「地面除去後の max_range 未満の点」のみ。max_range に置換されたレイは点を出さない
- `/nav/state` の `d_front` が無限大のときは 5.0(max_range)に置換
- 軌跡の間引き(5 ステップに 1 回送信、姿勢 10 ステップ間隔)はタスク指定どおり
- seed 12 は T05 が未実施のため v1 回避則で出力(タスクの「v2 で成功していれば v2」は該当せず)
- 検証用の `mcap` パッケージは requirements.txt に入れていない(実行には不要)
- `tasks/05_avoid_v2.md` は未着手のため未コミット(作業ディレクトリに残っている)

## うまくいかなかったこと

- Foxglove アプリでの表示確認ができていない(GUI 不可)。レイアウト JSON は手書きで、読み込めない可能性がある
- seed 12 の結果が実行ごとに 2/4 と 3/4 で揺れる(非決定性、T04 と同じ)

## 次タスクへの申し送り

1. T05 を実施したら `nav_state["committed"]` に v2 のコミット状態を入れ、seed 12 を v2 で書き出し直す(`t06_seed12.mcap` を上書き)
2. `run_eval.py` には `--mcap` を付けていない(評価の速度優先)。必要なら `run_patrol(mcap=...)` を 1 行足すだけ
3. 最終動画では Foxglove の 3D パネルの画面録画(点群 + 軌跡 + 障害物)を「実機 LiDAR と同じ可視化経路」として使える。Plot の `d_front` / `vx` は回避の瞬間の説明に使える
4. `/trajectory` は毎回全姿勢を送るため長時間(数分)の記録では肥大する。その場合は `traj_every` を大きくするか、直近 N 姿勢だけにする
