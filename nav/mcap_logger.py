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
from foxglove.channels import (FrameTransformChannel, GridChannel, LaserScanChannel, PointCloudChannel, PosesInFrameChannel,
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
        self.grid_ch = GridChannel("/map")                 # v3 の占有格子(1 s ごと)
        self.pc3d_ch = PointCloudChannel("/lidar/points3d")  # T12: 3D 点群(高さ分類つき)
        self.imu_ch = Channel("/imu", message_encoding="json", schema=Schema(
            name="Imu", encoding="jsonschema",
            data=json.dumps({"type": "object", "properties": {
                "frame_id": {"type": "string"},
                "angular_velocity": {"type": "object", "properties": {k: {"type": "number"} for k in "xyz"}},
                "linear_acceleration": {"type": "object", "properties": {k: {"type": "number"} for k in "xyz"}}}}).encode()))
        self.plan_ch = PosesInFrameChannel("/plan")        # v3 の A* 経路
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
            if o["type"] in ("box", "lowbox"):
                sx, sy, sz = o["size"]
                ents.append(M.SceneEntity(frame_id="world", id=f"obs{i}", timestamp=ts(0), cubes=[M.CubePrimitive(
                    pose=M.Pose(position=M.Vector3(x=x, y=y, z=sz / 2), orientation=_IDENTITY_Q),
                    size=M.Vector3(x=sx, y=sy, z=sz), color=gray)]))
            elif o["type"] == "table":
                st, zb, th, ins = o["top_size"], o["top_z_bottom"], o["thickness"], o.get("leg_inset", 0.1)
                ents.append(M.SceneEntity(frame_id="world", id=f"obs{i}", timestamp=ts(0),
                    cubes=[M.CubePrimitive(pose=M.Pose(position=M.Vector3(x=x, y=y, z=zb + th / 2), orientation=_IDENTITY_Q),
                                           size=M.Vector3(x=st, y=st, z=th), color=gray)],
                    cylinders=[M.CylinderPrimitive(pose=M.Pose(position=M.Vector3(x=x + sx * ins, y=y + sy * ins, z=zb / 2),
                                                               orientation=_IDENTITY_Q),
                                                   size=M.Vector3(x=2 * o["leg_radius"], y=2 * o["leg_radius"], z=zb),
                                                   bottom_scale=1.0, top_scale=1.0, color=gray)
                               for sx in (-1, 1) for sy in (-1, 1)]))
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

    def log_grid(self, t, gmap, path_xy=None):
        """占有格子を Foxglove Grid(uint8: 0 空き / 50 未知 / 100 占有)で書く。原点は格子の (xmin, ymin)"""
        ns = int(t * 1e9)
        u8 = gmap.occupancy_u8()                           # (ny, nx)、row = y
        self.grid_ch.log(M.Grid(
            timestamp=ts(t), frame_id="world",
            pose=M.Pose(position=M.Vector3(x=gmap.xmin, y=gmap.ymin, z=0.0), orientation=_IDENTITY_Q),
            column_count=gmap.nx, cell_size=M.Vector2(x=gmap.res, y=gmap.res),
            row_stride=gmap.nx, cell_stride=1,
            fields=[M.PackedElementField(name="occupancy", offset=0, type=M.PackedElementFieldNumericType.Uint8)],
            data=u8.tobytes()), log_time=ns)
        if path_xy:
            self.plan_ch.log(M.PosesInFrame(timestamp=ts(t), frame_id="world", poses=[
                M.Pose(position=M.Vector3(x=float(x), y=float(y), z=0.05), orientation=_IDENTITY_Q) for x, y in path_xy]),
                log_time=ns)

    def log_points3d(self, t, pts_world, cls):
        """3D 点群(world)。fields: x, y, z (float32) + cls (uint8: 0 地面 / 1 胴体帯 / 2 頭上 / 3 ヒットなし / 4 自機)。ヒットなしは除く"""
        m = cls != 3
        p = np.asarray(pts_world, dtype=np.float32)[m]
        c = np.asarray(cls, dtype=np.uint8)[m]
        buf = np.zeros(len(p), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("cls", "u1")])
        buf["x"], buf["y"], buf["z"], buf["cls"] = p[:, 0], p[:, 1], p[:, 2], c
        self.pc3d_ch.log(M.PointCloud(
            timestamp=ts(t), frame_id="world",
            pose=M.Pose(position=M.Vector3(x=0.0, y=0.0, z=0.0), orientation=_IDENTITY_Q),
            point_stride=13,
            fields=[M.PackedElementField(name="x", offset=0, type=M.PackedElementFieldNumericType.Float32),
                    M.PackedElementField(name="y", offset=4, type=M.PackedElementFieldNumericType.Float32),
                    M.PackedElementField(name="z", offset=8, type=M.PackedElementFieldNumericType.Float32),
                    M.PackedElementField(name="cls", offset=12, type=M.PackedElementFieldNumericType.Uint8)],
            data=buf.tobytes()), log_time=int(t * 1e9))

    def log_imu(self, t, ang_vel, lin_acc):
        """IMU 相当(胴体フレーム)。角速度 [rad/s]、線加速度 [m/s^2](重力込み)"""
        self.imu_ch.log({"frame_id": "base",
                         "angular_velocity": {k: float(v) for k, v in zip("xyz", ang_vel)},
                         "linear_acceleration": {k: float(v) for k, v in zip("xyz", lin_acc)}}, log_time=int(t * 1e9))

    def stats(self):
        return dict(steps=self.n_steps, points=self.n_points, total_s=self.t_spent,
                    ms_per_step=1e3 * self.t_spent / max(self.n_steps, 1))

    def close(self):
        self.writer.close()
