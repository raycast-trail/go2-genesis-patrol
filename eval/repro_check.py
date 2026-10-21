"""
eval/repro_check.py — 再現性の切り分け(T07 手順 1)。seed 12・拡張方策・v2 回避ありを条件ごとに N 回実行し、
到達数・所要時間・接触・走行距離を results/repro_seed12.csv に書く。

条件(各 N 回、既定 3):
  a  --no-video(評価バッチと同じ。別プロセス)
  b  録画あり(俯瞰)
  c  録画あり + --mcap
  d  --no-video --camera-only(カメラは作るが録画しない)
  e  --no-video を 1 プロセス内で N 回連続(評価バッチの実行形態)
a〜d は go2_patrol.py を別プロセスで起動する(単発実行と同じ)。e は run_patrol を同一プロセスで繰り返す。

使い方: python eval/repro_check.py --seed 12 --reps 3 --out results/repro_seed12.csv
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CONDS = {
    "a": ("no-video (separate process)", ["--no-video"]),
    "b": ("video (overhead)", []),
    "c": ("video + mcap", ["--mcap", "{scratch}/repro_{cond}_{rep}.mcap"]),
    "d": ("no-video + camera-only", ["--no-video", "--camera-only"]),
}
PAT = re.compile(r"(\d+) steps, sim ([\d.]+)s, wall ([\d.]+)s, waypoints reached (\d+)/(\d+), end reason: (\w+)")
PAT2 = re.compile(r"contact steps=(\d+) first=(\S+); path length=([\d.]+) m")


def run_cli(args_list, scratch, cond, rep, seed, version):
    out = os.path.join(scratch, f"repro_{cond}_{rep}.mp4")
    cmd = [sys.executable, "go2_patrol.py", "-e", "go2-patrol", "--ckpt", "299", "--backend", "cpu", "--seed", str(seed),
           "--avoid", "--avoid-version", version, "--summary-csv", "", "--out", out]
    cmd += [a.format(scratch=scratch, cond=cond, rep=rep) for a in args_list]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    wall = time.time() - t0
    m, m2 = PAT.search(p.stdout), PAT2.search(p.stdout)
    if not m:
        print(p.stdout[-2000:], p.stderr[-2000:])
        raise RuntimeError(f"parse failed for {cmd}")
    return dict(steps=int(m.group(1)), sim_s=float(m.group(2)), reached=int(m.group(4)), end_reason=m.group(6),
                contact_steps=int(m2.group(1)), path_length_m=float(m2.group(3)), wall_s=round(wall, 1))


def run_inprocess(reps, seed, version):
    import genesis as gs
    from go2_patrol import run_patrol
    gs.init(backend=gs.cpu, logging_level="warning")
    rows = []
    for rep in range(reps):
        t0 = time.time()
        r = run_patrol("go2-patrol", 299, seed=seed, avoid=True, out=None, verbose=False, avoid_version=version)
        rows.append(dict(steps=r["n_steps"], sim_s=r["sim_s"], reached=r["reached"], end_reason=r["end_reason"],
                         contact_steps=r["n_contact"], path_length_m=round(r["path_length"], 3),
                         wall_s=round(time.time() - t0, 1)))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=12)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--version", default="v2")
    parser.add_argument("--conds", default="abcde")
    parser.add_argument("--scratch", default="/tmp/repro_check")
    parser.add_argument("--out", default="results/repro_seed12.csv")
    args = parser.parse_args()
    os.makedirs(args.scratch, exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    rows = []
    for cond in args.conds:
        if cond == "e":
            for rep, r in enumerate(run_inprocess(args.reps, args.seed, args.version), 1):
                rows.append(dict(cond="e", desc="no-video, same process x%d" % args.reps, rep=rep, **r))
                print(f"[repro] e rep {rep}: {r}", flush=True)
            continue
        desc, extra = CONDS[cond]
        for rep in range(1, args.reps + 1):
            r = run_cli(extra, args.scratch, cond, rep, args.seed, args.version)
            rows.append(dict(cond=cond, desc=desc, rep=rep, **r))
            print(f"[repro] {cond} rep {rep}: {r}", flush=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cond", "desc", "rep", "reached", "end_reason", "sim_s", "steps", "contact_steps",
                                          "path_length_m", "wall_s"])
        w.writeheader()
        w.writerows(rows)
    print(f"[repro] wrote {args.out}")


if __name__ == "__main__":
    main()
