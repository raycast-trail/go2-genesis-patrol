"""
go2_record.py — 学習済み Go2 歩行方策を Viewer なし(headless)で実行し、mp4 に録画する。

go2_eval.py(Genesis v1.4.4 examples/locomotion)をベースに、
  * show_viewer=False(Viewer を開かない → macOS のメインスレッド制約を回避)
  * scene.add_camera() で固定/追従カメラを追加し、start_recording → render → stop_recording で mp4 化
  * 速度指令を乱数ではなく「台本」(前進 → 左旋回 → 前進 → 停止 …)で与え、指令追従が目視できるようにする
に変更している。go2_env.py は camera_cfg 引数を追加した最小パッチ版を使う。

使い方(Genesis リポジトリの examples/locomotion 相当のディレクトリで):
  python go2_record.py -e go2-walking --ckpt 100 --out go2_walk.mp4
  python go2_record.py -e go2-walking --ckpt 100 --backend cpu   # Metal で描画が不安定なとき
"""

import argparse
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

from go2_env import Go2Env


# 速度指令の台本: (継続秒, vx [m/s], vy [m/s], yaw_rate [rad/s])
# 注意: v1.4.4 の go2_train.py の command_cfg は vx=[0.5, 0.5], vy=[0,0], yaw=[0,0] に固定されている。
# つまり既定の学習では「前進 0.5 m/s」しか学んでいない。旋回・停止・速度変化を指令しても
# 方策はその指令を見たことがないので、追従しない・転倒する可能性が高い。
# → 巡回(ウェイポイント追従)をやるには command_cfg の範囲を広げて再学習する必要がある。
#   これが「実現可能性調査」の次の論点(段階 5)。
# T01: 指令範囲を広げて再学習した方策(go2-patrol)用の台本。前進 → 左旋回 → 前進 → 右旋回 → 停止(計 14 s)
SCRIPT = [(3.0, 0.5, 0, 0), (3.0, 0.5, 0, 0.5), (3.0, 0.5, 0, 0), (3.0, 0.5, 0, -0.5), (2.0, 0.0, 0, 0)]
# 既定例題(go2-walking)の学習範囲どおりに前進だけさせる場合:
# SCRIPT = [(8.0, 0.5, 0.0, 0.0)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exp-name", type=str, default="go2-walking")
    parser.add_argument("--ckpt", type=int, default=100)
    parser.add_argument("--out", type=str, default="go2_walk.mp4")
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="gpu",
                        help="gpu = Mac では Metal。描画が不安定なら cpu")
    parser.add_argument("--res", type=int, nargs=2, default=[1280, 720])
    parser.add_argument("--fps", type=int, default=50, help="録画 fps。制御周期 50Hz に合わせると等速")
    parser.add_argument("--follow", action="store_true", help="カメラがロボットを追従する")
    args = parser.parse_args()

    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, logging_level="warning")
    print(f"[go2_record] gs.backend={gs.backend}  gs.device={gs.device}")

    log_dir = f"logs/{args.exp_name}"
    with open(f"{log_dir}/cfgs.pkl", "rb") as f:
        env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(f)
    reward_cfg["reward_scales"] = {}

    camera_cfg = dict(
        res=tuple(args.res),
        pos=(2.5, -2.5, 1.5),
        lookat=(0.0, 0.0, 0.4),
        fov=40,
        GUI=False,   # True にすると cv2 ウィンドウが開き、macOS の Metal と衝突する報告あり
    )

    env = Go2Env(
        num_envs=1,
        env_cfg=env_cfg,
        obs_cfg=obs_cfg,
        reward_cfg=reward_cfg,
        command_cfg=command_cfg,
        show_viewer=False,
        camera_cfg=camera_cfg,
    )
    cam = env.cam

    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    runner.load(os.path.join(log_dir, f"model_{args.ckpt}.pt"))
    policy = runner.get_inference_policy(device=gs.device)

    # 評価中は指令の再サンプリングを無効化(台本で上書きする)
    env._resample_commands = lambda envs_idx: None

    obs_dict = env.reset()
    # v1.4.4: start_recording(save_to_filename, fps) / stop_recording() は引数なし
    # (docs「latest」の stop_recording(save_to_filename=...) は旧 API。v1.4.4 では TypeError になる)
    # 録画中は scene.step() ごとにカメラが自動で描画・エンコードされるので、cam.render() を明示的に呼ばない
    cam.start_recording(save_to_filename=args.out, fps=args.fps)
    t0 = time.time()
    n_frames = 0
    with torch.no_grad():
        for dur, vx, vy, wz in SCRIPT:
            env.commands[:] = torch.tensor([vx, vy, wz], dtype=gs.tc_float, device=gs.device)
            for _ in range(int(dur / env.dt)):
                actions = policy(obs_dict)
                obs_dict, rews, dones, infos = env.step(actions)
                if args.follow:
                    base = env.base_pos[0].cpu().numpy()
                    cam.set_pose(pos=(base[0] + 2.5, base[1] - 2.5, 1.5), lookat=(base[0], base[1], 0.4))
                n_frames += 1
                if bool(dones[0]):
                    print(f"[go2_record] fell / reset at frame {n_frames} (cmd vx={vx}, yaw={wz})")
    elapsed = time.time() - t0
    cam.stop_recording()
    print(f"[go2_record] wrote {args.out}: {n_frames} frames, sim {n_frames * env.dt:.1f}s, "
          f"wall {elapsed:.1f}s ({n_frames / elapsed:.1f} steps/s incl. render)")


if __name__ == "__main__":
    main()
