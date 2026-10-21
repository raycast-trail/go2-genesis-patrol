"""
nav/grid_map.py — LiDAR スキャンから作る 2D 占有格子(log-odds)。T09 の v3(地図 + A*)用。

  * 分解能 0.05 m、範囲 x, y ∈ [−2, 4] m(120 × 120 セル)。index は arr[iy, ix]
  * 更新: 地面除去後のヒット点のセルを +0.85、センサからヒット点までのレイ上のセルを −0.4、
    max_range のレイは空きのみ更新。地面除去で max_range に置換されたレイは床に当たった距離までを空きにする
    (レイ上のセルは res/2 間隔のサンプル点で近似。1 セルに 2 点入るので 1 点あたり −0.2)
  * クリップ ±5。占有判定 log-odds > 0.5、未知(0)は通行可として扱う(実機 costmap の慣習)
  * 膨張: 占有セルを Go2 の半径分(既定 0.35 m = 7 セル)膨張した bool 配列を返す
真の姿勢(Genesis の base 位置・yaw)を使う。SLAM はしない。
"""

import math

import numpy as np

from nav.lidar import ANGLES_DEG

_ANG = np.deg2rad(ANGLES_DEG)


class GridMap:
    def __init__(self, res=0.05, xmin=-2.0, xmax=4.0, ymin=-2.0, ymax=4.0, l_hit=0.85, l_miss=0.4, l_clip=5.0,
                 occ_thresh=0.5, max_range=5.0):
        self.res, self.xmin, self.xmax, self.ymin, self.ymax = res, xmin, xmax, ymin, ymax
        self.nx = int(round((xmax - xmin) / res))
        self.ny = int(round((ymax - ymin) / res))
        self.l_hit, self.l_miss, self.l_clip, self.occ_thresh, self.max_range = l_hit, l_miss, l_clip, occ_thresh, max_range
        self.logodds = np.zeros((self.ny, self.nx), dtype=np.float32)
        self.n_updates = 0
        self._disk_cache = {}

    # --- 座標変換 ---
    def to_cell(self, x, y):
        return int(math.floor((x - self.xmin) / self.res)), int(math.floor((y - self.ymin) / self.res))

    def to_world(self, ix, iy):
        return self.xmin + (ix + 0.5) * self.res, self.ymin + (iy + 0.5) * self.res

    def in_bounds(self, ix, iy):
        return 0 <= ix < self.nx and 0 <= iy < self.ny

    # --- 更新 ---
    def update(self, sensor_xy, yaw, scan, raw, pts_world, free_start=None):
        """1 スキャン分の更新。scan: 地面除去後 (72,)、raw: 生距離 (72,)、pts_world: ヒット点 (72, 3) world。
        free_start (72,) を渡すと空き更新をその距離から始める(3D: レイが低い高さにある区間だけ。T13)"""
        sx, sy = float(sensor_xy[0]), float(sensor_xy[1])
        hit = scan < self.max_range
        # レイごとの「空き」の終端距離: ヒットならヒット距離、地面除去なら床までの距離、それ以外は max_range
        free_len = np.where(hit, scan, np.where(raw < self.max_range, raw, self.max_range)).astype(np.float64)
        if free_start is not None:
            free_len = np.minimum(free_len, np.asarray(raw, dtype=np.float64))   # 3D: raw は「低い高さで確認した空き」の終端
        dirs = np.stack([np.cos(yaw + _ANG), np.sin(yaw + _ANG)], axis=1)
        step = self.res / 2.0
        n_samp = int(self.max_range / step) + 1
        s = (np.arange(n_samp) * step)[None, :]                     # (1, n_samp)
        valid = s < (free_len[:, None] - self.res)                  # ヒットセルの手前まで
        if free_start is not None:
            valid &= s >= np.asarray(free_start, dtype=np.float64)[:, None]
        px = sx + dirs[:, 0:1] * s
        py = sy + dirs[:, 1:2] * s
        ix = np.floor((px - self.xmin) / self.res).astype(int)
        iy = np.floor((py - self.ymin) / self.res).astype(int)
        m = valid & (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        np.add.at(self.logodds, (iy[m], ix[m]), -self.l_miss / 2.0)
        if hit.any():
            hx, hy = pts_world[hit, 0], pts_world[hit, 1]
            hix = np.floor((hx - self.xmin) / self.res).astype(int)
            hiy = np.floor((hy - self.ymin) / self.res).astype(int)
            mm = (hix >= 0) & (hix < self.nx) & (hiy >= 0) & (hiy < self.ny)
            np.add.at(self.logodds, (hiy[mm], hix[mm]), self.l_hit)
        np.clip(self.logodds, -self.l_clip, self.l_clip, out=self.logodds)
        self.n_updates += 1

    # --- 判定 ---
    def occupied(self):
        return self.logodds > self.occ_thresh

    def _disk(self, radius_m):
        r = int(math.ceil(radius_m / self.res))
        if r not in self._disk_cache:
            offs = [(dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if dx * dx + dy * dy <= r * r]
            self._disk_cache[r] = offs
        return self._disk_cache[r]

    def inflated(self, radius_m=0.35):
        """占有セルを radius_m だけ膨張した通行不可マスク (ny, nx)"""
        occ = self.occupied()
        out = np.zeros_like(occ)
        if not occ.any():
            return out
        ys, xs = np.nonzero(occ)
        for dx, dy in self._disk(radius_m):
            x2, y2 = xs + dx, ys + dy
            m = (x2 >= 0) & (x2 < self.nx) & (y2 >= 0) & (y2 < self.ny)
            out[y2[m], x2[m]] = True
        return out

    def occupancy_u8(self):
        """Foxglove Grid 用: 0 = 空き、100 = 占有、50 = 未知(log-odds ≈ 0)"""
        p = 1.0 / (1.0 + np.exp(-self.logodds))
        u8 = np.full(self.logodds.shape, 50, dtype=np.uint8)
        u8[self.logodds < -0.5] = 0
        u8[self.logodds > self.occ_thresh] = 100
        return u8

    def save_png(self, path, robot_xy=None, path_xy=None, waypoints=None, obstacles=None, title=None, inflate=0.35):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6.4, 6.4))
        p = 1.0 / (1.0 + np.exp(-self.logodds))
        ax.imshow(1.0 - p, cmap="gray", vmin=0, vmax=1, origin="lower", extent=(self.xmin, self.xmax, self.ymin, self.ymax),
                  interpolation="nearest")
        inf = self.inflated(inflate) & ~self.occupied()
        if inf.any():
            overlay = np.zeros((self.ny, self.nx, 4))
            overlay[inf] = (1.0, 0.5, 0.0, 0.25)
            ax.imshow(overlay, origin="lower", extent=(self.xmin, self.xmax, self.ymin, self.ymax), interpolation="nearest")
        if obstacles:
            for o in obstacles:
                x, y = o["pos"]
                if o["type"] in ("box", "lowbox"):
                    sx, sy = o["size"][0], o["size"][1]
                    ax.add_patch(plt.Rectangle((x - sx / 2, y - sy / 2), sx, sy, fill=False, ec="red", lw=1.0, ls="--"))
                elif o["type"] == "table":
                    st = o["top_size"]
                    ax.add_patch(plt.Rectangle((x - st / 2, y - st / 2), st, st, fill=False, ec="red", lw=1.0, ls=":"))
                else:
                    ax.add_patch(plt.Circle((x, y), o["radius"], fill=False, ec="red", lw=1.0, ls="--"))
        if waypoints is not None:
            w = np.array(waypoints)
            ax.plot(w[:, 0], w[:, 1], "k--", lw=1)
        if path_xy is not None and len(path_xy):
            pp = np.array(path_xy)
            ax.plot(pp[:, 0], pp[:, 1], color="tab:green", lw=2, label="A* path")
        if robot_xy is not None:
            ax.plot(robot_xy[0], robot_xy[1], "o", color="tab:blue", ms=8, label="robot")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(title or f"occupancy grid ({self.n_updates} updates)")
        ax.set_aspect("equal")
        if path_xy is not None or robot_xy is not None:
            ax.legend(loc="upper left", fontsize=8)
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)
