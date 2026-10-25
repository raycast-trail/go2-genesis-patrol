import heapq, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle, Circle

for f in font_manager.findSystemFonts():
    if "NotoSansCJK-Regular" in f or "NotoSansCJKjp-Regular" in f:
        font_manager.fontManager.addfont(f)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name(); break

W, H = 40, 24                      # cells
robot = (4, 12); goal = (36, 12)
# true world: box blocking straight line + a cylinder
true_occ = np.zeros((H, W), bool)
true_occ[7:18, 18:23] = True       # box  (rows=y, cols=x)
yy, xx = np.mgrid[0:H, 0:W]
true_occ |= (xx - 11) ** 2 + (yy - 5) ** 2 <= 2.2 ** 2   # cylinder

# --- 1. LiDAR ray casting -> occupancy grid (free / occupied / unknown)
UNK, FREE, OCC = 0, 1, 2
grid = np.full((H, W), UNK)
rays = []
NR = 180
for k in range(NR):
    a = 2 * math.pi * k / NR
    x, y = robot[0] + .5, robot[1] + .5
    hit = None
    for s in np.arange(0, 30, 0.25):
        cx, cy = x + s * math.cos(a), y + s * math.sin(a)
        ix, iy = int(cx), int(cy)
        if not (0 <= ix < W and 0 <= iy < H): break
        if true_occ[iy, ix]:
            grid[iy, ix] = OCC; hit = (cx, cy); break
        if grid[iy, ix] != OCC: grid[iy, ix] = FREE
    end = hit if hit else (cx, cy)
    rays.append(((x, y), end, hit is not None))

# --- 2. inflation (robot radius ~ 2 cells)
R = 2
occ = grid == OCC
infl = np.zeros_like(occ)
for iy, ix in zip(*np.where(occ)):
    infl |= (xx - ix) ** 2 + (yy - iy) ** 2 <= R ** 2
blocked = infl            # unknown = passable (same convention as v3)

# --- 3/4. Dijkstra vs A*
def search(use_h):
    g = {robot: 0.0}; parent = {}
    pq = [(0.0, robot)]; closed = set(); order = []
    while pq:
        f, c = heapq.heappop(pq)
        if c in closed: continue
        closed.add(c); order.append(c)
        if c == goal: break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0: continue
                n = (c[0] + dx, c[1] + dy)
                if not (0 <= n[0] < W and 0 <= n[1] < H) or blocked[n[1], n[0]]: continue
                if dx and dy and (blocked[c[1], n[0]] or blocked[n[1], c[0]]): continue
                ng = g[c] + (math.sqrt(2) if dx and dy else 1.0)
                if ng < g.get(n, 1e9):
                    g[n] = ng; parent[n] = c
                    h = math.hypot(goal[0] - n[0], goal[1] - n[1]) if use_h else 0.0
                    heapq.heappush(pq, (ng + h, n))
    path = [goal]
    while path[-1] != robot: path.append(parent[path[-1]])
    return order, path[::-1], g[goal]

dj_order, dj_path, dj_len = search(False)
as_order, as_path, as_len = search(True)
print("dijkstra expanded", len(dj_order), "len", dj_len)
print("astar expanded", len(as_order), "len", as_len)

# --- draw
fig, axs = plt.subplots(2, 2, figsize=(12, 7.6))
def frame(ax, title):
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title, fontsize=13, loc="left", pad=6)
def gridlines(ax):
    for i in range(W + 1): ax.axvline(i, color="#d8d8d8", lw=0.4, zorder=1)
    for j in range(H + 1): ax.axhline(j, color="#d8d8d8", lw=0.4, zorder=1)
def markers(ax):
    ax.add_patch(Circle((robot[0] + .5, robot[1] + .5), 0.9, color="#1f77b4", zorder=6))
    ax.text(robot[0] + .5, robot[1] - 1.6, "Go2", ha="center", fontsize=10, color="#1f77b4", zorder=6)
    ax.plot(goal[0] + .5, goal[1] + .5, marker="*", ms=18, color="#d62728", zorder=6)
    ax.text(goal[0] + .5, goal[1] - 1.8, "ゴール", ha="center", fontsize=10, color="#d62728", zorder=6)

# (1) true world + rays
ax = axs[0, 0]; frame(ax, "① LiDAR のレイを放つ(実際の世界)")
ax.add_patch(Rectangle((18, 7), 5, 11, fc="#8c8c8c", ec="none", zorder=1))
ax.add_patch(Circle((11.5, 5.5), 2.2, fc="#8c8c8c", ec="none", zorder=1))
for (p, q, h) in rays:
    ax.plot([p[0], q[0]], [p[1], q[1]], color="#ff9f40" if h else "#ffd8b0", lw=0.7, zorder=2)
    if h: ax.plot(q[0], q[1], "o", ms=3, color="#d62728", zorder=3)
markers(ax)
ax.text(20.5, 18.6, "箱", ha="center", fontsize=11); ax.text(11.5, 8.2, "円柱", ha="center", fontsize=11)
ax.text(0.6, 0.6, "赤点 = レイが物に当たった点。箱の裏側にはレイが届かない", fontsize=9.5, color="#333", zorder=7, bbox=dict(fc="white", ec="none", alpha=0.85, pad=2))

# (2) occupancy grid + inflation
ax = axs[0, 1]; frame(ax, "② 占有格子地図を描き、障害物を膨らませる")
img = np.ones((H, W, 3))
img[grid == UNK] = (0.78, 0.78, 0.78)
img[grid == FREE] = (1, 1, 1)
img[infl & (grid != OCC)] = (1.0, 0.86, 0.70)
img[grid == OCC] = (0.1, 0.1, 0.1)
ax.imshow(img, origin="lower", extent=(0, W, 0, H), interpolation="nearest", zorder=0)
gridlines(ax); markers(ax)
for (lbl, c) in [("物がある(占有)", (0.1, 0.1, 0.1)), ("膨張(ロボットの半径)", (1, .86, .70)), ("何もない(空き)", (1, 1, 1)), ("未知(まだ見ていない)", (.78, .78, .78))]:
    pass
ax.legend(handles=[Rectangle((0, 0), 1, 1, fc=c, ec="#888") for _, c in
                   [("", (0.1, 0.1, 0.1)), ("", (1, .86, .70)), ("", (1, 1, 1)), ("", (.78, .78, .78))]],
          labels=["物がある(占有)", "膨張(ロボットの半径分)", "何もない(空き)", "未知(通れるとみなす)"],
          loc="upper right", fontsize=8.5, framealpha=0.95)

def draw_search(ax, order, path, title, note):
    frame(ax, title)
    img = np.ones((H, W, 3)); img[grid == UNK] = (0.90, 0.90, 0.90)
    for i, c in enumerate(order):
        t = i / max(1, len(order) - 1)
        img[c[1], c[0]] = (0.62 + 0.3 * t, 0.80 + 0.12 * t, 1.0)
    img[infl & (grid != OCC)] = (1.0, 0.86, 0.70); img[grid == OCC] = (0.1, 0.1, 0.1)
    ax.imshow(img, origin="lower", extent=(0, W, 0, H), interpolation="nearest", zorder=0)
    gridlines(ax)
    px = [p[0] + .5 for p in path]; py = [p[1] + .5 for p in path]
    ax.plot(px, py, color="#2ca02c", lw=3, zorder=5)
    markers(ax)
    ax.text(0.6, 0.6, note, fontsize=9.5, color="#111", zorder=7,
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=2))

draw_search(axs[1, 0], dj_order, dj_path, "③ ダイクストラ法: 近いマスから全方向に調べる",
            f"調べたマス {len(dj_order)} 個(水色)/ 経路長 {dj_len:.1f} マス")
draw_search(axs[1, 1], as_order, as_path, "④ A*(エースター): ゴールに近づきそうなマスを優先",
            f"調べたマス {len(as_order)} 個(水色)/ 経路長 {as_len:.1f} マス(③と同じ長さ)")
axs[1, 1].text(39.4, 22.6, "優先度 = ここまでの距離 g\n      + ゴールまでの直線距離 h", ha="right", va="top", fontsize=9.5,
               bbox=dict(fc="white", ec="#2ca02c", pad=3), zorder=7)
axs[1, 1].annotate("箱の裏は未知 → 通れるとみなして計画。\n近づいて見えたら 1 秒ごとに引き直す", xy=(25.5, 10.5), xytext=(13.0, 2.4),
    fontsize=9, ha="left", arrowprops=dict(arrowstyle="->", color="#555"), zorder=8,
    bbox=dict(fc="white", ec="#aaa", pad=2))
fig.tight_layout(h_pad=1.2, w_pad=1.0)
fig.savefig("/home/claude/figwork/astar_explain.png", dpi=150, facecolor="white")
