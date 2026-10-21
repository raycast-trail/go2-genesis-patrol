"""
go2_patrol.py — 学習済み方策にウェイポイント巡回をさせ、headless で mp4 に録画する。

構成(実機 Go2 の「Nav2 → cmd_vel → 歩行コントローラ」と同じ層構造):
  ウェイポイント列 ──► 追従則(P 制御: 進行方向の誤差 → yaw_rate、距離 → vx) ──► 速度指令 (vx, vy, yaw)
                                                                                   │
                                                                    学習済み方策(RL) ──► 12 関節の目標角
                                                                                   │
                                                                              Genesis で物理シミュレーション

方策は go2_train_patrol.py(指令範囲を広げて学習)のものを使う。
go2_train.py 既定(前進 0.5 m/s のみ)の方策では旋回指令に追従できないので、巡回は成立しない。

使い方:
  python go2_patrol.py -e go2-patrol --ckpt 299 --out go2_patrol.mp4
  python go2_patrol.py -e go2-patrol --ckpt 299 --waypoints square   # 既定。circle / line も可
  python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --seed 0 --avoid --out videos/t03_seed0.mp4
      # --seed N: eval/scenes.py の乱数障害物シーン(-1 で障害物なし)。--avoid/--no-avoid: LiDAR 回避の有無
      # 1 env の評価・録画は --backend cpu が速い(T02 実測: Metal 21 ms/step, CPU 2.1 ms/step)
"""

import argparse
import math
import os
import pickle
import time
from importlib import metadata

import numpy as np
import torch

try:
    if int(metadata.version("rsl-rl-lib").split(".")[0]) < 5:
        raise ImportError
except (metadata.PackageNotFoundError, ImportError, ValueError) as e:
    raise ImportError("Please install 'rsl-rl-lib>=5.0.0'.") from e
from rsl_rl.runners import OnPolicyRunner

import genesis as gs
from genesis.utils.geom import quat_to_xyz

from go2_env import Go2Env
from nav.lidar import make_lidar_cfg, read_scan, read_scan_full, read_scan_3d, sector_min
from nav.avoid import make_avoider
from nav.grid_map import GridMap
from nav.planner import Planner
from eval.scenes import make_obstacles, save_scene

WAYPOINT_SETS = {
    "line":   [(3.0, 0.0)],
    "square": [(2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)],
    "circle": [(2.0 * math.cos(a), 2.0 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 9)[1:]],
}


class WaypointFollower:
    """ウェイポイントへの単純な P 制御。出力は学習時の指令範囲(go2_train_patrol.PATROL_COMMAND_CFG)に収める。"""

    def __init__(self, waypoints, vx_max=0.6, yaw_gain=1.5, yaw_max=0.8, reach_dist=0.3, loop=True):
        self.waypoints = [np.asarray(w, dtype=np.float64) for w in waypoints]
        self.idx = 0
        self.vx_max, self.yaw_gain, self.yaw_max, self.reach_dist, self.loop = vx_max, yaw_gain, yaw_max, reach_dist, loop
        self.done = False

    def __call__(self, pos_xy, yaw_rad):
        if self.done:
            return 0.0, 0.0, 0.0
        target = self.waypoints[self.idx]
        delta = target - pos_xy
        dist = float(np.linalg.norm(delta))
        if dist < self.reach_dist:
            self.idx += 1
            if self.idx >= len(self.waypoints):
                if self.loop:
                    self.idx = 0
                else:
                    self.done = True
                    return 0.0, 0.0, 0.0
            target = self.waypoints[self.idx]
            delta = target - pos_xy
            dist = float(np.linalg.norm(delta))
        return self.command_to(pos_xy, yaw_rad, target)

    def command_to(self, pos_xy, yaw_rad, target):
        """任意の目標点 target へ向かう (vx, vy, yaw_rate)。到達判定・添字の更新はしない(v3 のローカル目標用)"""
        delta = np.asarray(target, dtype=np.float64) - pos_xy
        dist = float(np.linalg.norm(delta))
        heading_err = math.atan2(delta[1], delta[0]) - yaw_rad
        heading_err = (heading_err + math.pi) % (2 * math.pi) - math.pi   # [-pi, pi] に正規化
        yaw_rate = float(np.clip(self.yaw_gain * heading_err, -self.yaw_max, self.yaw_max))
        # 進行方向が大きくずれている間は前進を抑える(その場旋回に近づける)
        vx = self.vx_max * max(0.0, math.cos(heading_err)) * min(1.0, dist / 0.8)
        return vx, 0.0, yaw_rate

    @property
    def target(self):
        return self.waypoints[self.idx]


def resolve_ckpt_dir(exp_name, ckpt_dir=None):
    """cfgs.pkl と model_*.pt のあるディレクトリ。指定が無ければ logs/<exp>(学習直後)→ checkpoints/<exp>(同梱)の順に探す"""
    cands = [ckpt_dir] if ckpt_dir else [f"logs/{exp_name}", f"checkpoints/{exp_name}"]
    for d in cands:
        if d and os.path.exists(os.path.join(d, "cfgs.pkl")):
            return d
    raise FileNotFoundError(f"cfgs.pkl not found in {cands} (train first, or use the bundled checkpoints/)")


def run_patrol(exp_name, ckpt, seed=-1, avoid=True, waypoints="square", laps=1.0, max_time=60.0, out=None,
               camera=None, res=(1280, 720), fps=50, collision_dist=0.25, lidar_warmup=5, avoid_kwargs=None,
               lidar_min_range=0.0, verbose=True, mcap=None, avoid_version="v2", camera_only=False, v3_kwargs=None,
               ckpt_dir=None, lidar="2d"):
    """1 エピソードの巡回を実行して計測値の dict を返す(gs.init() 済みであること)。

    out=None なら録画しない(camera_cfg=None、T04 の評価用)。
    mcap=PATH なら nav/mcap_logger.py で LiDAR・姿勢・軌跡・障害物・指令を MCAP に書く(Foxglove 用。既定 None)。
    camera_only=True なら out=None でもカメラを作る(録画はしない)。T07 の再現性の切り分け用。
    avoid_version="v3": LiDAR から占有格子(nav/grid_map.py)を作り A*(nav/planner.py)で次のウェイポイントまでの経路を
      計画してローカル目標を経路追従に与える。下層の反応的回避は v1。v3_kwargs: replan_s(1.0), lookahead(0.8), inflate(0.35)
    戻り値: reached, max_laps_idx, end_reason, sim_s, wall_s, n_steps, n_collision, first_collision_t, n_contact,
            first_contact_t, n_raw_hit_steps, n_raw_hits, n_hits_after, path_length, min_lidar, n_placed, scene_meta,
            log(np.ndarray, 列は LOG_HEADER)
    """
    log_dir = resolve_ckpt_dir(exp_name, ckpt_dir)
    with open(f"{log_dir}/cfgs.pkl", "rb") as f:
        env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(f)
    reward_cfg["reward_scales"] = {}
    # go2_env.py は episode_length_s(学習用 20 s)を超えるとタイムアウトでリセットする。
    # 巡回中にリセットされないよう、上限を max_time より長く上書きする(T01 申し送り)
    env_cfg["episode_length_s"] = max_time + 5.0
    if verbose:
        print(f"[go2_patrol] trained command ranges: vx={command_cfg['lin_vel_x_range']} "
              f"vy={command_cfg['lin_vel_y_range']} yaw={command_cfg['ang_vel_range']}")

    wps = WAYPOINT_SETS[waypoints]
    obstacles, scene_meta = make_obstacles(seed, return_spec=True)
    if seed >= 0:
        scene_file = save_scene(scene_meta)
        if verbose:
            print(f"[go2_patrol] scene seed={seed}: {scene_meta['n_placed']} obstacles -> {scene_file}")
    camera_mode = camera or ("overhead" if seed >= 0 else "follow")
    if out is None and not camera_only:
        camera_cfg = None
    elif camera_mode == "overhead":
        camera_cfg = dict(res=tuple(res), pos=(1.0, -4.0, 4.0), lookat=(1.0, 1.0, 0.0), fov=50, GUI=False)
    elif camera_mode == "overhead-close":
        # 提出動画用の寄せた俯瞰(T08)
        camera_cfg = dict(res=tuple(res), pos=(1.0, -3.2, 3.0), lookat=(1.0, 1.0, 0.3), fov=50, GUI=False)
    else:
        camera_cfg = dict(res=tuple(res), pos=(4.0, -4.0, 3.0), lookat=(1.0, 1.0, 0.3), fov=45, GUI=False)
    lidar_cfg = make_lidar_cfg(mode=lidar, min_range=lidar_min_range)

    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg,
                 command_cfg=command_cfg, show_viewer=False, camera_cfg=camera_cfg,
                 lidar_cfg=lidar_cfg, obstacles=obstacles)
    max_range = lidar_cfg["max_range"]
    cam = env.cam if out is not None else None     # camera_only のときは env.cam はあるが録画しない
    # 障害物エンティティの種類(spec の順に展開。table は 天板 + 脚 4 本)。接触した相手の種類の記録用(T12)
    obstacle_types = []
    for o in scene_meta["obstacles"]:
        obstacle_types += ["table_top", "table_leg", "table_leg", "table_leg", "table_leg"] if o["type"] == "table" else [o["type"]]
    assert len(obstacle_types) == len(env.obstacles)

    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    runner.load(os.path.join(log_dir, f"model_{ckpt}.pt"))
    policy = runner.get_inference_policy(device=gs.device)

    env._resample_commands = lambda envs_idx: None   # 指令は追従則で与える
    follower = WaypointFollower(wps, loop=waypoints != "line")
    max_laps_idx = int(len(wps) * laps)
    v3 = avoid and avoid_version == "v3"
    v3k = dict(replan_s=1.0, lookahead=0.8, inflate=0.35, inflate_retry=0.25)
    v3k.update(v3_kwargs or {})
    avoider = make_avoider("v1" if v3 else avoid_version, **(avoid_kwargs or {})) if avoid else None
    gmap = GridMap(max_range=max_range) if v3 else None
    planner = Planner(gmap, inflate=v3k["inflate"], inflate_retry=v3k["inflate_retry"], lookahead=v3k["lookahead"]) if v3 else None
    replan_steps = max(1, int(round(v3k["replan_s"] / 0.02)))
    last_plan_step, plan_target_idx = -10 ** 9, -1
    n_local = 0
    if verbose:
        print(f"[go2_patrol] avoid={'on ' + str(avoider.params()) if avoider else 'off'}"
              + (f" | v3 map+A*: {v3k}" if v3 else ""))

    mcap_logger = None
    if mcap:
        from nav.mcap_logger import McapLogger
        os.makedirs(os.path.dirname(mcap) or ".", exist_ok=True)
        mcap_logger = McapLogger(mcap, scene_meta["obstacles"], lidar_pos_offset=lidar_cfg["pos_offset"],
                                 max_range=max_range)

    obs_dict = env.reset()
    if cam is not None:
        cam.start_recording(save_to_filename=out, fps=fps)
    t0 = time.time()
    n_steps, reached, log = 0, 0, []
    end_reason = "timeout"   # max_time まで走り切った場合。完了 / 転倒で上書きする
    scan = None
    n_collision, first_collision_t = 0, None
    n_contact, first_contact_t = 0, None          # 物理接触(robot と障害物の contact)。衝突の主指標(T04)
    first_contact_type, contact_types = None, set()
    pts3d, cls3d = None, None
    prev_lin_vel = None
    n_raw_hit_steps, n_raw_hits, n_hits_after = 0, 0, 0   # 地面除去の検証用(raw / 除去後のヒット数)
    min_lidar = max_range
    with torch.no_grad():
        while n_steps * env.dt < max_time:
            # env.base_pos / base_euler は step() 内で更新されるため reset 直後は未定義 → ロボットから直接読む
            pos = env.robot.get_pos()[0].cpu().numpy()
            yaw = float(quat_to_xyz(env.robot.get_quat(), rpy=True, degrees=False)[0, 2])
            prev_idx = follower.idx
            vx, vy, wz = follower(pos[:2], yaw)
            if follower.idx != prev_idx:
                reached += 1
                if verbose:
                    print(f"[go2_patrol] t={n_steps * env.dt:5.1f}s reached waypoint {prev_idx} at ({pos[0]:.2f}, {pos[1]:.2f})")
                if reached >= max_laps_idx and waypoints != "line":
                    end_reason = "completed"
                    break
            if follower.done:
                end_reason = "completed"
                break
            # v3: 1.0 s ごと(またはウェイポイント切替時)に A* で再計画し、経路上 0.8 m 先をローカル目標にする
            if v3 and scan is not None:
                if (n_steps - last_plan_step >= replan_steps) or (follower.idx != plan_target_idx):
                    planner.plan(pos[:2], follower.target)
                    last_plan_step, plan_target_idx = n_steps, follower.idx
                lg = planner.local_goal(pos[:2])
                if lg is not None:
                    vx, vy, wz = follower.command_to(pos[:2], yaw, lg)
                    n_local += 1
            vx_follow, wz_follow = vx, wz
            if avoider is not None and scan is not None:
                vx, wz = avoider(scan, vx, wz)
            av = avoider.last if avoider is not None else {}
            env.commands[:] = torch.tensor([vx, vy, wz], dtype=gs.tc_float, device=gs.device)
            actions = policy(obs_dict)
            obs_dict, rews, dones, infos = env.step(actions)
            if cam is not None and camera_mode == "follow":
                cam.set_pose(pos=(pos[0] + 3.0, pos[1] - 3.0, 2.2), lookat=(pos[0], pos[1], 0.3))
            # LiDAR(着地後から使う)。ニアミス = 地面除去後の最小距離 < collision_dist
            min_dist, collision, raw_hits, hits = max_range, 0, 0, 0
            raw, pts = None, None
            if n_steps >= lidar_warmup:
                if lidar == "3d":
                    scan, pts, raw, pts3d, cls3d, _ = read_scan_3d(env)     # 胴体帯だけを 72 本に投影(T12)
                else:
                    scan, raw, pts = read_scan_full(env)
                if v3:
                    bp = env.robot.get_pos()[0].cpu().numpy()
                    byaw = float(quat_to_xyz(env.robot.get_quat(), rpy=True, degrees=False)[0, 2])
                    gmap.update(bp[:2], byaw, scan, raw, pts)
                min_dist = float(scan.min())
                min_lidar = min(min_lidar, min_dist)
                raw_hits, hits = int(np.sum(raw < max_range)), int(np.sum(scan < max_range))
                n_raw_hit_steps += raw_hits > 0
                n_raw_hits += raw_hits
                n_hits_after += hits
                if min_dist < collision_dist:
                    collision = 1
                    n_collision += 1
                    if first_collision_t is None:
                        first_collision_t = n_steps * env.dt
                        if verbose:
                            print(f"[go2_patrol] collision (lidar) at t={first_collision_t:.1f}s min_dist={min_dist:.2f}")
            contact = 0
            for obs, otype in zip(env.obstacles, obstacle_types):
                c = env.robot.get_contacts(with_entity=obs)
                n_c = int(c["valid_mask"].sum()) if "valid_mask" in c else len(c["position"])
                if n_c > 0:
                    contact = 1
                    contact_types.add(otype)
                    if first_contact_type is None:
                        first_contact_type = otype
                    break
            if contact:
                n_contact += 1
                if first_contact_t is None:
                    first_contact_t = n_steps * env.dt
                    if verbose:
                        print(f"[go2_patrol] contact with obstacle at t={first_contact_t:.1f}s (lidar min_dist={min_dist:.2f})")
            log.append((n_steps * env.dt, pos[0], pos[1], math.degrees(yaw), vx, wz, min_dist, collision, raw_hits, hits,
                        contact, vx_follow, wz_follow, av.get("d_front", np.inf), av.get("hit_lat", 0.0),
                        avoider.side if avoider is not None else 0, av.get("committed", 0)))
            if mcap_logger is not None:
                # step 後の姿勢(LiDAR と同じ時刻)。Genesis の quat は (w, x, y, z)
                bp = env.robot.get_pos()[0].cpu().numpy()
                bq = env.robot.get_quat()[0].cpu().numpy()
                hit_pts = pts[scan < max_range] if pts is not None else np.zeros((0, 3))
                mcap_logger.log_step(n_steps * env.dt, bp, bq, raw, scan if raw is not None else None, hit_pts, (vx, wz),
                                     dict(d_front=av.get("d_front", np.inf), avoid_side=avoider.side if avoider else 0,
                                          committed=av.get("committed", 0), reached=reached, min_dist=min_dist,
                                          contact=contact))
                if v3 and n_steps % 50 == 0:
                    mcap_logger.log_grid(n_steps * env.dt, gmap, planner.path_xy)
                if lidar == "3d" and pts3d is not None:
                    mcap_logger.log_points3d(n_steps * env.dt, pts3d, cls3d)
                    # IMU 相当: 胴体角速度(観測)と線加速度(胴体フレーム速度の差分 + 重力)。提出後の SLAM 実験用の素材
                    lv = env.base_lin_vel[0].cpu().numpy().astype(np.float64)
                    av = env.base_ang_vel[0].cpu().numpy().astype(np.float64)
                    pg = env.projected_gravity[0].cpu().numpy().astype(np.float64)
                    acc = (lv - prev_lin_vel) / env.dt - 9.81 * pg if prev_lin_vel is not None else -9.81 * pg
                    prev_lin_vel = lv
                    mcap_logger.log_imu(n_steps * env.dt, av, acc)
            n_steps += 1
            if bool(dones[0]):
                # 環境のエピソード上限によるリセット(time_outs)と転倒(pitch/roll 超過)を区別する
                if bool(infos["time_outs"][0]):
                    end_reason = "timeout"
                    if verbose:
                        print(f"[go2_patrol] timeout (env episode limit) at t={n_steps * env.dt:.1f}s")
                else:
                    end_reason = "fell"
                    if verbose:
                        print(f"[go2_patrol] fell at t={n_steps * env.dt:.1f}s (cmd vx={vx:.2f}, yaw_rate={wz:.2f})")
                break
    if cam is not None:
        cam.stop_recording()
    elapsed = time.time() - t0
    mcap_stats = None
    if mcap_logger is not None:
        mcap_logger.close()
        mcap_stats = mcap_logger.stats()
        mcap_stats["bytes"] = os.path.getsize(mcap)
        if verbose:
            print(f"[go2_patrol] wrote {mcap}: {mcap_stats['bytes'] / 1e6:.1f} MB, {mcap_stats['steps']} steps, "
                  f"{mcap_stats['points']} points, {mcap_stats['ms_per_step']:.2f} ms/step for logging")
    log = np.array(log)
    path_length = float(np.sum(np.hypot(np.diff(log[:, 1]), np.diff(log[:, 2])))) if len(log) > 1 else 0.0
    v3_stats = None
    if v3:
        v3_stats = dict(n_plans=planner.n_plans, n_fail=planner.n_fail, n_retry=planner.n_retry, n_local=n_local,
                        occupied_cells=int(gmap.occupied().sum()), last_path=planner.path_xy)
        if verbose:
            print(f"[go2_patrol] v3: plans={planner.n_plans} no-path={planner.n_fail} retry(inflate 0.25)={planner.n_retry} "
                  f"local-goal steps={n_local} occupied cells={v3_stats['occupied_cells']}")
    return dict(first_contact_type=first_contact_type, contact_types=sorted(contact_types), lidar=lidar,
                fell=end_reason == "fell", v3_stats=v3_stats, gmap=gmap, reached=reached, max_laps_idx=max_laps_idx, end_reason=end_reason, sim_s=n_steps * env.dt,
                wall_s=elapsed, n_steps=n_steps, n_collision=n_collision, first_collision_t=first_collision_t,
                n_contact=n_contact, first_contact_t=first_contact_t, n_raw_hit_steps=n_raw_hit_steps,
                n_raw_hits=n_raw_hits, n_hits_after=n_hits_after, path_length=path_length, min_lidar=min_lidar,
                n_placed=scene_meta["n_placed"], scene_meta=scene_meta, log=log, lidar_steps=max(n_steps - lidar_warmup, 0),
                avoid_params=avoider.params() if avoider else None, mcap_stats=mcap_stats)


LOG_HEADER = ("t,x,y,yaw_deg,cmd_vx,cmd_yaw,min_dist,collision,raw_hits,hits,contact,follow_vx,follow_yaw,d_front,hit_lat,"
              "avoid_side,committed")
SUMMARY_HEADER = ("exp_name,ckpt,backend,waypoints,seed,n_obstacles,avoid,reached,n_waypoints,end_reason,sim_s,"
                  "wall_s,collision_steps,first_collision_s,contact_steps,first_contact_s,raw_hit_steps,raw_hits,hits_after,out")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exp-name", type=str, default="go2-patrol")
    parser.add_argument("--ckpt", type=int, default=299)
    parser.add_argument("--ckpt-dir", type=str, default=None,
                        help="cfgs.pkl / model_*.pt のディレクトリ(既定: logs/<exp> → 無ければ checkpoints/<exp>)")
    parser.add_argument("--out", type=str, default="go2_patrol.mp4")
    parser.add_argument("--no-video", action="store_true", help="録画しない(camera なし。評価用、速い)")
    parser.add_argument("--mcap", type=str, default=None, help="指定時のみ MCAP(Foxglove 用)を書く。例: results/mcap/run.mcap")
    parser.add_argument("--camera-only", action="store_true", help="--no-video でもカメラを作る(録画しない)。再現性の切り分け用")
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument("--waypoints", choices=list(WAYPOINT_SETS), default="square")
    parser.add_argument("--laps", type=float, default=1.0, help="周回数(square/circle)。line では無視")
    parser.add_argument("--max-time", type=float, default=60.0, help="シミュレーション秒数の上限")
    parser.add_argument("--res", type=int, nargs=2, default=[1280, 720])
    parser.add_argument("--fps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=-1, help="障害物シーンの seed(eval/scenes.py)。-1 で障害物なし")
    parser.add_argument("--avoid", action=argparse.BooleanOptionalAction, default=True,
                        help="LiDAR による回避則(nav/avoid.py)を使う。--no-avoid で経路追従のみ")
    parser.add_argument("--camera", choices=["follow", "overhead", "overhead-close"], default=None,
                        help="追従 / 俯瞰 / 寄せた俯瞰(既定: 障害物ありなら overhead、なしなら follow)")
    parser.add_argument("--collision-dist", type=float, default=0.25, help="LiDAR 最小距離がこれ未満ならニアミス(LiDAR 衝突)")
    parser.add_argument("--lidar-warmup", type=int, default=5, help="着地までの間 LiDAR を使わないステップ数")
    parser.add_argument("--d-slow", type=float, default=1.0)
    parser.add_argument("--d-stop", type=float, default=0.45)
    parser.add_argument("--k-avoid", type=float, default=0.8)
    parser.add_argument("--rate-limit", type=float, default=0.1)
    parser.add_argument("--w-half", type=float, default=0.4, help="回避の正面判定に使う進路の半幅 [m]")
    parser.add_argument("--front-mode", choices=["corridor", "sectors"], default="corridor")
    parser.add_argument("--avoid-version", choices=["v1", "v2", "v3"], default="v2",
                        help="v1 = T03/T04 の回避則、v2 = コミット区間つき(T05、既定)、v3 = 占有格子 + A* + v1 下層(T09)")
    parser.add_argument("--replan-s", type=float, default=1.0, help="v3: 再計画周期 [s]")
    parser.add_argument("--lookahead", type=float, default=0.8, help="v3: ローカル目標の距離 [m]")
    parser.add_argument("--inflate", type=float, default=0.35, help="v3: 膨張半径 [m]")
    parser.add_argument("--t-commit", type=float, default=2.0, help="v2: 回避側へのコミット時間 [s]")
    parser.add_argument("--t-clear", type=float, default=1.0, help="v2: 正面が空いた後に直進する時間 [s]")
    parser.add_argument("--lidar-min-range", type=float, default=0.0)
    parser.add_argument("--lidar", choices=["2d", "3d"], default="2d",
                        help="2d = 水平 72 本(既定)、3d = 72 × 16 層を胴体の高さ帯で 72 本に投影(T12)")
    parser.add_argument("--summary-csv", type=str, default="results/t03_metrics.csv",
                        help="実行ごとの要約行を追記する CSV(空文字で無効)")
    args = parser.parse_args()

    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, logging_level="warning")
    print(f"[go2_patrol] gs.backend={gs.backend}  gs.device={gs.device}")
    avoid_kwargs = dict(d_slow=args.d_slow, d_stop=args.d_stop, k_avoid=args.k_avoid, rate_limit=args.rate_limit,
                        w_half=args.w_half, front_mode=args.front_mode, T_commit=args.t_commit, T_clear=args.t_clear)
    r = run_patrol(args.exp_name, args.ckpt, seed=args.seed, avoid=args.avoid, waypoints=args.waypoints, laps=args.laps,
                   max_time=args.max_time, out=None if args.no_video else args.out, camera=args.camera, res=args.res,
                   fps=args.fps, collision_dist=args.collision_dist, lidar_warmup=args.lidar_warmup,
                   avoid_kwargs=avoid_kwargs, lidar_min_range=args.lidar_min_range, mcap=args.mcap,
                   avoid_version=args.avoid_version, camera_only=args.camera_only,
                   v3_kwargs=dict(replan_s=args.replan_s, lookahead=args.lookahead, inflate=args.inflate),
                   ckpt_dir=args.ckpt_dir, lidar=args.lidar)
    if r.get("v3_stats"):
        base = os.path.splitext(args.out)[0]
        if r["v3_stats"]["last_path"]:
            np.savetxt(base + "_plan.csv", np.array(r["v3_stats"]["last_path"]), delimiter=",", fmt="%.4f", header="x,y", comments="")
        r["gmap"].save_png(base + "_map.png", robot_xy=r["log"][-1, 1:3], path_xy=r["v3_stats"]["last_path"],
                           obstacles=r["scene_meta"]["obstacles"], waypoints=[(0, 0)] + WAYPOINT_SETS[args.waypoints],
                           title=f"v3 map, seed {args.seed}, t={r['sim_s']:.1f}s")
        print(f"[go2_patrol] wrote {base}_map.png and {base}_plan.csv")
    log_path = os.path.splitext(args.out)[0] + "_log.csv"
    np.savetxt(log_path, r["log"], delimiter=",", fmt="%.4f", header=LOG_HEADER, comments="")
    print(f"[go2_patrol] wrote {'(no video) ' + log_path if args.no_video else args.out}: {r['n_steps']} steps, "
          f"sim {r['sim_s']:.1f}s, wall {r['wall_s']:.1f}s, waypoints reached {r['reached']}/{r['max_laps_idx']}, "
          f"end reason: {r['end_reason']}")
    print(f"[go2_patrol] collision steps={r['n_collision']} first={r['first_collision_t']}; "
          f"contact steps={r['n_contact']} first={r['first_contact_t']} type={r['first_contact_type']}; path length={r['path_length']:.2f} m; "
          f"lidar: steps with raw hits={r['n_raw_hit_steps']}/{r['lidar_steps']}, raw hits total={r['n_raw_hits']}, "
          f"hits after ground removal={r['n_hits_after']}")
    if args.summary_csv:
        os.makedirs(os.path.dirname(args.summary_csv) or ".", exist_ok=True)
        new = not os.path.exists(args.summary_csv)
        with open(args.summary_csv, "a", encoding="utf-8") as f:
            if new:
                f.write(SUMMARY_HEADER + "\n")
            fc = "" if r["first_collision_t"] is None else f"{r['first_collision_t']:.2f}"
            ft = "" if r["first_contact_t"] is None else f"{r['first_contact_t']:.2f}"
            f.write(f"{args.exp_name},{args.ckpt},{gs.backend},{args.waypoints},{args.seed},{r['n_placed']},"
                    f"{int(args.avoid)},{r['reached']},{r['max_laps_idx']},{r['end_reason']},{r['sim_s']:.2f},"
                    f"{r['wall_s']:.1f},{r['n_collision']},{fc},{r['n_contact']},{ft},{r['n_raw_hit_steps']},"
                    f"{r['n_raw_hits']},{r['n_hits_after']},{args.out}\n")


if __name__ == "__main__":
    main()
