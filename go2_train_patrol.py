"""
go2_train_patrol.py — 巡回(ウェイポイント追従)に使えるよう、速度指令の範囲を広げて Go2 歩行方策を学習する。

v1.4.4 の go2_train.py は command_cfg が vx=[0.5,0.5], vy=[0,0], yaw=[0,0] に固定されていて
「前進 0.5 m/s」しか学ばない。本スクリプトは go2_train.py の設定関数をそのまま使い、
command_cfg だけを上書きする(設定の差分が 1 か所に閉じるようにしている)。

使い方(examples/locomotion 相当のディレクトリで):
  python go2_train_patrol.py -e go2-patrol -b 1024 --max-iterations 300
  python go2_train_patrol.py -e go2-patrol -b 4096 --max-iterations 300 --backend gpu   # Colab / Metal
  tensorboard --logdir logs
"""

import argparse
import os
import pickle
import shutil
from importlib import metadata

try:
    if int(metadata.version("rsl-rl-lib").split(".")[0]) < 5:
        raise ImportError
except (metadata.PackageNotFoundError, ImportError, ValueError) as e:
    raise ImportError("Please install 'rsl-rl-lib>=5.0.0'.") from e
from rsl_rl.runners import OnPolicyRunner

import genesis as gs

from go2_env import Go2Env
from go2_train import get_cfgs, get_train_cfg

# 巡回用の指令範囲。学習時にこの範囲から 4 秒ごとに再サンプリングされる。
# 評価(go2_patrol.py)で与える指令はこの範囲内に収めること。
PATROL_COMMAND_CFG = {
    "num_commands": 3,
    "lin_vel_x_range": [0.0, 0.8],    # 停止〜前進 0.8 m/s(後退は学習しない)
    "lin_vel_y_range": [-0.2, 0.2],   # 横歩きは小さく
    "ang_vel_range": [-0.8, 0.8],     # 旋回 ±0.8 rad/s
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exp-name", type=str, default="go2-patrol")
    parser.add_argument("-b", "--num-envs", type=int, default=1024)
    parser.add_argument("--max-iterations", type=int, default=300,
                        help="指令範囲が広い分、既定(101)より長めに")
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    gs.init(backend=gs.gpu if args.backend == "gpu" else gs.cpu, precision="32",
            logging_level="warning", seed=args.seed, performance_mode=True)
    print(f"[go2_train_patrol] gs.backend={gs.backend} gs.device={gs.device} num_envs={args.num_envs}")

    log_dir = f"logs/{args.exp_name}"
    env_cfg, obs_cfg, reward_cfg, _ = get_cfgs()
    command_cfg = dict(PATROL_COMMAND_CFG)
    train_cfg = get_train_cfg(args.exp_name)
    # 停止指令(vx≈0)も学ぶので、報酬の中で姿勢維持がやや重要になる。既定のままでも学べるが、
    # 立ち止まる時に足踏みし続ける場合は action_rate のペナルティを強める(例: -0.01)。

    if os.path.exists(log_dir):
        shutil.rmtree(log_dir)
    os.makedirs(log_dir, exist_ok=True)
    with open(f"{log_dir}/cfgs.pkl", "wb") as f:
        pickle.dump([env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg], f)

    env = Go2Env(num_envs=args.num_envs, env_cfg=env_cfg, obs_cfg=obs_cfg,
                 reward_cfg=reward_cfg, command_cfg=command_cfg, show_viewer=False)
    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    runner.learn(num_learning_iterations=args.max_iterations, init_at_random_ep_len=True)


if __name__ == "__main__":
    main()
