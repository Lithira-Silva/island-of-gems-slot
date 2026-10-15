"""Generate parity fixtures from the reference engine (math/engine.py).

Usage:  python tools/parity/gen_fixtures.py [--boards 100000] [--rounds 20000] [--seed 20261015] [--out tools/parity/fixtures.jsonl]

Each line is one JSON fixture:
  {"kind": "board", "src": "base|free|uniform|edge", "board": [...], "wins": [...], "scatters": [...], "total": x}
  {"kind": "round", "mode": m, "payoutMultiplier": n, "events": [...], "draws": [[range, value], ...]}
      # full round; JS replays Python's exact random draws (stops, stampede rolls, buy-mode redraws)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "math"))
from engine import Engine, load_config, REELS, ROWS  # noqa: E402

SYMBOLS = ["W", "S", "H1", "H2", "H3", "H4", "H5", "L1", "L2", "L3", "L4"]


def edge_boards() -> list[list[list[str]]]:
    """Hand-picked boards for rules that random draws rarely hit. Boards are reels x rows."""
    col = lambda *rows: list(rows)  # one reel, top to bottom
    fill = lambda s: [col(s, s, s) for _ in range(REELS)]
    boards = [
        fill("W"),                                              # all wilds: 5-wild line on every payline
        fill("S"),                                              # 15 scatters: count > 5, pays nothing extra by table
        [col("W", "W", "W"), col("W", "W", "W"), col("W", "W", "W"), col("H1", "H1", "H1"), col("H1", "H1", "H1")],  # 3 wilds + H1 x5
        [col("W", "W", "W"), col("W", "W", "W"), col("W", "W", "W"), col("L4", "L4", "L4"), col("L4", "L4", "L4")],  # wild-only beats L4 x5
        [col("W", "W", "W"), col("W", "W", "W"), col("W", "W", "W"), col("W", "W", "W"), col("L4", "L4", "L4")],    # 4 wilds vs L4 x5
        [col("W", "W", "W"), col("W", "W", "W"), col("S", "S", "S"), col("H1", "H1", "H1"), col("H1", "H1", "H1")],  # wild run stopped by scatter
        [col("W", "W", "W"), col("W", "W", "W"), col("W", "W", "W"), col("S", "S", "S"), col("H1", "H1", "H1")],    # 3 wilds then scatter
        [col("S", "W", "L1"), col("W", "S", "L1"), col("L1", "W", "S"), col("S", "L2", "W"), col("W", "L3", "S")],    # scatters + wilds share reels
        [col("S", "L1", "L2"), col("S", "L1", "L2"), col("S", "L1", "L2"), col("S", "L1", "L2"), col("S", "L1", "L2")],  # 5 scatters
        [col("S", "L1", "L2"), col("L3", "S", "L2"), col("L3", "L1", "S"), col("H5", "H4", "H3"), col("H2", "H1", "L4")],  # exactly 3
        [col("H1", "H2", "H3"), col("H2", "H3", "H4"), col("H3", "H4", "H5"), col("H4", "H5", "L1"), col("H5", "L1", "L2")],  # no win
        [col("L1", "L1", "L1"), col("W", "W", "W"), col("L1", "L1", "L1"), col("L2", "L2", "L2"), col("L1", "L1", "L1")],  # wild in the middle
        [col("W", "H1", "W"), col("H1", "W", "H1"), col("W", "H1", "W"), col("H1", "W", "H1"), col("W", "H1", "W")],  # checkerboard
    ]
    return boards


class RecordingRandom(random.Random):
    """Logs every randrange(n) the engine makes, so JS can be fed the identical draw sequence."""
    def __init__(self, seed):
        self.log = []
        super().__init__(seed)

    def start(self):
        self.log = []
        return self

    def randrange(self, n):  # the engine only ever calls randrange(n)
        v = super().randrange(n)
        self.log.append([n, v])
        return v


def round_fixture(eng: Engine, rng: RecordingRandom, mode: str, want=lambda r: True) -> dict:
    while True:
        r = eng.play_round(rng.start(), record=True, mode=mode)
        if want(r):
            return {"kind": "round", "mode": mode, "payoutMultiplier": int(round(r["total"] * 100)), "events": r["events"], "draws": rng.log}


def board_fixture(eng: Engine, board, src: str) -> dict:
    wins, scatters, total = eng.evaluate(board)
    return {"kind": "board", "src": src, "board": board, "wins": wins, "scatters": scatters, "total": total}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=100_000, help="random boards per source (base, free, uniform)")
    ap.add_argument("--rounds", type=int, default=21_000, help="base rounds (1/3 natural, 1/3 forced free spins, 1/3 forced stampede); each buy mode gets a tenth as many")
    ap.add_argument("--seed", type=int, default=20261015)
    ap.add_argument("--out", default=str(ROOT / "tools" / "parity" / "fixtures.jsonl"))
    a = ap.parse_args()

    eng = Engine(load_config())
    rng = RecordingRandom(a.seed)
    n = 0
    with open(a.out, "w", encoding="utf-8") as f:
        w = lambda obj: f.write(json.dumps(obj, separators=(",", ":")) + "\n")
        for b in edge_boards():
            w(board_fixture(eng, b, "edge")); n += 1
        for mode in ("base", "free"):
            for _ in range(a.boards):
                _, board = eng.draw(rng, mode)
                w(board_fixture(eng, board, mode)); n += 1
        for _ in range(a.boards):
            board = [[rng.choice(SYMBOLS) for _ in range(ROWS)] for _ in range(REELS)]
            w(board_fixture(eng, board, "uniform")); n += 1
        wants = [lambda r: True, lambda r: r["fsTriggered"], lambda r: r["stampede"] > 0]  # natural, forced FS, forced stampede
        for i in range(a.rounds):
            w(round_fixture(eng, rng, "base", wants[i % 3])); n += 1
        buys = [m for m, cfg in eng.modes.items() if cfg.get("buy")]
        for m in buys:
            for _ in range(max(1, a.rounds // 10)):
                w(round_fixture(eng, rng, m)); n += 1
    print(f"wrote {n} fixtures ({a.rounds} base rounds + {a.rounds // 10} per buy mode: {', '.join(buys)}) to {a.out}")


if __name__ == "__main__":
    main()
