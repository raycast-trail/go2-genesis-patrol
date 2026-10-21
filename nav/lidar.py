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


# --- 3D(T12): 垂直 −30°〜+30° を N_LAYERS 層(4° 刻み)。胴体の高さ帯に入る点だけを 72 本の仮想 2D スキャンに投影する ---
N_LAYERS = 16
VFOV_DEG = 60.0
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
    if mode == "3d":
        cfg.setdefault("pattern", gs.options.sensors.SphericalPattern(fov=(360.0, VFOV_DEG), n_points=(N_RAYS, N_LAYERS)))
    else:
        cfg.setdefault("pattern", gs.options.sensors.SphericalPattern(fov=(360.0, 0.0), n_points=(N_RAYS, 1)))
    return cfg       # Raycaster(**cfg) に渡すので余分なキーは入れない。mode は lidar_mode(env) でパターンから判定


def lidar_mode(env):
    """取り付けた LiDAR が 2d か 3d か(パターンの仰角層数で判定)"""
    pat = env.lidar_cfg["pattern"]
    return "3d" if len(pat.angles[1]) > 1 else "2d"


def classify_points(pts, floor_z=0.0, body_top_z=BODY_TOP_Z):
    """点群の高さ分類 (N,): 0 地面 / 1 胴体帯 / 2 頭上"""
    z = pts[..., 2]
    cls = np.full(z.shape, CLS_BODY, dtype=np.int8)
    cls[z < floor_z + GROUND_BAND_Z] = CLS_GROUND
    cls[z > floor_z + body_top_z + BODY_BAND_MARGIN] = CLS_OVERHEAD
    return cls


def read_scan_3d(env, env_idx=0, floor_z=0.0, body_top_z=BODY_TOP_Z):
    """3D パターンの点群を高さ帯で分類し、72 本の仮想 2D スキャンに投影する。
    戻り値: scan2d (72,) 胴体帯の最小水平距離(無ければ max_range)、pts2d (72, 3) その点(world)、raw2d (72,)
            地面を含む全ヒットの最小水平距離(空き更新用)、pts_all (72*16, 3)、cls_all (72*16,)、dist_all (72*16,)"""
    r = env.lidar.read()
    max_range = float(env.lidar_cfg.get("max_range", 20.0))
    d = torch.as_tensor(r.distances).reshape(env.num_envs, N_RAYS, N_LAYERS)[env_idx].detach().cpu().numpy().astype(np.float64)
    pts = torch.as_tensor(r.points).reshape(env.num_envs, N_RAYS, N_LAYERS, 3)[env_idx].detach().cpu().numpy().astype(np.float64)
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
    anyhit = np.where(hit, horiz, np.inf).min(axis=1)
    raw2d = np.where(np.isfinite(anyhit), anyhit, max_range)
    return scan2d, pts2d, raw2d, pts.reshape(-1, 3), cls.reshape(-1), d.reshape(-1)


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
