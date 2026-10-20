"""
eval/scenes.py — 正方形巡回経路の周辺に障害物を乱数配置する(seed で再現可能)。

配置の制約(タスク T03):
  * 領域 area = (-0.5, 2.5) の正方形(x, y とも)
  * Box: 0.3〜0.5 m 角、高さ 0.6 m / Cylinder: 半径 0.1〜0.2 m、高さ 0.7 m
    (初期姿勢ではセンサが z=0.57 にあるため、0.5 m の Box は見えない → 0.6 m 以上)
  * ウェイポイントの表面クリアランス 0.5 m 以上、初期位置 (0,0) から 1.0 m 以上
  * 障害物同士は表面間 1.2 m 以上(Go2 が通れる幅)
配置は results/scenes/seed_NN.json に保存する。

使い方:
  python eval/scenes.py --seed 0 1 2          # 生成して JSON 保存、件数を表示
"""

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SQUARE_WAYPOINTS = [(2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]
START = (0.0, 0.0)
BOX_H, CYL_H = 0.6, 0.7
SCENE_DIR = "results/scenes"


def _radius(o):
    """障害物の外接円半径(xy)。クリアランス計算用"""
    if o["type"] == "box":
        return 0.5 * math.hypot(o["size"][0], o["size"][1])
    return o["radius"]


def make_obstacle_spec(seed, n_min=3, n_max=6, area=(-0.5, 2.5), wp_clear=0.5, start_clear=1.0, gap=1.2,
                       waypoints=SQUARE_WAYPOINTS, max_tries=5000):
    """配置の dict(JSON 保存用)を返す。genesis 不要。seed < 0 なら障害物なし。"""
    if seed is None or seed < 0:
        return dict(seed=-1, n_target=0, n_placed=0, obstacles=[])
    rng = np.random.default_rng(seed)
    n_target = int(rng.integers(n_min, n_max + 1))
    spec = []
    tries = 0
    while len(spec) < n_target and tries < max_tries:
        tries += 1
        if rng.random() < 0.5:
            s = float(rng.uniform(0.3, 0.5))
            o = dict(type="box", size=[s, s, BOX_H])
        else:
            o = dict(type="cylinder", radius=float(rng.uniform(0.1, 0.2)), height=CYL_H)
        x, y = rng.uniform(area[0], area[1], size=2)
        o["pos"] = [float(x), float(y)]
        r = _radius(o)
        if any(math.hypot(x - wx, y - wy) < wp_clear + r for wx, wy in waypoints):
            continue
        if math.hypot(x - START[0], y - START[1]) < start_clear + r:
            continue
        if any(math.hypot(x - p["pos"][0], y - p["pos"][1]) < gap + r + _radius(p) for p in spec):
            continue
        spec.append(o)
    return dict(seed=seed, n_target=n_target, n_placed=len(spec), area=list(area), wp_clear=wp_clear,
                start_clear=start_clear, gap=gap, obstacles=spec)


def make_obstacles(seed, return_spec=False, **kwargs):
    """障害物の gs.morphs リストを返す(gs.init() 後に呼ぶ)。return_spec=True なら (morphs, meta)。"""
    meta = make_obstacle_spec(seed, **kwargs)
    morphs = spec_to_morphs(meta["obstacles"])
    return (morphs, meta) if return_spec else morphs


def spec_to_morphs(spec):
    import genesis as gs
    morphs = []
    for o in spec:
        x, y = o["pos"]
        if o["type"] == "box":
            morphs.append(gs.morphs.Box(pos=(x, y, o["size"][2] / 2), size=tuple(o["size"]), fixed=True))
        else:
            morphs.append(gs.morphs.Cylinder(pos=(x, y, o["height"] / 2), radius=o["radius"], height=o["height"],
                                             fixed=True))
    return morphs


def scene_path(seed):
    return os.path.join(SCENE_DIR, f"seed_{seed:02d}.json")


def save_scene(meta, path=None):
    path = path or scene_path(meta["seed"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    return path


def load_scene(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, nargs="+", default=[0, 1, 2])
    args = parser.parse_args()
    for seed in args.seed:
        meta = make_obstacle_spec(seed)
        p = save_scene(meta)
        kinds = ", ".join(f"{o['type']}@({o['pos'][0]:.2f},{o['pos'][1]:.2f})" for o in meta["obstacles"])
        print(f"seed {seed}: placed {meta['n_placed']}/{meta['n_target']} -> {p}\n    {kinds}")


if __name__ == "__main__":
    main()
