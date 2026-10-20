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

import numpy as np
import torch

import genesis as gs

N_RAYS = 72
ANGLES_DEG = np.arange(-180.0, 180.0, 360.0 / N_RAYS)   # (72,): -180, -175, ..., 175
IDX_BACK, IDX_RIGHT, IDX_FRONT, IDX_LEFT = 0, 18, 36, 54
GROUND_Z = 0.05          # これより低いヒット点は床とみなす [m]

DEFAULT_LIDAR_CFG = dict(
    pos_offset=(0.0, 0.0, 0.15),   # base リンク原点からの取り付け位置
    min_range=0.3,
    max_range=5.0,
    return_points=True,            # 地面除去にヒット点の z が要る
    return_world_frame=True,
)


def make_lidar_cfg(**overrides):
    """Go2Env(lidar_cfg=...) に渡す dict を作る。pattern は gs.init() 後に生成する必要があるためここで作る。"""
    cfg = dict(DEFAULT_LIDAR_CFG)
    cfg.update(overrides)
    cfg.setdefault("pattern", gs.options.sensors.SphericalPattern(fov=(360.0, 0.0), n_points=(N_RAYS, 1)))
    return cfg


def read_scan(env, env_idx=0, ground_z=GROUND_Z):
    """距離配列 (72,) を返す。地面除去と min_range 未満の除去を行う。"""
    r = env.lidar.read()
    max_range = float(env.lidar_cfg.get("max_range", 20.0))
    min_range = float(env.lidar_cfg.get("min_range", 0.0))
    # read() の戻り値は NamedTuple(points, distances)。np.asarray() に直接渡すと shape 不整合になるので個別に取り出す
    d = torch.as_tensor(r.distances).reshape(env.num_envs, N_RAYS)[env_idx].detach().cpu().numpy().astype(np.float64)
    scan = d.copy()
    if r.points is not None:
        pts = torch.as_tensor(r.points).reshape(env.num_envs, N_RAYS, 3)[env_idx].detach().cpu().numpy()
        hit = scan < max_range
        scan[hit & (pts[:, 2] < ground_z)] = max_range
    scan[scan < min_range] = max_range
    return scan


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
