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
from nav.lidar import make_lidar_cfg, read_scan, sector_min
from nav.avoid import ObstacleAvoider
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
        heading_err = math.atan2(delta[1], delta[0]) - yaw_rad
        heading_err = (heading_err + math.pi) % (2 * math.pi) - math.pi   # [-pi, pi] に正規化
        yaw_rate = float(np.clip(self.yaw_gain * heading_err, -self.yaw_max, self.yaw_max))
        # 進行方向が大きくずれている間は前進を抑える(その場旋回に近づける)
        vx = self.vx_max * max(0.0, math.cos(heading_err)) * min(1.0, dist / 0.8)
        return vx, 0.0, yaw_rate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exp-name", type=str, default="go2-patrol")
    parser.add_argument("--ckpt", type=int, default=299)
    parser.add_argument("--out", type=str, default="go2_patrol.mp4")
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument("--waypoints", choices=list(WAYPOINT_SETS), default="square")
    parser.add_argument("--laps", type=float, default=1.0, help="周回数(square/circle)。line では無視")
    parser.add_argument("--max-time", type=float, default=60.0, help="シミュレーション秒数の上限")
    parser.add_argument("--res", type=int, nargs=2, default=[1280, 720])
    parser.add_argument("--fps", type=int, default=50)
    parser.add_argument("--markers", action="store_true", help="ウェイポイントに目印(衝突なしの円柱)を置く")
    parser.add_argument("--seed", type=int, default=-1, help="障害物シーンの seed(eval/scenes.py)。-1 で障害物なし")
    parser.add_argument("--avoid", action=argparse.BooleanOptionalAction, default=True,
                        help="LiDAR セクタ距離による回避則(nav/avoid.py)を使う。--no-avoid で経路追従のみ")
    parser.add_argument("--camera", choices=["follow", "overhead"], default=None,
                        help="追従カメラ / 俯瞰カメラ(既定: 障害物ありなら overhead、なしなら follow)")
    parser.add_argument("--collision-dist", type=float, default=0.25, help="LiDAR 最小距離がこれ未満なら衝突")
    parser.add_argument("--lidar-warmup", type=int, default=5, help="着地までの間 LiDAR を使わないステップ数")
    parser.add_argument("--d-slow", type=float, default=1.0)
    parser.add_argument("--d-stop", type=float, default=0.45)
    parser.add_argument("--k-avoid", type=float, default=0.8)
    parser.add_argument("--rate-limit", type=float, default=0.1)
    parser.add_argument("--w-half", type=float, default=0.4, help="回避の正面判定に使う進路の半幅 [m]")
    parser.add_argument("--front-mode", choices=["corridor", "sectors"], default="corridor")
    parser.add_argument("--lidar-min-range", type=float, default=0.0)
    parser.add_argument("--summary-csv", type=str, default="results/t03_metrics.csv",
                        help="実行ごとの要約行を追記する CSV(空文字で無効)")
    args = parser.parse_args()

    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, logging_level="warning")
    print(f"[go2_patrol] gs.backend={gs.backend}  gs.device={gs.device}")

    log_dir = f"logs/{args.exp_name}"
    with open(f"{log_dir}/cfgs.pkl", "rb") as f:
        env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(f)
    reward_cfg["reward_scales"] = {}
    # go2_env.py は episode_length_s(学習用 20 s)を超えるとタイムアウトでリセットする。
    # 巡回中にリセットされないよう、上限を max_time より長く上書きする(T01 申し送り)
    env_cfg["episode_length_s"] = args.max_time + 5.0
    print(f"[go2_patrol] trained command ranges: vx={command_cfg['lin_vel_x_range']} "
          f"vy={command_cfg['lin_vel_y_range']} yaw={command_cfg['ang_vel_range']}")

    waypoints = WAYPOINT_SETS[args.waypoints]
    obstacles, scene_meta = make_obstacles(args.seed, return_spec=True)
    if args.seed >= 0:
        scene_file = save_scene(scene_meta)
        print(f"[go2_patrol] scene seed={args.seed}: {scene_meta['n_placed']} obstacles -> {scene_file}")
    camera_mode = args.camera or ("overhead" if args.seed >= 0 else "follow")
    if camera_mode == "overhead":
        camera_cfg = dict(res=tuple(args.res), pos=(1.0, -4.0, 4.0), lookat=(1.0, 1.0, 0.0), fov=50, GUI=False)
    else:
        camera_cfg = dict(res=tuple(args.res), pos=(4.0, -4.0, 3.0), lookat=(1.0, 1.0, 0.3), fov=45, GUI=False)
    lidar_cfg = make_lidar_cfg(min_range=args.lidar_min_range)

    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg,
                 command_cfg=command_cfg, show_viewer=False, camera_cfg=camera_cfg,
                 lidar_cfg=lidar_cfg, obstacles=obstacles)
    max_range = lidar_cfg["max_range"]
    # (markers は scene.build() の前に追加する必要があるため、Go2Env の内部で足すのが本来。
    #  本スクリプトでは簡単のため省略し、--markers 指定時は警告だけ出す)
    if args.markers:
        print("[go2_patrol] --markers はこの版では未実装(build 前に add_entity が必要)。段階 5 で go2_env.py に追加予定")
    cam = env.cam

    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    runner.load(os.path.join(log_dir, f"model_{args.ckpt}.pt"))
    policy = runner.get_inference_policy(device=gs.device)

    env._resample_commands = lambda envs_idx: None   # 指令は追従則で与える
    follower = WaypointFollower(waypoints, loop=args.waypoints != "line")
    max_laps_idx = int(len(waypoints) * args.laps)
    avoider = ObstacleAvoider(d_slow=args.d_slow, d_stop=args.d_stop, k_avoid=args.k_avoid,
                              rate_limit=args.rate_limit, w_half=args.w_half,
                              front_mode=args.front_mode) if args.avoid else None
    print(f"[go2_patrol] avoid={'on ' + str(avoider.params()) if avoider else 'off'}")

    obs_dict = env.reset()
    cam.start_recording(save_to_filename=args.out, fps=args.fps)
    t0 = time.time()
    n_steps, reached, log = 0, 0, []
    end_reason = "timeout"   # max_time まで走り切った場合。完了 / 転倒で上書きする
    scan, sectors = None, None
    n_collision, first_collision_t = 0, None
    n_contact, first_contact_t = 0, None          # 物理接触(robot と障害物の contact)による衝突。LiDAR 判定の検証用
    n_raw_hit_steps, n_raw_hits, n_hits_after = 0, 0, 0   # 地面除去の検証用(raw / 除去後のヒット数)
    with torch.no_grad():
        while n_steps * env.dt < args.max_time:
            # env.base_pos / base_euler は step() 内で更新されるため reset 直後は未定義 → ロボットから直接読む
            pos = env.robot.get_pos()[0].cpu().numpy()
            yaw = float(quat_to_xyz(env.robot.get_quat(), rpy=True, degrees=False)[0, 2])
            prev_idx = follower.idx
            vx, vy, wz = follower(pos[:2], yaw)
            if follower.idx != prev_idx:
                reached += 1
                print(f"[go2_patrol] t={n_steps * env.dt:5.1f}s reached waypoint {prev_idx} at ({pos[0]:.2f}, {pos[1]:.2f})")
                if reached >= max_laps_idx and args.waypoints != "line":
                    end_reason = "completed"
                    break
            if follower.done:
                end_reason = "completed"
                break
            vx_follow, wz_follow = vx, wz
            if avoider is not None and scan is not None:
                vx, wz = avoider(scan, vx, wz)
            av = avoider.last if avoider is not None else {}
            env.commands[:] = torch.tensor([vx, vy, wz], dtype=gs.tc_float, device=gs.device)
            actions = policy(obs_dict)
            obs_dict, rews, dones, infos = env.step(actions)
            if camera_mode == "follow":
                cam.set_pose(pos=(pos[0] + 3.0, pos[1] - 3.0, 2.2), lookat=(pos[0], pos[1], 0.3))
            # LiDAR(着地後から使う)。衝突 = 地面除去後の最小距離 < collision_dist
            min_dist, collision, raw_hits, hits = max_range, 0, 0, 0
            if n_steps >= args.lidar_warmup:
                scan, raw = read_scan(env, return_raw=True)
                sectors = sector_min(scan)
                min_dist = float(scan.min())
                raw_hits, hits = int(np.sum(raw < max_range)), int(np.sum(scan < max_range))
                n_raw_hit_steps += raw_hits > 0
                n_raw_hits += raw_hits
                n_hits_after += hits
                if min_dist < args.collision_dist:
                    collision = 1
                    n_collision += 1
                    if first_collision_t is None:
                        first_collision_t = n_steps * env.dt
                        print(f"[go2_patrol] collision at t={first_collision_t:.1f}s min_dist={min_dist:.2f}")
            contact = 0
            for obs in env.obstacles:
                c = env.robot.get_contacts(with_entity=obs)
                n_c = int(c["valid_mask"].sum()) if "valid_mask" in c else len(c["position"])
                if n_c > 0:
                    contact = 1
                    break
            if contact:
                n_contact += 1
                if first_contact_t is None:
                    first_contact_t = n_steps * env.dt
                    print(f"[go2_patrol] contact with obstacle at t={first_contact_t:.1f}s (lidar min_dist={min_dist:.2f})")
            log.append((n_steps * env.dt, pos[0], pos[1], math.degrees(yaw), vx, wz, min_dist, collision, raw_hits, hits,
                        contact, vx_follow, wz_follow, av.get("d_front", np.inf), av.get("hit_lat", 0.0),
                        avoider.side if avoider is not None else 0))
            n_steps += 1
            if bool(dones[0]):
                # 環境のエピソード上限によるリセット(time_outs)と転倒(pitch/roll 超過)を区別する
                if bool(infos["time_outs"][0]):
                    end_reason = "timeout"
                    print(f"[go2_patrol] timeout (env episode limit) at t={n_steps * env.dt:.1f}s")
                else:
                    end_reason = "fell"
                    print(f"[go2_patrol] fell at t={n_steps * env.dt:.1f}s (cmd vx={vx:.2f}, yaw_rate={wz:.2f})")
                break
    cam.stop_recording()
    elapsed = time.time() - t0
    np.savetxt(os.path.splitext(args.out)[0] + "_log.csv", np.array(log), delimiter=",", fmt="%.4f",
               header="t,x,y,yaw_deg,cmd_vx,cmd_yaw,min_dist,collision,raw_hits,hits,contact,"
                      "follow_vx,follow_yaw,d_front,hit_lat,avoid_side", comments="")
    sim_s = n_steps * env.dt
    print(f"[go2_patrol] wrote {args.out}: {n_steps} steps, sim {sim_s:.1f}s, wall {elapsed:.1f}s, "
          f"waypoints reached {reached}/{max_laps_idx}, end reason: {end_reason}")
    print(f"[go2_patrol] collision steps={n_collision} first={first_collision_t}; "
          f"contact steps={n_contact} first={first_contact_t}; "
          f"lidar: steps with raw hits={n_raw_hit_steps}/{max(n_steps - args.lidar_warmup, 0)}, "
          f"raw hits total={n_raw_hits}, hits after ground removal={n_hits_after}")
    if args.summary_csv:
        os.makedirs(os.path.dirname(args.summary_csv) or ".", exist_ok=True)
        new = not os.path.exists(args.summary_csv)
        with open(args.summary_csv, "a", encoding="utf-8") as f:
            if new:
                f.write("exp_name,ckpt,backend,waypoints,seed,n_obstacles,avoid,reached,n_waypoints,end_reason,sim_s,"
                        "wall_s,collision_steps,first_collision_s,contact_steps,first_contact_s,"
                        "raw_hit_steps,raw_hits,hits_after,out\n")
            f.write(f"{args.exp_name},{args.ckpt},{gs.backend},{args.waypoints},{args.seed},{len(obstacles)},"
                    f"{int(args.avoid)},{reached},{max_laps_idx},{end_reason},{sim_s:.2f},{elapsed:.1f},{n_collision},"
                    f"{'' if first_collision_t is None else f'{first_collision_t:.2f}'},{n_contact},"
                    f"{'' if first_contact_t is None else f'{first_contact_t:.2f}'},{n_raw_hit_steps},{n_raw_hits},"
                    f"{n_hits_after},{args.out}\n")


if __name__ == "__main__":
    main()
