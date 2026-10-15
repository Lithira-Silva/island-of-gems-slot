"""RTP / volatility analysis and book generation, per bet mode.

  python simulate.py exact                              # exact base parts + MC free spins and buy modes (fast, use for tuning)
  python simulate.py mc --mode base --rounds 2400000    # full Monte Carlo of one mode: RTP, hit rate, volatility, distribution
  python simulate.py books --mode bonus --rounds 100000 # write books + lookup table for one mode (Stake Engine-style outputs)

Book/lookup format is modelled on the Stake Engine math-sdk outputs
(books_<mode>.jsonl + lookUpTable_<mode>_0.csv with integer payoutMultiplier = x100 of the base bet).
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

from engine import CONFIG_PATH, REELS, ROWS, SCATTER, WILD, Engine, load_config

BUCKETS = [0, 0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500, 1000, 2500, 5000, 10000, float("inf")]


# ---------------------------------------------------------------- exact parts
def reel_dists(eng: Engine, mode: str) -> list[dict[str, list[tuple[str, float]]]]:
    """Per reel, the distribution of one line cell: unconditioned ('any'), given the window shows no scatter
    ('noS'), and given it shows one ('S': the cell is the scatter 1/3 of the time)."""
    out = []
    for strip in eng.strips[mode]:
        c = Counter(strip)
        non = {s: n for s, n in c.items() if s != SCATTER}
        tot = sum(non.values())
        no_s = [(s, n / tot) for s, n in non.items()]
        out.append({"any": [(s, n / len(strip)) for s, n in c.items()], "noS": no_s,
                    "S": [(SCATTER, 1 / ROWS)] + [(s, f * (ROWS - 1) / ROWS) for s, f in no_s]})
    return out


def exact_line_rtp(eng: Engine, mode: str, wild_reels: tuple[int, ...] = (), freqs: list | None = None) -> float:
    """Exact expected line win (x bet) for one spin. Each line position on reel r is distributed by the strip's
    symbol frequencies, independent per reel; reels in `wild_reels` are fully wild."""
    if freqs is None:
        freqs = [d["any"] for d in reel_dists(eng, mode)]
    freqs = [[(WILD, 1.0)] if r in wild_reels else f for r, f in enumerate(freqs)]
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


def stampede_line_rtp(eng: Engine) -> tuple[float, float, float]:
    """Base line RTP including Elephant Stampede, exact up to strip-neighbour effects. Enumerates which candidate
    reels show a scatter (those cannot be picked), the reel count, and every equally likely pick; reels that were
    not picked keep the cell distribution conditioned on their scatter state.
    Returns (total line RTP, line RTP without stampede, stampede contribution)."""
    plain = exact_line_rtp(eng, "base")
    st = eng.stampede
    if not st:
        return plain, plain, 0.0
    p = st["chance"][0] / st["chance"][1]
    wsum = sum(st["countWeights"].values())
    dists = reel_dists(eng, "base")
    q = {r: ROWS * eng.strips["base"][r].count(SCATTER) / len(eng.strips["base"][r]) for r in st["reels"]}
    cache: dict = {}
    with_st = 0.0
    for state in itertools.product((False, True), repeat=len(st["reels"])):  # True = reel shows a scatter
        has_s = dict(zip(st["reels"], state))
        p_state = math.prod(q[r] if s else 1 - q[r] for r, s in has_s.items())
        avail = [r for r in st["reels"] if not has_s[r]]
        freqs = [dists[r]["any"] if r not in has_s else dists[r]["S" if has_s[r] else "noS"] for r in range(REELS)]
        for k, w in st["countWeights"].items():
            subsets = list(itertools.combinations(avail, min(int(k), len(avail))))
            ev = 0.0
            for sub in subsets:
                key = (state, sub)
                if key not in cache:
                    cache[key] = exact_line_rtp(eng, "base", sub, freqs)
                ev += cache[key]
            with_st += p_state * w / wsum * ev / len(subsets)
    total = (1 - p) * plain + p * with_st
    return total, plain, total - plain


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


def fs_session(eng: Engine, rng: random.Random, spins: int, mult: int) -> float:
    left, win = spins, 0.0
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
    eng = Engine(load_config())
    rng = random.Random(seed)
    s = s2 = 0.0
    for _ in range(n):
        w = fs_session(eng, rng, spins, eng.mult_start)
        s += w
        s2 += w * w
    return s, s2, n


def _mode_worker(args):
    seed, mode, n = args
    eng = Engine(load_config())
    rng = random.Random(seed)
    s = s2 = 0.0
    for _ in range(n):
        w = eng.play_round(rng, mode=mode)["total"]
        s += w
        s2 += w * w
    return s, s2, n


def _mean_se(parts):
    s = sum(p[0] for p in parts); s2 = sum(p[1] for p in parts); n = sum(p[2] for p in parts)
    mean = s / n
    return mean, math.sqrt(max(0.0, s2 / n - mean * mean) / n), n


def cmd_exact(eng: Engine, sessions: int, workers: int):
    t = time.time()
    target = eng.cfg["targetRtp"]
    line, plain, st = stampede_line_rtp(eng)
    dist = scatter_count_dist(eng, "base")
    scat = sum(dist[k] * eng.scatter_pays.get(k, 0) for k in range(len(dist)))
    p_trigger = sum(dist[3:])
    print(f"Base line RTP (exact)     : {plain * 100:7.3f}%")
    print(f"Elephant Stampede (exact) : {st * 100:7.3f}%   (1 in {eng.stampede['chance'][1] / eng.stampede['chance'][0]:.0f} spins)" if eng.stampede else "Elephant Stampede         : off")
    print(f"Scatter pay RTP (exact)   : {scat * 100:7.3f}%")
    print(f"Free spins trigger        : 1 in {1 / p_trigger:,.1f} spins")

    fs_rtp = 0.0
    chunk = max(1, sessions // workers)
    with Pool(workers) as pool:
        for k in (3, 4, 5):
            if dist[k] == 0:
                continue
            spins = eng.fs_award[k]
            mean, se, n = _mean_se(pool.map(_fs_worker, [(1000 * k + i, spins, chunk) for i in range(workers)]))
            fs_rtp += dist[k] * mean
            print(f"  FS EV | {k} scatters ({spins:2d} spins): {mean:8.2f}x  (+-{se:.2f}, n={n:,})  P={dist[k]:.6f}")
        print(f"Free spins RTP (MC)       : {fs_rtp * 100:7.3f}%   (avg Gem Rush {fs_rtp / p_trigger:.1f}x per trigger)")
        total = line + scat + fs_rtp
        print(f"BASE MODE RTP             : {total * 100:7.3f}%   target {target * 100:.2f}%")
        for mode, m in eng.modes.items():
            if not m.get("buy"):
                continue
            mean, se, n = _mean_se(pool.map(_mode_worker, [(77 + 31 * i, mode, max(1, sessions // 4 // workers)) for i in range(workers)]))
            print(f"{m.get('label', mode):<11} ({mode:>5}) : EV {mean:8.2f}x (+-{se:.2f})  cost {m['cost']}x  ->  RTP {mean / m['cost'] * 100:7.3f}%"
                  f"   (price for target: {mean / target:.1f}x)")
    print(f"({time.time() - t:.1f}s)")


# ---------------------------------------------------------------- full MC
def _mc_worker(args):
    seed, mode, n = args
    eng = Engine(load_config())
    rng = random.Random(seed)
    agg = {"n": 0, "sum": 0.0, "sum2": 0.0, "base": 0.0, "free": 0.0, "hits": 0, "fs": 0, "stampede": 0,
           "capped": 0, "max": 0.0, "buckets": [0] * (len(BUCKETS) - 1)}
    for _ in range(n):
        r = eng.play_round(rng, mode=mode)
        w = r["total"]
        agg["n"] += 1
        agg["sum"] += w
        agg["sum2"] += w * w
        agg["base"] += r["base"]
        agg["free"] += r["free"]
        agg["hits"] += w > 0
        agg["fs"] += r["fsTriggered"]
        agg["stampede"] += r["stampede"] > 0
        agg["capped"] += r["capped"]
        agg["max"] = max(agg["max"], w)
        for i in range(len(BUCKETS) - 1):
            if BUCKETS[i] <= w < BUCKETS[i + 1] or (i == 0 and w == 0):
                agg["buckets"][i] += 1
                break
    return agg


def cmd_mc(mode: str, rounds: int, workers: int, seed: int):
    t = time.time()
    cost = Engine(load_config()).modes[mode]["cost"]
    chunk = rounds // workers
    with Pool(workers) as pool:
        parts = pool.map(_mc_worker, [(seed + i, mode, chunk) for i in range(workers)])
    a = parts[0]
    for p in parts[1:]:
        for k in ("n", "sum", "sum2", "base", "free", "hits", "fs", "stampede", "capped"):
            a[k] += p[k]
        a["max"] = max(a["max"], p["max"])
        a["buckets"] = [x + y for x, y in zip(a["buckets"], p["buckets"])]
    n = a["n"]
    mean = a["sum"] / n
    sd = math.sqrt(a["sum2"] / n - mean * mean)
    stats = {
        "mode": mode,
        "cost": cost,
        "rounds": n,
        "rtp": mean / cost,
        "rtpStdErr": sd / math.sqrt(n) / cost,
        "baseRtp": a["base"] / n / cost,
        "freeRtp": a["free"] / n / cost,
        "hitRate": a["hits"] / n,
        "fsFrequency": n / max(1, a["fs"]),
        "stampedeFrequency": n / max(1, a["stampede"]),
        "stdDev": sd / cost,
        "maxWinObserved": a["max"],
        "maxWinHits": a["capped"],
        "distribution": {f"[{BUCKETS[i]}, {BUCKETS[i + 1]})": a["buckets"][i] / n for i in range(len(BUCKETS) - 1)},
    }
    print(f"Mode              : {mode} (cost {cost}x)")
    print(f"Rounds            : {n:,}")
    print(f"RTP               : {stats['rtp'] * 100:.3f}%  (+-{stats['rtpStdErr'] * 100:.3f}% 1 s.e.)")
    print(f"  base / free     : {stats['baseRtp'] * 100:.3f}% / {stats['freeRtp'] * 100:.3f}%")
    print(f"Hit rate          : {stats['hitRate'] * 100:.2f}%  (1 in {1 / max(stats['hitRate'], 1e-12):.2f})")
    print(f"Free spins        : 1 in {stats['fsFrequency']:,.1f}")
    print(f"Elephant Stampede : 1 in {stats['stampedeFrequency']:,.1f}")
    print(f"Std dev (vol idx) : {stats['stdDev']:.2f}  (per unit of cost)")
    print(f"Max win observed  : {a['max']:.2f}x  (cap hits: {a['capped']})")
    print("Win distribution (x base bet):")
    for k, v in stats["distribution"].items():
        print(f"  {k:>16}: {v * 100:8.4f}%")
    out = CONFIG_PATH.parent / "stats.json"
    allstats = json.loads(out.read_text()) if out.exists() else {}
    if "rtp" in allstats:  # pre-0.3 single-mode file
        allstats = {}
    allstats[mode] = stats
    out.write_text(json.dumps(allstats, indent=2))
    print(f"wrote {out} [{mode}]  ({time.time() - t:.1f}s)")


# ---------------------------------------------------------------- books
def cmd_books(eng: Engine, mode: str, rounds: int, seed: int):
    rng = random.Random(seed)
    out = CONFIG_PATH.parent
    books_path = out / f"books_{mode}.jsonl"
    lut_path = out / f"lookUpTable_{mode}_0.csv"
    with open(books_path, "w", encoding="utf-8") as bf, open(lut_path, "w", newline="") as lf:
        lw = csv.writer(lf)
        for i in range(1, rounds + 1):
            r = eng.play_round(rng, record=True, mode=mode)
            pm = int(round(r["total"] * 100))
            bf.write(json.dumps({"id": i, "payoutMultiplier": pm, "events": r["events"]}, separators=(",", ":")) + "\n")
            lw.writerow([i, 1, pm])
    print(f"wrote {books_path}\nwrote {lut_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["exact", "mc", "books"])
    ap.add_argument("--mode", default="base", help="bet mode for mc / books (base, bonus, super)")
    ap.add_argument("--rounds", type=int, default=1_000_000)
    ap.add_argument("--sessions", type=int, default=200_000, help="FS sessions per trigger size (exact mode)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    eng = Engine(load_config())
    if args.mode not in eng.modes:
        raise SystemExit(f"unknown mode {args.mode!r}; choose from {', '.join(eng.modes)}")
    if args.cmd == "exact":
        cmd_exact(eng, args.sessions, args.workers)
    elif args.cmd == "mc":
        cmd_mc(args.mode, args.rounds, args.workers, args.seed)
    else:
        cmd_books(eng, args.mode, args.rounds, args.seed)


if __name__ == "__main__":
    main()
