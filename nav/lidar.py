"""
nav/lidar.py — Go2 胴体に付けた疑似 2D LiDAR(Genesis Raycaster)の読み出しと前処理。

構成(go2_env.Go2Env の lidar_cfg で指定):
  SphericalPattern(fov=(360, 0), n_points=(72, 1)) → 水平 72 本、5° 刻み
  角度の並び: index 0 = −180°(後方)、index 36 = 0°(正面)、index 18 = −90°(右)、index 54 = +90°(左)

前処理(read_scan):
  * 地面除去: 胴体が前傾するとレイが床に当たり 2.5〜5 m 先に偽の障害物が見える → ヒット点の world z < GROUND_Z のレイは max_range に置換
  * 近接除去: min_range 未満の値(脚への自己遮蔽など)は max_range に置換

実機 Go2 の LiDAR(3D)に対して「2D スキャンに落とした」近似であることに注意。
"""

import math

import numpy as np
import torch

import genesis as gs

N_RAYS = 72
ANGLES_DEG = np.arange(-180.0, 180.0, 360.0 / N_RAYS)   # (72,): -180, -175, ..., 175
IDX_BACK, IDX_RIGHT, IDX_FRONT, IDX_LEFT = 0, 18, 36, 54
GROUND_Z = 0.05          # これより低いヒット点は床とみなす [m]

DEFAULT_LIDAR_CFG = dict(
    pos_offset=(0.0, 0.0, 0.15),   # base リンク原点からの取り付け位置
    min_range=0.0,                 # T02 では 0.3 だったが、衝突判定(< 0.25 m)に近接ヒットが要るため 0 に(T03)
    max_range=5.0,
    return_points=True,            # 地面除去にヒット点の z が要る
    return_world_frame=True,
)


# --- 3D(T12/T13): 胴体の高さ帯に入る点だけを 72 本の仮想 2D スキャンに投影する ---
# "3d"(既定、T12 の構成): 垂直 −30°〜+30° を 16 層(4° 刻み)。混合 30 配置で 30/30・接触 0・平均 27.5 s(T12/T13)
# "3d-dense"(T13 の試作): ±12° を 1° 刻み(25 層、天板の縁の検出遅れ対策)+ 下向きの粗い層 −30, −26, −22, −18, −14°
#   (5 層)= 30 層。縁誤差は 0.37 → 0.03 m に改善したが、テーブルの脇で下層の反応的回避が減速する時間が増えて
#   所要時間が伸びた(29/30、平均 30.6 s)ため既定にはしていない
# "3d-dense-only"(T13 の初回案): ±12°、25 層のみ。−12° の層が 1.35 m より近い低い箱の上を通り過ぎて箱が見えなくなり、
#   空き更新で地図から消えた(低い箱に接触 20/30)。比較用に残す
ELEV_DENSE = [float(a) for a in range(-12, 13)]
ELEV_STEEP = [-30.0, -26.0, -22.0, -18.0, -14.0]
LAYERS = {"3d": ("fov", (60.0, 16)), "3d-dense": ("angles", ELEV_STEEP + ELEV_DENSE), "3d-dense-only": ("angles", ELEV_DENSE)}
N_LAYERS = 16          # 互換用(T12)。実際の層数はパターンから lidar_layers(env) で取る
VFOV_DEG = 60.0
LOW_H = 0.10           # 空き更新を許すレイの高さの上限 [m](低い箱 0.15 m より下を通ったレイだけが「空き」を主張できる)
GROUND_BAND_Z = 0.05            # 床面 + 0.05 未満は地面
BODY_TOP_Z = 0.39               # 歩行中の胴体最高点(T12 手順 1 の実測 0.390)
BODY_BAND_MARGIN = 0.10         # 胴体帯の上限 = BODY_TOP_Z + 0.10 = 0.49。それより上は頭上(無視)
CLS_GROUND, CLS_BODY, CLS_OVERHEAD, CLS_NOHIT, CLS_SELF = 0, 1, 2, 3, 4
# 自機の footprint(胴体フレーム、T12 手順 1 の AABB: x −0.42..0.30、y ±0.18)+ 余裕 0.05。下向きレイが自分の脚・股関節に当たる点を除く
SELF_X = (-0.47, 0.35)
SELF_Y = (-0.23, 0.23)


def make_lidar_cfg(mode="2d", **overrides):
    """Go2Env(lidar_cfg=...) に渡す dict を作る。pattern は gs.init() 後に生成する必要があるためここで作る。
    mode="2d": 水平 72 本(既定、v1/v2/v3 の評価と同じ)。mode="3d": 72 × 16 層(T12)"""
    cfg = dict(DEFAULT_LIDAR_CFG)
    cfg.update(overrides)
    if mode in LAYERS:
        kind, spec = LAYERS[mode]
        if kind == "fov":
            cfg.setdefault("pattern", gs.options.sensors.SphericalPattern(fov=(360.0, spec[0]), n_points=(N_RAYS, spec[1])))
        else:
            cfg.setdefault("pattern", gs.options.sensors.SphericalPattern(angles=(list(ANGLES_DEG), list(spec))))
    else:
        cfg.setdefault("pattern", gs.options.sensors.SphericalPattern(fov=(360.0, 0.0), n_points=(N_RAYS, 1)))
    return cfg       # Raycaster(**cfg) に渡すので余分なキーは入れない。mode は lidar_mode(env) でパターンから判定


def lidar_layers(env):
    """取り付けた LiDAR の仰角層数(2D なら 1)"""
    return int(len(env.lidar_cfg["pattern"].angles[1]))


def lidar_mode(env):
    """取り付けた LiDAR が 2d / 3d(16 層)/ 3d-dense(30 層)/ 3d-dense-only(25 層)か(仰角層数で判定)"""
    n = lidar_layers(env)
    return {1: "2d", 16: "3d", 25: "3d-dense-only", 30: "3d-dense"}.get(n, "3d")


def classify_points(pts, floor_z=0.0, body_top_z=BODY_TOP_Z):
    """点群の高さ分類 (N,): 0 地面 / 1 胴体帯 / 2 頭上"""
    z = pts[..., 2]
    cls = np.full(z.shape, CLS_BODY, dtype=np.int8)
    cls[z < floor_z + GROUND_BAND_Z] = CLS_GROUND
    cls[z > floor_z + body_top_z + BODY_BAND_MARGIN] = CLS_OVERHEAD
    return cls


def read_scan_3d(env, env_idx=0, floor_z=0.0, body_top_z=BODY_TOP_Z, clear_policy="auto"):
    """3D パターンの点群を高さ帯で分類し、72 本の仮想 2D スキャンに投影する。
    戻り値: scan2d (72,) 胴体帯の最小水平距離(無ければ max_range)、pts2d (72, 3) その点(world)、
            free_len2d (72,) 空き更新の終端距離、pts_all (N, 3)、cls_all (N,)、dist_all (N,)、free_start2d (72,) 空き更新の開始距離
    空き更新(GridMap.update)の方針 clear_policy:
      "all"(16 層の既定 = T12 と同じ): 地面を含む全ヒットの最小水平距離まで空き(free_start なし)
      "low"(30 層・25 層の既定): 「レイの高さが LOW_H 以下になった区間」だけ空き。密な ±12° 帯では低い箱の上を通るレイが
            多く、全ヒット方式だと箱が地図から消えるため(T13)
      "auto": 層数 16 なら "all"、それ以外は "low"""
    r = env.lidar.read()
    max_range = float(env.lidar_cfg.get("max_range", 20.0))
    n_layers = lidar_layers(env)
    d = torch.as_tensor(r.distances).reshape(env.num_envs, N_RAYS, n_layers)[env_idx].detach().cpu().numpy().astype(np.float64)
    pts = torch.as_tensor(r.points).reshape(env.num_envs, N_RAYS, n_layers, 3)[env_idx].detach().cpu().numpy().astype(np.float64)
    hit = d < max_range
    cls = classify_points(pts, floor_z, body_top_z)
    cls[~hit] = CLS_NOHIT
    # センサ位置(world): ヒット点とレイ距離から逆算せず、base 位置 + 取付高さで近似(xy は base と同じ)
    base = env.robot.get_pos()[env_idx].detach().cpu().numpy().astype(np.float64)
    dx, dy = pts[..., 0] - base[0], pts[..., 1] - base[1]
    horiz = np.hypot(dx, dy)                                               # (72, 16) 水平距離
    # 自己ヒット: 胴体フレームに回して footprint 内の点を除外
    from genesis.utils.geom import quat_to_xyz
    yaw = float(quat_to_xyz(env.robot.get_quat(), rpy=True, degrees=False)[env_idx, 2])
    c, s_ = math.cos(-yaw), math.sin(-yaw)
    bx, by = c * dx - s_ * dy, s_ * dx + c * dy
    self_hit = hit & (bx > SELF_X[0]) & (bx < SELF_X[1]) & (by > SELF_Y[0]) & (by < SELF_Y[1]) & (cls != CLS_GROUND)
    cls[self_hit] = CLS_SELF
    body = cls == CLS_BODY
    hd = np.where(body, horiz, np.inf)
    k = np.argmin(hd, axis=1)                                             # 各方位で最も近い胴体帯の層
    scan2d = hd[np.arange(N_RAYS), k]
    scan2d = np.where(np.isfinite(scan2d), scan2d, max_range)
    pts2d = pts[np.arange(N_RAYS), k]
    pts2d[scan2d >= max_range] = 0.0
    if clear_policy == "auto":
        clear_policy = "all" if n_layers == 16 else "low"
    if clear_policy == "all":
        anyhit = np.where(hit, horiz, np.inf).min(axis=1)
        raw2d = np.where(np.isfinite(anyhit), anyhit, max_range)
        return scan2d, pts2d, raw2d, pts.reshape(-1, 3), cls.reshape(-1), d.reshape(-1), None
    # 空き更新の区間: 下向きの層 e について、レイが z ≤ LOW_H になる水平距離 d_low = (sensor_z − LOW_H)/tan|e| から
    # ヒット(地面を含む)までの区間 [d_low, d_hit] を「低い高さで確認した空き」とする。方位ごとに
    # free_start = 確認できた層の d_low の最小、free_len = その層の d_hit の最大(確認できた層が無ければ 0 = 更新しない)
    elev = np.deg2rad(np.asarray(torch.as_tensor(env.lidar_cfg["pattern"].angles[1]).cpu().numpy(), dtype=np.float64))
    sensor_z = base[2] + float(env.lidar_cfg.get("pos_offset", (0, 0, 0.15))[2])
    down = elev < -1e-6
    d_low = np.full(len(elev), np.inf)
    d_low[down] = np.maximum(0.0, (sensor_z - LOW_H) / np.tan(-elev[down]))
    d_hit = np.where(hit, horiz, max_range)                                # (72, L)
    verified = down[None, :] & (d_hit >= d_low[None, :])
    free_len2d = np.where(verified.any(axis=1), np.where(verified, d_hit, 0.0).max(axis=1), 0.0)
    free_start2d = np.where(verified.any(axis=1), np.where(verified, d_low[None, :], np.inf).min(axis=1), 0.0)
    return scan2d, pts2d, free_len2d, pts.reshape(-1, 3), cls.reshape(-1), d.reshape(-1), free_start2d


def read_scan_full(env, env_idx=0, ground_z=GROUND_Z):
    """(scan, raw, points) を返す。scan は地面除去・min_range 除去後の距離 (72,)、raw は生の距離 (72,)、
    points はヒット点の world 座標 (72, 3)(return_points=False のときは None)。"""
    r = env.lidar.read()
    max_range = float(env.lidar_cfg.get("max_range", 20.0))
    min_range = float(env.lidar_cfg.get("min_range", 0.0))
    # read() の戻り値は NamedTuple(points, distances)。np.asarray() に直接渡すと shape 不整合になるので個別に取り出す
    d = torch.as_tensor(r.distances).reshape(env.num_envs, N_RAYS)[env_idx].detach().cpu().numpy().astype(np.float64)
    scan = d.copy()
    pts = None
    if r.points is not None:
        pts = torch.as_tensor(r.points).reshape(env.num_envs, N_RAYS, 3)[env_idx].detach().cpu().numpy()
        hit = scan < max_range
        scan[hit & (pts[:, 2] < ground_z)] = max_range
    scan[scan < min_range] = max_range
    return scan, d, pts


def read_scan(env, env_idx=0, ground_z=GROUND_Z, return_raw=False):
    """距離配列 (72,) を返す。地面除去と min_range 未満の除去を行う。return_raw=True なら (scan, raw) を返す。"""
    scan, d, _ = read_scan_full(env, env_idx=env_idx, ground_z=ground_z)
    return (scan, d) if return_raw else scan


def sector_min(scan, n_sectors=12):
    """各セクタの最小距離 (n_sectors,)。セクタ 0 が正面 ±(180/n_sectors)°、以降反時計回り(左回り)。"""
    width = 360.0 / n_sectors
    idx = np.floor((ANGLES_DEG + width / 2.0) / width).astype(int) % n_sectors
    out = np.full(n_sectors, np.inf)
    for s in range(n_sectors):
        out[s] = scan[idx == s].min()
    return out


def sector_angles_deg(n_sectors=12):
    """各セクタの中心角(度)。sector_min の添字と対応"""
    return (np.arange(n_sectors) * 360.0 / n_sectors + 180.0) % 360.0 - 180.0
