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
    camera_cfg = dict(res=tuple(args.res), pos=(4.0, -4.0, 3.0), lookat=(1.0, 1.0, 0.3), fov=45, GUI=False)

    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, reward_cfg=reward_cfg,
                 command_cfg=command_cfg, show_viewer=False, camera_cfg=camera_cfg)
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

    obs_dict = env.reset()
    cam.start_recording(save_to_filename=args.out, fps=args.fps)
    t0 = time.time()
    n_steps, reached, log = 0, 0, []
    end_reason = "timeout"   # max_time まで走り切った場合。完了 / 転倒で上書きする
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
            env.commands[:] = torch.tensor([vx, vy, wz], dtype=gs.tc_float, device=gs.device)
            actions = policy(obs_dict)
            obs_dict, rews, dones, infos = env.step(actions)
            cam.set_pose(pos=(pos[0] + 3.0, pos[1] - 3.0, 2.2), lookat=(pos[0], pos[1], 0.3))
            log.append((n_steps * env.dt, pos[0], pos[1], math.degrees(yaw), vx, wz))
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
               header="t,x,y,yaw_deg,cmd_vx,cmd_yaw", comments="")
    print(f"[go2_patrol] wrote {args.out}: {n_steps} steps, sim {n_steps * env.dt:.1f}s, wall {elapsed:.1f}s, "
          f"waypoints reached {reached}/{max_laps_idx}, end reason: {end_reason}")


if __name__ == "__main__":
    main()
