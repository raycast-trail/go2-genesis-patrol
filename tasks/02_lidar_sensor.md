# T02: 疑似 LiDAR(Raycaster)の組み込みと単体テスト

## 目的
Go2 の胴体に 2D LiDAR 相当の Raycaster を取り付け、距離配列を毎ステップ読めるようにする。地面除去を含めて「障害物までの距離」が正しく取れることを、既知配置で検証する。設計書 §3.2。

## CPU(Linux)で確認済みの API(そのまま使ってよい)
```python
pattern = gs.options.sensors.SphericalPattern(fov=(360.0, 0.0), n_points=(72, 1))   # 水平 72 本、5° 刻み
lidar = scene.add_sensor(gs.options.sensors.Raycaster(
    pattern=pattern, entity_idx=robot.idx, link_idx_local=0,      # base リンク
    pos_offset=(0.0, 0.0, 0.15), min_range=0.0, max_range=5.0,
    return_points=True, return_world_frame=True))                 # 地面除去のため点も取る
scene.build(n_envs=...)                                           # add_sensor は build の前
r = lidar.read()                                                  # NamedTuple(distances, points)
d   = torch.as_tensor(r.distances)   # shape (n_envs, 72, 1) → squeeze
pts = torch.as_tensor(r.points)      # shape (n_envs, 72, 1, 3)、world 座標
```
- 角度の並び: `pattern.angles[0]` は **−180° から +175° まで 5° 刻み**。index 0 = 後方、**index 36 = 正面(0°)**、index 18 = 右(−90°)、index 54 = 左(+90°)
- 1 ステップのコスト(CPU, 1 env, points なし): 約 5 ms。Metal は未計測 → 本タスクで計測
- **判明している落とし穴**: 胴体が前傾すると正面のレイが床に当たる(ヒット点 z ≈ 0)。歩行中のピッチ ±10° で 2.5〜5 m 先に偽の障害物が見える。→ **地面除去**: ヒット点の z < 0.05 m のレイは `max_range` に置き換える
- `read()` の戻り値を `np.asarray()` に直接渡すと shape 不整合でエラー。`.distances` / `.points` を個別に取り出す
- 取り付け高さ 0.15 m(base 原点から)で自己遮蔽(脚への当たり)は確認されなかったが、歩行中の脚振りで一時的に当たる可能性はある → min_range は 0.3 に設定して様子を見る

## 手順
1. `go2_env.py` の `Go2Env.__init__` に `lidar_cfg=None` 引数を追加し、`camera_cfg` と同じ位置(`scene.build()` の前)で `self.lidar = self.scene.add_sensor(gs.options.sensors.Raycaster(**lidar_cfg))` を行う。`entity_idx` は `self.robot.idx` で埋める(呼び出し側は robot を知らないため、`lidar_cfg` に `entity_idx` が無ければ自動で入れる)。NOTICE の modified 行を更新
2. `nav/lidar.py` を新規作成:
   - `read_scan(env) -> np.ndarray(72,)`: 距離配列を返す。地面除去(点の z < 0.05 → max_range)と、`min_range` 未満の値の `max_range` 置換を行う
   - `sector_min(scan, n_sectors=12) -> np.ndarray(12,)`: 各セクタの最小距離。セクタ 0 が正面 ±15°、反時計回り
   - `ANGLES_DEG`: 各レイの角度(度)の配列
3. `eval/lidar_test.py` を新規作成(学習不要、方策も不要):
   - `Go2Env(num_envs=1, ..., lidar_cfg=...)` でシーンを作り、**既知の障害物**を置く: 正面 1.3 m に面がくる Box(`gs.morphs.Box(pos=(1.5,0,0.25), size=(0.4,0.4,0.5), fixed=True)`)、右 1.85 m に面がくる Cylinder(`pos=(0,-2.0,0.3), radius=0.15, height=0.6, fixed=True`)。障害物の追加も `scene.build()` の前なので、`Go2Env` に `obstacles=None`(morph のリスト)引数を追加して `add_entity` する
   - 立位を保持したまま 100 ステップ回し(`env.step(torch.zeros(1,12))` でよい。`actions=0` は既定姿勢)、`read_scan` の結果を表示: 正面(idx 36)、右(idx 18)、左(idx 54)、後方(idx 0)、および 1.0 m 未満のヒット一覧
   - 100 ステップの `env.step()+read_scan()` の平均時間を計測(ms)
   - `results/t02_scan.png`: 極座標プロット(距離 vs 角度)に障害物の期待位置を重ねる
4. Metal(`--backend gpu`)と CPU(`--backend cpu`)の両方で実行し、結果が一致するか確認
5. **T01 申し送り対応(20 s エピソード上限)**: `go2_patrol.py` で `cfgs.pkl` を読んだ直後に `env_cfg["episode_length_s"] = args.max_time + 5.0` と上書きし、タイムアウトリセットが巡回中に起きないようにする。あわせて `dones` が立ったときは `infos["time_outs"][0]` を見て「timeout」と「fell」を区別してログに出す。確認: `python go2_patrol.py -e go2-walking --ckpt 100 --waypoints square --max-time 40 --out /tmp/t02_timeout_check.mp4` を実行し、20 s でリセットされず 40 s まで走って `timeout` で終わること(既定方策は旋回できないので到達 1/4 のまま)

## 受け入れ条件
- [ ] Metal で `lidar_test.py` がエラーなく動く
- [ ] 正面距離が 1.24 ± 0.1 m(base が x≈0.06 まで前に出るため 1.3 より少し短い)、右距離が 1.85 ± 0.1 m、左と後方が max_range(5.0)
- [ ] 地面除去後に、障害物以外のレイがすべて max_range
- [ ] 1 ステップ(sim + read)が **10 ms 以下**(Metal)。超える場合は `return_points=False` にして地面除去を「距離 > 床までの幾何距離」で近似する案を報告に書く(実装はしない)
- [ ] `results/t02_scan.png` と `reports/02_lidar_sensor.md`(Metal/CPU の計測表つき)
- [ ] 手順 5 の確認で、既定方策の巡回が 20 s でリセットされず 40 s まで走り、終了理由が `timeout` と表示される

## 調整候補(最大 2 つ)
1. 自己遮蔽が出る場合: `pos_offset` の z を 0.15 → 0.25、`min_range` を 0.3 → 0.4
2. Metal で Raycaster が動かない場合: 障害物の位置は既知なので、`nav/lidar.py` に幾何計算の仮想スキャン(各レイと Box/Cylinder の交点)を実装し、同じ `read_scan` インターフェースで返す。設計書 §9 の代替案。どちらを使ったかをレポートに明記

## 成果物
- `go2_env.py`(lidar_cfg, obstacles 引数)、`nav/lidar.py`、`eval/lidar_test.py`、`go2_patrol.py`(episode_length_s 上書き、timeout/fell の区別)
- `results/t02_scan.png`、`results/t02_timing.csv`
- `reports/02_lidar_sensor.md`
