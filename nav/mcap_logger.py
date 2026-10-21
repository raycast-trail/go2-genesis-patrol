"""
nav/mcap_logger.py — 巡回ログを MCAP に書き出す(Foxglove アプリで 3D 表示)。ROS は使わず foxglove-sdk で直接書く。

書き方は docs/foxglove_example.py をそのまま流用:
  foxglove.open_mcap(path) → 各 *Channel("/topic") → channel.log(message, log_time=ns) → writer.close()

チャンネル:
  /obstacles        SceneUpdate   障害物(Box=CubePrimitive, Cylinder=CylinderPrimitive)。開始時に 1 回
  /tf               FrameTransform world → base(Genesis の quat は (w,x,y,z) 順 → Foxglove は (x,y,z,w))
  /lidar/scan_raw   LaserScan     地面除去前の 72 本(frame_id=base、取付 z=0.15)
  /lidar/scan       LaserScan     地面除去後
  /lidar/points     PointCloud    地面除去後のヒット点(max_range 未満のみ)、world 座標 xyz float32
  /trajectory       PosesInFrame  これまでの姿勢列(5 ステップに 1 回送信、姿勢は 10 ステップ間隔に間引き)
  /nav/state        json          vx, yaw_rate, d_front, avoid_side, committed, reached, min_dist, contact(Plot 用)
"""

import json
import math
import time

import numpy as np

import foxglove
from foxglove import Channel, Schema
from foxglove import messages as M
from foxglove.channels import (FrameTransformChannel, LaserScanChannel, PointCloudChannel, PosesInFrameChannel,
                               SceneUpdateChannel)

from nav.lidar import ANGLES_DEG

NAV_STATE_FIELDS = ["vx", "yaw_rate", "d_front", "avoid_side", "committed", "reached", "min_dist", "contact"]
_IDENTITY_Q = M.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)


def ts(t):
    """秒 → Timestamp"""
    return M.Timestamp(sec=int(t), nsec=int((t % 1) * 1e9))


def q_wxyz_to_fg(q):
    """Genesis の (w, x, y, z) → Foxglove の Quaternion(x, y, z, w)"""
    w, x, y, z = (float(v) for v in q)
    return M.Quaternion(x=x, y=y, z=z, w=w)


class McapLogger:
    def __init__(self, path, scene_obstacles, lidar_pos_offset=(0.0, 0.0, 0.15), traj_every=5, traj_stride=10,
                 max_range=5.0):
        self.path = path
        self.writer = foxglove.open_mcap(path, allow_overwrite=True)
        self.tf_ch = FrameTransformChannel("/tf")
        self.scan_raw_ch = LaserScanChannel("/lidar/scan_raw")
        self.scan_ch = LaserScanChannel("/lidar/scan")
        self.pc_ch = PointCloudChannel("/lidar/points")
        self.path_ch = PosesInFrameChannel("/trajectory")
        self.scene_ch = SceneUpdateChannel("/obstacles")
        schema = Schema(name="NavState", encoding="jsonschema",
                        data=json.dumps({"type": "object",
                                         "properties": {k: {"type": "number"} for k in NAV_STATE_FIELDS}}).encode())
        self.nav_ch = Channel("/nav/state", message_encoding="json", schema=schema)
        self.lidar_pose = M.Pose(position=M.Vector3(x=float(lidar_pos_offset[0]), y=float(lidar_pos_offset[1]),
                                                    z=float(lidar_pos_offset[2])), orientation=_IDENTITY_Q)
        self.angles = np.deg2rad(ANGLES_DEG)
        self.max_range = max_range
        self.traj_every, self.traj_stride = traj_every, traj_stride
        self.poses = []          # 間引いた姿勢列
        self.n_steps = 0
        self.n_points = 0
        self.t_spent = 0.0
        self._log_obstacles(scene_obstacles)

    def _log_obstacles(self, obstacles):
        """障害物(eval/scenes.py の spec dict のリスト)を SceneUpdate で 1 回だけ出す。色はグレー"""
        gray = M.Color(r=0.6, g=0.6, b=0.6, a=1.0)
        ents = []
        for i, o in enumerate(obstacles or []):
            x, y = o["pos"]
            if o["type"] == "box":
                sx, sy, sz = o["size"]
                ents.append(M.SceneEntity(frame_id="world", id=f"obs{i}", timestamp=ts(0), cubes=[M.CubePrimitive(
                    pose=M.Pose(position=M.Vector3(x=x, y=y, z=sz / 2), orientation=_IDENTITY_Q),
                    size=M.Vector3(x=sx, y=sy, z=sz), color=gray)]))
            else:
                r, h = o["radius"], o["height"]
                ents.append(M.SceneEntity(frame_id="world", id=f"obs{i}", timestamp=ts(0), cylinders=[M.CylinderPrimitive(
                    pose=M.Pose(position=M.Vector3(x=x, y=y, z=h / 2), orientation=_IDENTITY_Q),
                    size=M.Vector3(x=2 * r, y=2 * r, z=h), bottom_scale=1.0, top_scale=1.0, color=gray)]))
        self.scene_ch.log(M.SceneUpdate(entities=ents), log_time=0)

    def _laser(self, t, ranges):
        return M.LaserScan(timestamp=ts(t), frame_id="base", pose=self.lidar_pose, start_angle=float(self.angles[0]),
                           end_angle=float(self.angles[-1]), ranges=[float(v) for v in ranges], intensities=[])

    def log_step(self, t, base_pos, base_quat, scan_raw, scan_filtered, hit_points_world, cmd, nav_state):
        """1 ステップ分を書く。scan_* が None の間(着地前)は TF と状態だけ書く。base_quat は Genesis の (w,x,y,z)"""
        t0 = time.perf_counter()
        ns = int(t * 1e9)
        pos = M.Vector3(x=float(base_pos[0]), y=float(base_pos[1]), z=float(base_pos[2]))
        rot = q_wxyz_to_fg(base_quat)
        self.tf_ch.log(M.FrameTransform(timestamp=ts(t), parent_frame_id="world", child_frame_id="base",
                                        translation=pos, rotation=rot), log_time=ns)
        if scan_raw is not None:
            self.scan_raw_ch.log(self._laser(t, scan_raw), log_time=ns)
            self.scan_ch.log(self._laser(t, scan_filtered), log_time=ns)
            pts = np.asarray(hit_points_world, dtype=np.float32).reshape(-1, 3)
            self.n_points += len(pts)
            self.pc_ch.log(M.PointCloud(
                timestamp=ts(t), frame_id="world",
                pose=M.Pose(position=M.Vector3(x=0.0, y=0.0, z=0.0), orientation=_IDENTITY_Q),
                point_stride=12,
                fields=[M.PackedElementField(name="x", offset=0, type=M.PackedElementFieldNumericType.Float32),
                        M.PackedElementField(name="y", offset=4, type=M.PackedElementFieldNumericType.Float32),
                        M.PackedElementField(name="z", offset=8, type=M.PackedElementFieldNumericType.Float32)],
                data=pts.tobytes()), log_time=ns)
        if self.n_steps % self.traj_stride == 0:
            self.poses.append(M.Pose(position=pos, orientation=rot))
        if self.n_steps % self.traj_every == 0:
            self.path_ch.log(M.PosesInFrame(timestamp=ts(t), frame_id="world", poses=list(self.poses)), log_time=ns)
        state = {k: float(nav_state.get(k, 0.0)) for k in NAV_STATE_FIELDS}
        state["vx"], state["yaw_rate"] = float(cmd[0]), float(cmd[1])
        for k, v in state.items():
            if not math.isfinite(v):
                state[k] = float(self.max_range) if k in ("d_front", "min_dist") else 0.0   # JSON は inf を書けない
        self.nav_ch.log(state, log_time=ns)
        self.n_steps += 1
        self.t_spent += time.perf_counter() - t0

    def stats(self):
        return dict(steps=self.n_steps, points=self.n_points, total_s=self.t_spent,
                    ms_per_step=1e3 * self.t_spent / max(self.n_steps, 1))

    def close(self):
        self.writer.close()
