"""RTP / volatility analysis and book generation.

  python simulate.py exact                 # exact base-game RTP + MC free-spin EV (fast, use for tuning)
  python simulate.py mc --rounds 2000000   # full Monte Carlo, multi-core: RTP, hit rate, volatility, distribution
  python simulate.py books --rounds 100000 # write books + lookup table (Stake Engine-style outputs)

Book/lookup format is modelled on the Stake Engine math-sdk outputs
(books_<mode>.jsonl + lookUpTable_<mode>_0.csv with integer payoutMultiplier = x100).
Verify field names against the current Stake Engine docs before upload.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import random
import time
from collections import Counter
from multiprocessing import Pool

from engine import CONFIG_PATH, REELS, ROWS, SCATTER, Engine, load_config

BUCKETS = [0, 0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500, 1000, 2500, 5000, float("inf")]


# ---------------------------------------------------------------- exact parts
def exact_line_rtp(eng: Engine, mode: str) -> float:
    """Exact expected line win (x total bet) for one spin. Each line position on
    reel r is distributed by the strip's symbol frequencies, independent per reel."""
    freqs = []
    for strip in eng.strips[mode]:
        c = Counter(strip)
        freqs.append([(s, n / len(strip)) for s, n in c.items()])
    ev = 0.0
    for combo in itertools.product(*freqs):
        p = 1.0
        syms = []
        for s, f in combo:
            p *= f
            syms.append(s)
        res = eng.line_win(syms)
        if res:
            ev += p * res[2]
    return ev  # n_lines * E[line pay] / n_lines


def scatter_count_dist(eng: Engine, mode: str) -> list[float]:
    dist = [1.0]
    for strip in eng.strips[mode]:
        p = ROWS * strip.count(SCATTER) / len(strip)  # strips guarantee <=1 scatter per window
        nxt = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            nxt[k] += q * (1 - p)
            nxt[k + 1] += q * p
        dist = nxt
    return dist


def fs_session(eng: Engine, rng: random.Random, spins: int) -> float:
    left, mult, win = spins, eng.mult_start, 0.0
    while left > 0:
        left -= 1
        _, board = eng.draw(rng, "free")
        _, scatters, raw = eng.evaluate(board)
        win += raw * mult
        if raw > 0:
            mult = min(mult + eng.mult_step, eng.mult_max)
        if len(scatters) >= 3:
            left += eng.fs_retrigger[min(len(scatters), 5)]
        if win >= eng.max_win:
            return float(eng.max_win)
    return win


def _fs_worker(args):
    seed, spins, n = args
    cfg = load_config()
    eng = Engine(cfg)
    rng = random.Random(seed)
    s = s2 = 0.0
    for _ in range(n):
        w = fs_session(eng, rng, spins)
        s += w
        s2 += w * w
    return s, s2, n


def cmd_exact(eng: Engine, sessions: int, workers: int):
    t = time.time()
    line = exact_line_rtp(eng, "base")
    dist = scatter_count_dist(eng, "base")
    scat = sum(dist[k] * eng.scatter_pays.get(k, 0) for k in range(len(dist)))
    p_trigger = sum(dist[3:])
    print(f"Base line RTP (exact)     : {line * 100:7.3f}%")
    print(f"Scatter pay RTP (exact)   : {scat * 100:7.3f}%")
    print(f"Free spins trigger        : 1 in {1 / p_trigger:,.1f} spins")

    fs_rtp = 0.0
    with Pool(workers) as pool:
        for k in (3, 4, 5):
            if dist[k] == 0:
                continue
            spins = eng.fs_award[k]
            chunk = max(1, sessions // workers)
            res = pool.map(_fs_worker, [(1000 * k + i, spins, chunk) for i in range(workers)])
            s = sum(r[0] for r in res)
            s2 = sum(r[1] for r in res)
            n = sum(r[2] for r in res)
            mean = s / n
            se = math.sqrt(max(0.0, s2 / n - mean * mean) / n)
            fs_rtp += dist[k] * mean
            print(f"  FS EV | {k} scatters ({spins:2d} spins): {mean:8.2f}x  (+-{se:.2f}, n={n:,})  P={dist[k]:.6f}")
    print(f"Free spins RTP (MC)       : {fs_rtp * 100:7.3f}%")
    total = line + scat + fs_rtp
    print(f"TOTAL RTP                 : {total * 100:7.3f}%   target {eng.cfg['targetRtp'] * 100:.2f}%")
    print(f"({time.time() - t:.1f}s)")


# ---------------------------------------------------------------- full MC
def _mc_worker(args):
    seed, n = args
    eng = Engine(load_config())
    rng = random.Random(seed)
    agg = {"n": 0, "sum": 0.0, "sum2": 0.0, "base": 0.0, "free": 0.0, "hits": 0, "fs": 0,
           "capped": 0, "max": 0.0, "buckets": [0] * (len(BUCKETS) - 1)}
    for _ in range(n):
        r = eng.play_round(rng)
        w = r["total"]
        agg["n"] += 1
        agg["sum"] += w
        agg["sum2"] += w * w
        agg["base"] += r["base"]
        agg["free"] += r["free"]
        agg["hits"] += w > 0
        agg["fs"] += r["fsTriggered"]
        agg["capped"] += r["capped"]
        agg["max"] = max(agg["max"], w)
        for i in range(len(BUCKETS) - 1):
            if BUCKETS[i] <= w < BUCKETS[i + 1] or (i == 0 and w == 0):
                agg["buckets"][i] += 1
                break
    return agg


def cmd_mc(rounds: int, workers: int, seed: int):
    t = time.time()
    chunk = rounds // workers
    with Pool(workers) as pool:
        parts = pool.map(_mc_worker, [(seed + i, chunk) for i in range(workers)])
    a = parts[0]
    for p in parts[1:]:
        for k in ("n", "sum", "sum2", "base", "free", "hits", "fs", "capped"):
            a[k] += p[k]
        a["max"] = max(a["max"], p["max"])
        a["buckets"] = [x + y for x, y in zip(a["buckets"], p["buckets"])]
    n = a["n"]
    mean = a["sum"] / n
    sd = math.sqrt(a["sum2"] / n - mean * mean)
    stats = {
        "rounds": n,
        "rtp": mean,
        "rtpStdErr": sd / math.sqrt(n),
        "baseRtp": a["base"] / n,
        "freeRtp": a["free"] / n,
        "hitRate": a["hits"] / n,
        "fsFrequency": n / max(1, a["fs"]),
        "stdDev": sd,
        "maxWinObserved": a["max"],
        "maxWinHits": a["capped"],
        "distribution": {f"[{BUCKETS[i]}, {BUCKETS[i + 1]})": a["buckets"][i] / n for i in range(len(BUCKETS) - 1)},
    }
    print(f"Rounds            : {n:,}")
    print(f"RTP               : {stats['rtp'] * 100:.3f}%  (+-{stats['rtpStdErr'] * 100:.3f}% 1 s.e.)")
    print(f"  base / free     : {stats['baseRtp'] * 100:.3f}% / {stats['freeRtp'] * 100:.3f}%")
    print(f"Hit rate          : {stats['hitRate'] * 100:.2f}%  (1 in {1 / stats['hitRate']:.2f})")
    print(f"Free spins        : 1 in {stats['fsFrequency']:,.1f}")
    print(f"Std dev (vol idx) : {sd:.2f}")
    print(f"Max win observed  : {a['max']:.2f}x  (cap hits: {a['capped']})")
    print("Win distribution (x bet):")
    for k, v in stats["distribution"].items():
        print(f"  {k:>16}: {v * 100:8.4f}%")
    out = CONFIG_PATH.parent / "stats.json"
    out.write_text(json.dumps(stats, indent=2))
    print(f"wrote {out}  ({time.time() - t:.1f}s)")


# ---------------------------------------------------------------- books
def cmd_books(eng: Engine, rounds: int, seed: int):
    rng = random.Random(seed)
    out = CONFIG_PATH.parent
    books_path = out / "books_base.jsonl"
    lut_path = out / "lookUpTable_base_0.csv"
    with open(books_path, "w", encoding="utf-8") as bf, open(lut_path, "w", newline="") as lf:
        lw = csv.writer(lf)
        for i in range(1, rounds + 1):
            r = eng.play_round(rng, record=True)
            pm = int(round(r["total"] * 100))
            bf.write(json.dumps({"id": i, "payoutMultiplier": pm, "events": r["events"]}, separators=(",", ":")) + "\n")
            lw.writerow([i, 1, pm])
    print(f"wrote {books_path}\nwrote {lut_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["exact", "mc", "books"])
    ap.add_argument("--rounds", type=int, default=1_000_000)
    ap.add_argument("--sessions", type=int, default=200_000, help="FS sessions per trigger size (exact mode)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    eng = Engine(load_config())
    if args.cmd == "exact":
        cmd_exact(eng, args.sessions, args.workers)
    elif args.cmd == "mc":
        cmd_mc(args.rounds, args.workers, args.seed)
    else:
        cmd_books(eng, args.rounds, args.seed)


if __name__ == "__main__":
    main()
