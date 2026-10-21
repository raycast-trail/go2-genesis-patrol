"""
nav/avoid.py — LiDAR スキャンに基づく反応的な障害物回避(反発ベクトル法の簡易版)。

入力: 地面除去後のスキャン (72,)(nav.lidar.read_scan)と、経路追従が出した (vx, ωz)
規則:
  * 正面距離 d_front:
      - front_mode="corridor"(既定): 進路幅 ±w_half の回廊内(|d·sinφ| < w_half, d·cosφ > 0)にあるヒットの
        進行方向距離 d·cosφ の最小値。経路脇(横 0.4 m 以上)の障害物には反応しない
      - front_mode="sectors": 正面 3 セクタ(−45°〜+45°)の最小距離(タスク記載の素朴版。v1)
  * d_front < d_slow: vx を (d_front − d_stop)/(d_slow − d_stop) 倍に減速
  * d_front < d_stop: vx = 0(安全停止)、その場旋回
  * 旋回方向: 正面ヒットのうち最も近いものの横位置と **反対側**(右にあれば左へ)。毎ステップ決め直す。
    ただしその側のセクタ(45°〜135°)が d_stop + side_margin 未満で塞がっていて、反対側の方が空いていれば反対側。
    ヒットがほぼ正面(|横位置| < lat_deadband)のときは前回の側を保持
    (v1 は左右セクタの空き具合だけで決めていたため、正面右の障害物に対して右へ旋回する誤りがあった)
  * 回避項: ωz += side * k_avoid * (1 − d_front/d_slow)
  * ωz の変化率制限: 1 ステップあたり ±rate_limit(急な指令変化で転倒させない)
  * 出力は学習時の指令範囲にクリップ(vx [0, 0.8], ωz [−0.8, 0.8])
学習不要・決定的・説明可能。実機の Nav2 の costmap 回避の代わりになる最小構成。
"""

import numpy as np

from nav.lidar import ANGLES_DEG, sector_min

FRONT_SECTORS = (11, 0, 1)      # −45°〜+45°
LEFT_SECTORS = (2, 3, 4)        # +45°〜+135°
RIGHT_SECTORS = (8, 9, 10)      # −135°〜−45°
_ANG = np.deg2rad(ANGLES_DEG)
_COS, _SIN = np.cos(_ANG), np.sin(_ANG)


class ObstacleAvoider:
    def __init__(self, d_slow=1.0, d_stop=0.45, k_avoid=0.8, rate_limit=0.1, w_half=0.4, side_margin=0.3,
                 side_hysteresis=0.2, lat_deadband=0.05, front_mode="corridor", vx_range=(0.0, 0.8),
                 wz_range=(-0.8, 0.8), front=FRONT_SECTORS, left=LEFT_SECTORS, right=RIGHT_SECTORS):
        self.d_slow, self.d_stop, self.k_avoid, self.rate_limit = d_slow, d_stop, k_avoid, rate_limit
        self.w_half, self.side_margin, self.side_hysteresis = w_half, side_margin, side_hysteresis
        self.lat_deadband = lat_deadband
        self.front_mode = front_mode
        self.vx_range, self.wz_range = vx_range, wz_range
        self.front, self.left, self.right = front, left, right
        self.reset()

    def reset(self):
        self.prev_wz = 0.0
        self.side = 0           # +1 = 左へ回避、−1 = 右へ回避
        self.last = dict(d_front=np.inf, d_left=np.inf, d_right=np.inf, hit_lat=0.0, mode="free")

    def params(self):
        return dict(front_mode=self.front_mode, d_slow=self.d_slow, d_stop=self.d_stop, k_avoid=self.k_avoid,
                    rate_limit=self.rate_limit, w_half=self.w_half, side_margin=self.side_margin,
                    side_hysteresis=self.side_hysteresis, lat_deadband=self.lat_deadband, left=self.left,
                    right=self.right, front=self.front)

    def _front(self, scan, sectors):
        """(d_front, 最近接ヒットの横位置 lat: 正 = 左)"""
        if self.front_mode == "sectors":
            d_front = float(sectors[list(self.front)].min())
            # 最近接の正面レイの横位置
            i = int(np.argmin(np.where(np.abs(ANGLES_DEG) <= 45.0, scan, np.inf)))
            return d_front, float(scan[i] * _SIN[i])
        lon, lat = scan * _COS, scan * _SIN
        mask = (lon > 0.0) & (np.abs(lat) < self.w_half) & (scan < scan.max())
        if not mask.any():
            return np.inf, 0.0
        i = int(np.argmin(np.where(mask, lon, np.inf)))
        return float(lon[i]), float(lat[i])

    def __call__(self, scan, vx, wz):
        scan = np.asarray(scan, dtype=np.float64)
        sectors = sector_min(scan)
        d_front, hit_lat = self._front(scan, sectors)
        d_left = float(sectors[list(self.left)].min())
        d_right = float(sectors[list(self.right)].min())
        mode = "free"
        if d_front < self.d_slow:
            # 旋回方向は毎ステップ、現在の正面ヒットの反対側に決め直す(固定すると、角を曲がる途中で
            # 障害物が左→右へ移ったときに障害物側へ旋回し続けて停止する)。ヒットがほぼ正面(|lat| が小さい)の
            # ときだけ前回の側を保持して左右のばたつきを防ぐ
            if abs(hit_lat) > self.lat_deadband or self.side == 0:
                side = -1 if hit_lat > 0.0 else 1
                # その側が塞がっていて反対側の方が空いていれば反対側
                d_side = d_left if side > 0 else d_right
                d_other = d_right if side > 0 else d_left
                if d_side < self.d_stop + self.side_margin and d_other > d_side + self.side_hysteresis:
                    side = -side
                self.side = side
            if d_front < self.d_stop:
                mode = "stop"
                vx = 0.0
                wz = self.side * self.k_avoid                       # その場旋回
            else:
                mode = "slow"
                vx = vx * (d_front - self.d_stop) / (self.d_slow - self.d_stop)
                wz = wz + self.side * self.k_avoid * (1.0 - d_front / self.d_slow)
        else:
            self.side = 0
        wz = float(np.clip(wz, self.prev_wz - self.rate_limit, self.prev_wz + self.rate_limit))
        wz = float(np.clip(wz, *self.wz_range))
        vx = float(np.clip(vx, *self.vx_range))
        self.prev_wz = wz
        self.last = dict(d_front=d_front, d_left=d_left, d_right=d_right, hit_lat=hit_lat, mode=mode)
        return vx, wz


class ObstacleAvoiderV2(ObstacleAvoider):
    """v2: 回避側の「コミット区間」で振動(停止 → その場旋回 → 回廊が空く → 経路追従が戻す → 再停止)を抑える。

    v1 との差分:
      * 回避が発動して旋回方向 side を決めたら、T_commit(既定 2.0 s。T05 で 1.0 / 1.5 / 2.0 を比較して決定)の間はその側へ旋回し続け、経路追従の ωz を無視する
        (vx は v1 と同じ減速則に従う)
      * コミット中に正面が空いた(d_front ≥ d_slow)ら、残り時間に関わらず T_clear(既定 0.6 s)だけ直進(ωz = 0)
        してから経路追従に戻す(v1 は空いた瞬間に戻していた)
      * コミット中は反対側が空いていても side を変えない。正面 d_front < d_stop かつ回避側のセクタも
        d_stop + side_margin 未満(袋小路)のときだけ反転を許す
      * 直進(clear)中に再び正面に障害物が入ったら、v1 と同じ規則で side を決め直して再コミット
      * コミット中・直進中の vx は、経路追従の vx(目標が真横〜後方だと ≈ 0 になる)ではなく巡航速度 v_clear
        (既定 0.4 m/s)を下限にした値を v1 と同じ減速則にかける(前進しないと障害物の脇を抜けられない)
    """

    def __init__(self, T_commit=2.0, T_clear=1.0, v_clear=0.4, dt=0.02, **kwargs):
        self.T_commit, self.T_clear, self.v_clear, self.dt = T_commit, T_clear, v_clear, dt
        self.n_commit = max(1, int(round(T_commit / dt)))
        self.n_clear = max(0, int(round(T_clear / dt)))
        super().__init__(**kwargs)

    def reset(self):
        super().reset()
        self.commit_left = 0     # コミット残りステップ
        self.clear_left = 0      # 直進残りステップ
        self.n_commits = 0       # 統計用: コミットに入った回数
        self.n_flips = 0         # 統計用: 袋小路で反転した回数
        self.last["committed"] = 0

    def params(self):
        p = super().params()
        p.update(version="v2", T_commit=self.T_commit, T_clear=self.T_clear, v_clear=self.v_clear)
        return p

    def _choose_side(self, hit_lat, d_left, d_right):
        side = -1 if hit_lat > 0.0 else 1
        d_side = d_left if side > 0 else d_right
        d_other = d_right if side > 0 else d_left
        if d_side < self.d_stop + self.side_margin and d_other > d_side + self.side_hysteresis:
            side = -side
        return side

    def __call__(self, scan, vx, wz):
        scan = np.asarray(scan, dtype=np.float64)
        sectors = sector_min(scan)
        d_front, hit_lat = self._front(scan, sectors)
        d_left = float(sectors[list(self.left)].min())
        d_right = float(sectors[list(self.right)].min())
        mode = "free"
        if self.commit_left > 0:
            # --- コミット中 ---
            vx = max(vx, self.v_clear)
            if d_front >= self.d_slow:
                # 正面が空いた → 直進フェーズへ(残り時間に関わらず)
                self.commit_left = 0
                self.clear_left = self.n_clear
                mode = "clear"
                wz = 0.0
            else:
                d_side = d_left if self.side > 0 else d_right
                if d_front < self.d_stop and d_side < self.d_stop + self.side_margin:
                    self.side = -self.side          # 袋小路: 反転を許す
                    self.commit_left = self.n_commit
                    self.n_flips += 1
                if d_front < self.d_stop:
                    mode = "stop"
                    vx = 0.0
                    wz = self.side * self.k_avoid
                else:
                    mode = "slow"
                    vx = vx * (d_front - self.d_stop) / (self.d_slow - self.d_stop)
                    wz = self.side * self.k_avoid * (1.0 - d_front / self.d_slow)   # 経路追従の ωz は無視
                self.commit_left -= 1
        elif self.clear_left > 0:
            # --- 直進フェーズ ---
            vx = max(vx, self.v_clear)
            if d_front < self.d_slow:
                # 新たな障害物 → 側を決め直して再コミット
                self.side = self._choose_side(hit_lat, d_left, d_right)
                self.commit_left = self.n_commit
                self.clear_left = 0
                self.n_commits += 1
                mode = "stop" if d_front < self.d_stop else "slow"
                if mode == "stop":
                    vx, wz = 0.0, self.side * self.k_avoid
                else:
                    vx = vx * (d_front - self.d_stop) / (self.d_slow - self.d_stop)
                    wz = self.side * self.k_avoid * (1.0 - d_front / self.d_slow)
                self.commit_left -= 1
            else:
                mode = "clear"
                wz = 0.0
                self.clear_left -= 1
        else:
            # --- 通常(v1 と同じ発動条件) ---
            if d_front < self.d_slow:
                self.side = self._choose_side(hit_lat, d_left, d_right)
                self.commit_left = self.n_commit
                self.n_commits += 1
                vx = max(vx, self.v_clear)
                if d_front < self.d_stop:
                    mode = "stop"
                    vx, wz = 0.0, self.side * self.k_avoid
                else:
                    mode = "slow"
                    vx = vx * (d_front - self.d_stop) / (self.d_slow - self.d_stop)
                    wz = self.side * self.k_avoid * (1.0 - d_front / self.d_slow)
                self.commit_left -= 1
            else:
                self.side = 0
        wz = float(np.clip(wz, self.prev_wz - self.rate_limit, self.prev_wz + self.rate_limit))
        wz = float(np.clip(wz, *self.wz_range))
        vx = float(np.clip(vx, *self.vx_range))
        self.prev_wz = wz
        committed = 1 if self.commit_left > 0 else (2 if self.clear_left > 0 else 0)
        self.last = dict(d_front=d_front, d_left=d_left, d_right=d_right, hit_lat=hit_lat, mode=mode, committed=committed)
        return vx, wz


def make_avoider(version="v2", **kwargs):
    """回避則のファクトリ。version='v1' はタスク T03 の ObstacleAvoider、'v2' はコミット区間つき"""
    if version == "v1":
        kwargs.pop("T_commit", None)
        kwargs.pop("T_clear", None)
        return ObstacleAvoider(**kwargs)
    if version == "v2":
        return ObstacleAvoiderV2(**kwargs)
    raise ValueError(f"unknown avoid version: {version}")
