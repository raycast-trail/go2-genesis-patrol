# T06: 巡回ログの MCAP 書き出し(Foxglove で 3D 可視化)

## 目的
巡回中の LiDAR 点群・胴体姿勢・軌跡・障害物・指令を **MCAP** に書き出し、Foxglove アプリで 3D 表示できるようにする。実機 LiDAR の運用と同じ可視化経路を持つことで、動画の「表現力」と実機への対応の説明に使う。ROS は使わない(`foxglove-sdk` で直接書く)。

## 前提(動作確認済み)
- `pip install foxglove-sdk`(0.30 系)。`requirements.txt` に追加する
- 合成データでの書き出し例が `docs/foxglove_example.py`(このタスクと一緒に置く。`mcap_smoke.py` と同じ内容)。**この書き方をそのまま流用**する: `foxglove.open_mcap(path)` → 各 `*Channel("/topic")` → `channel.log(message, log_time=ns)` → `writer.close()`
- スキーマは `from foxglove import messages as M`(`foxglove.schemas` は deprecated)。`M.Timestamp(sec, nsec)`、`log_time` はナノ秒の int
- Foxglove アプリで開いて、3D パネルの表示フレームを `world` にすると点群・軌跡・障害物が出る(ユーザー確認済み)

## 手順
1. `nav/mcap_logger.py` を新規作成: `McapLogger(path, scene_obstacles)` クラス
   - `__init__`: writer と以下のチャンネルを開く。障害物は `SceneUpdate` で一度だけ出す(Box は `CubePrimitive`、Cylinder は `CylinderPrimitive`、高さ・半径は scene JSON から。色はグレー)
   - `log_step(t, base_pos, base_quat, scan_raw, scan_filtered, hit_points_world, cmd, nav_state)`:
     - `/tf`: `FrameTransform(parent="world", child="base", translation=base_pos, rotation=base_quat)` ※ Genesis の quat は (w, x, y, z) 順なので Foxglove の `Quaternion(x, y, z, w)` に並べ替える
     - `/lidar/scan_raw` と `/lidar/scan`: `LaserScan(frame_id="base", pose=センサ取付(z=0.15), start_angle=-π, end_angle=+175°, ranges=72 個)`。raw と地面除去後の両方
     - `/lidar/points`: 地面除去後のヒット点(max_range 未満のみ)を world 座標の `PointCloud`(xyz float32、`point_stride=12`)
     - `/trajectory`: `PosesInFrame(frame_id="world", poses=これまでの姿勢列)`。毎ステップ全部送ると肥大するので **5 ステップに 1 回**、かつ姿勢は 10 ステップ間隔に間引く
     - `/nav/state`: JSON チャンネル(`foxglove.Channel("/nav/state", message_encoding="json", schema=...)` または `KeyValuePair` でもよい)に `vx, yaw_rate, d_front, avoid_side, committed, reached, min_dist, contact` を数値で。Foxglove の Plot パネルで時系列が描ける
   - `close()`
2. `go2_patrol.py` に `--mcap PATH` を追加。指定時だけ `McapLogger` を使う(既定は無効。評価ループの速度に影響させない)
3. 確認: seed 10(T04 成功例)と seed 12(T04 失敗例 / T05 v2 で成功していれば v2)を `--mcap` 付きで実行し、`results/mcap/t06_seed10.mcap`, `t06_seed12.mcap` を出す。ファイルサイズを記録(60 s で 10〜30 MB 程度の見込み。50 MB を超えるなら `/lidar/scan_raw` を間引く)
4. Foxglove 用レイアウト `docs/foxglove_layout.json` を作る(3D パネル: 表示フレーム world、`/lidar/points` 点サイズ 5・減衰 3 s、`/trajectory` を線で、`/obstacles`;Plot パネル: `/nav/state.vx`, `.yaw_rate`, `.d_front`)。Foxglove アプリで作ってエクスポートしてよい(作業者が GUI を使えない場合は JSON を手書きし、ユーザーに読み込み確認を依頼する旨を報告に書く)
5. `README.md` の「使い方」に `--mcap` と Foxglove での開き方(3 行)を追記

## 受け入れ条件
- [ ] `t06_seed10.mcap` が Foxglove で開け、3D パネルに点群・軌跡・障害物・TF が出る(ユーザー確認。報告にはスクリーンショットの依頼を書く)
- [ ] `/lidar/points` が障害物の表面をなぞっている(地面除去後なので床の点が無い)
- [ ] `/nav/state` の `d_front` が障害物接近時に下がり、`vx` が連動して下がるのが Plot で見える
- [ ] `--mcap` なしの実行速度が T04 と同等(回帰なし)
- [ ] `reports/06_foxglove_mcap.md`(チャンネル一覧、ファイルサイズ、1 ステップあたりの書き出しコスト)

## 成果物
- `nav/mcap_logger.py`、`go2_patrol.py`(`--mcap`)、`docs/foxglove_example.py`、`docs/foxglove_layout.json`、`requirements.txt`
- `results/mcap/t06_seed10.mcap`, `t06_seed12.mcap`(**コミットする**。各 50 MB 以下)
- `reports/06_foxglove_mcap.md`
