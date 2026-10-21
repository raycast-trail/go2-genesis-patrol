"""
nav/planner.py — 占有格子上の A*(8 近傍、対角 √2、ユークリッド・ヒューリスティック)とローカル目標の切り出し。

  * 通行不可 = 膨張後の占有セル。未知は通行可
  * 対角移動は角をかすめない(両隣の直交セルが空いているときだけ)
  * 開始セルが通行不可(回避中に障害物の膨張領域にいる)なら、最寄りの通行可セルから計画する
  * 経路が無ければ膨張半径を縮めて再試行し、それでも無ければ None(呼び出し側で直線 = v1 の挙動に戻す)
"""

import heapq
import math

import numpy as np

_NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
       (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]


def nearest_free(blocked, cell, max_r=10):
    ix, iy = cell
    ny, nx = blocked.shape
    if not blocked[iy, ix]:
        return cell
    for r in range(1, max_r + 1):
        best = None
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x2, y2 = ix + dx, iy + dy
                if 0 <= x2 < nx and 0 <= y2 < ny and not blocked[y2, x2]:
                    d = dx * dx + dy * dy
                    if best is None or d < best[0]:
                        best = (d, (x2, y2))
        if best:
            return best[1]
    return None


def astar(blocked, start, goal):
    """blocked: bool (ny, nx)、start/goal: (ix, iy)。セル列 [(ix, iy), ...] または None"""
    ny, nx = blocked.shape
    sx, sy = start
    gx, gy = goal
    if not (0 <= gx < nx and 0 <= gy < ny):
        return None
    if blocked[gy, gx]:
        g2 = nearest_free(blocked, goal, max_r=8)
        if g2 is None:
            return None
        gx, gy = g2
    h = lambda x, y: math.hypot(x - gx, y - gy)
    g_cost = {(sx, sy): 0.0}
    parent = {}
    heap = [(h(sx, sy), 0.0, sx, sy)]
    closed = set()
    while heap:
        f, g, x, y = heapq.heappop(heap)
        if (x, y) in closed:
            continue
        closed.add((x, y))
        if (x, y) == (gx, gy):
            path = [(x, y)]
            while (x, y) in parent:
                x, y = parent[(x, y)]
                path.append((x, y))
            return path[::-1]
        for dx, dy, c in _NB:
            x2, y2 = x + dx, y + dy
            if not (0 <= x2 < nx and 0 <= y2 < ny) or blocked[y2, x2]:
                continue
            if dx != 0 and dy != 0 and (blocked[y, x2] or blocked[y2, x]):
                continue   # 角をかすめない
            ng = g + c
            if ng < g_cost.get((x2, y2), float("inf")):
                g_cost[(x2, y2)] = ng
                parent[(x2, y2)] = (x, y)
                heapq.heappush(heap, (ng + h(x2, y2), ng, x2, y2))
    return None


class Planner:
    def __init__(self, gmap, inflate=0.35, inflate_retry=0.25, lookahead=0.8):
        self.gmap, self.inflate, self.inflate_retry, self.lookahead = gmap, inflate, inflate_retry, lookahead
        self.path_xy = None          # 最新の経路(world)
        self.last_inflate = None
        self.n_plans = 0
        self.n_fail = 0
        self.n_retry = 0

    def plan(self, pos_xy, goal_xy):
        """pos → goal の経路(world 座標のリスト)。見つからなければ None"""
        self.n_plans += 1
        start = self.gmap.to_cell(*pos_xy)
        goal = self.gmap.to_cell(*goal_xy)
        for k, r in enumerate([self.inflate, self.inflate_retry]):
            blocked = self.gmap.inflated(r)
            s = nearest_free(blocked, start, max_r=10)
            if s is None:
                continue
            cells = astar(blocked, s, goal)
            if cells is not None:
                if k > 0:
                    self.n_retry += 1
                self.last_inflate = r
                self.path_xy = [self.gmap.to_world(ix, iy) for ix, iy in cells]
                # 終点を正確な目標に
                self.path_xy.append((float(goal_xy[0]), float(goal_xy[1])))
                return self.path_xy
        self.n_fail += 1
        self.path_xy = None
        return None

    def local_goal(self, pos_xy):
        """経路上で現在位置の最寄り点から lookahead 先の点。経路が無ければ None"""
        if not self.path_xy:
            return None
        p = np.asarray(self.path_xy)
        d = np.hypot(p[:, 0] - pos_xy[0], p[:, 1] - pos_xy[1])
        i = int(np.argmin(d))
        acc = 0.0
        for j in range(i, len(p) - 1):
            seg = math.hypot(p[j + 1, 0] - p[j, 0], p[j + 1, 1] - p[j, 1])
            if acc + seg >= self.lookahead:
                t = (self.lookahead - acc) / seg if seg > 0 else 0.0
                return (float(p[j, 0] + t * (p[j + 1, 0] - p[j, 0])), float(p[j, 1] + t * (p[j + 1, 1] - p[j, 1])))
            acc += seg
        return (float(p[-1, 0]), float(p[-1, 1]))
