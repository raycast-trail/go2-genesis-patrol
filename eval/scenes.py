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


LOWBOX_H = 0.15                 # 低い箱の高さ(T12: 遊脚 0.022 m より上、センサ面 0.44 m より下)
TABLE_TOP_BOTTOM = 0.316        # 天板の下面 = 立位の胴体最高点 0.346 − 0.03(T12 手順 1 の実測)
TABLE_THICKNESS = 0.04          # 天板の厚さ(上面 0.356 < センサ z − 0.03 = 0.408)
TABLE_LEG_R = 0.02
TABLE_LEG_INSET = 0.10          # 脚は天板中央から ±0.10 m(2D には細い脚だけが見え、膨張しても天板の下に入れる)


def _radius(o):
    """障害物の外接円半径(xy)。クリアランス計算用"""
    if o["type"] in ("box", "lowbox"):
        return 0.5 * math.hypot(o["size"][0], o["size"][1])
    if o["type"] == "table":
        return 0.5 * math.hypot(o["top_size"], o["top_size"])
    return o["radius"]


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def path_clearance(o, waypoints=SQUARE_WAYPOINTS):
    """障害物表面から巡回経路(辺)までの最小距離。< 0.2 なら経路上"""
    pts = [START] + list(waypoints)
    return min(_seg_dist(o["pos"], pts[i], pts[i + 1]) for i in range(len(pts) - 1)) - _radius(o)


def make_mixed_spec(seed, area=(-1.0, 3.0), wp_clear=0.5, start_clear=1.0, gap=0.8, waypoints=SQUARE_WAYPOINTS,
                    max_tries=5000, max_scene_tries=200):
    """T12 の混合配置(seed 100〜): 高い障害物 1〜2、低い箱 1〜2、テーブル 1。
    テーブル(外接半径 ≈ 0.5 m)が入るよう領域を 4 m 角、障害物間の表面間隔を 0.8 m にしている(既定配置は 3 m 角・1.2 m)。
    低い箱が 1 つ以上置け、かつ経路上(表面クリアランス < 0.2 m)に低い箱かテーブルが少なくとも 1 つ来るまで配置をやり直す"""
    rng = np.random.default_rng(seed)
    for scene_try in range(max_scene_tries):
        n_high, n_low = int(rng.integers(1, 3)), int(rng.integers(1, 3))
        plan = ["lowbox"] * n_low + ["table"] + ["high"] * n_high      # 低い箱を先に置く(テーブルで領域が埋まる前に)
        spec, tries = [], 0
        for kind in plan:
            placed = False
            while tries < max_tries and not placed:
                tries += 1
                if kind == "table":
                    o = dict(type="table", top_size=float(rng.uniform(0.7, 0.8)), top_z_bottom=TABLE_TOP_BOTTOM,
                             thickness=TABLE_THICKNESS, leg_radius=TABLE_LEG_R, leg_inset=TABLE_LEG_INSET)
                elif kind == "lowbox":
                    w = float(rng.uniform(0.3, 0.5))
                    o = dict(type="lowbox", size=[w, w, LOWBOX_H])
                elif rng.random() < 0.5:
                    w = float(rng.uniform(0.3, 0.5))
                    o = dict(type="box", size=[w, w, BOX_H])
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
                placed = True
        on_path = [o["type"] for o in spec if o["type"] in ("lowbox", "table") and path_clearance(o, waypoints) < 0.2]
        if on_path and any(o["type"] == "lowbox" for o in spec) and any(o["type"] == "table" for o in spec):
            return dict(seed=seed, profile="mixed", n_target=len(plan), n_placed=len(spec), area=list(area), wp_clear=wp_clear,
                        start_clear=start_clear, gap=gap, on_path_types=on_path, scene_tries=scene_try + 1, obstacles=spec)
    raise RuntimeError(f"seed {seed}: no mixed scene with a low obstacle on the path after {max_scene_tries} tries")


def make_obstacle_spec(seed, n_min=3, n_max=6, area=(-0.5, 2.5), wp_clear=0.5, start_clear=1.0, gap=1.2,
                       waypoints=SQUARE_WAYPOINTS, max_tries=5000, profile=None):
    """配置の dict(JSON 保存用)を返す。genesis 不要。seed < 0 なら障害物なし。
    profile=None のとき seed ≥ 100 は mixed(T12)、それ以外は従来どおり(seed 0〜49 の配置は変わらない)"""
    if seed is None or seed < 0:
        return dict(seed=-1, n_target=0, n_placed=0, obstacles=[])
    if profile == "mixed" or (profile is None and seed >= 100):
        return make_mixed_spec(seed, area=area, wp_clear=wp_clear, start_clear=start_clear, gap=gap, waypoints=waypoints,
                               max_tries=max_tries)
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
        if o["type"] in ("box", "lowbox"):
            morphs.append(gs.morphs.Box(pos=(x, y, o["size"][2] / 2), size=tuple(o["size"]), fixed=True))
        elif o["type"] == "table":
            s, zb, th = o["top_size"], o["top_z_bottom"], o["thickness"]
            morphs.append(gs.morphs.Box(pos=(x, y, zb + th / 2), size=(s, s, th), fixed=True))          # 天板
            ins = o.get("leg_inset", TABLE_LEG_INSET)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    morphs.append(gs.morphs.Cylinder(pos=(x + sx * ins, y + sy * ins, zb / 2), radius=o["leg_radius"],
                                                     height=zb, fixed=True))                            # 脚 4 本
        else:
            morphs.append(gs.morphs.Cylinder(pos=(x, y, o["height"] / 2), radius=o["radius"], height=o["height"],
                                             fixed=True))
    return morphs


def scene_path(seed):
    return os.path.join(SCENE_DIR, f"seed_{seed:02d}.json")   # seed ≥ 100 は seed_1NN.json


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
    parser.add_argument("--profile", choices=["default", "mixed"], default=None, help="mixed = T12(低い箱・テーブル入り)")
    args = parser.parse_args()
    for seed in args.seed:
        meta = make_obstacle_spec(seed, profile=args.profile)
        p = save_scene(meta)
        kinds = ", ".join(f"{o['type']}@({o['pos'][0]:.2f},{o['pos'][1]:.2f})" for o in meta["obstacles"])
        extra = f" on_path={meta['on_path_types']} tries={meta['scene_tries']}" if "on_path_types" in meta else ""
        print(f"seed {seed}: placed {meta['n_placed']}/{meta['n_target']} -> {p}{extra}\n    {kinds}")


if __name__ == "__main__":
    main()
