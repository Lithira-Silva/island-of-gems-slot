"""Reference math engine for Lanka Tusker Treasures.

This module is the single source of truth for game rules. The frontend demo
(frontend/index.html, `MathEngine`) mirrors it 1:1 and must stay in sync.
All win amounts are expressed as multiples of the TOTAL bet.
"""
from __future__ import annotations

import json
from pathlib import Path

ROWS = 3
REELS = 5
WILD = "W"
SCATTER = "S"

ROOT = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "game_design.json"
CONFIG_PATH = ROOT / "out" / "game_config.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Engine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.paylines = cfg["paylines"]
        self.n_lines = len(self.paylines)
        self.pays = {s: {int(k): v for k, v in p.items()} for s, p in cfg["linePays"].items()}
        self.scatter_pays = {int(k): v for k, v in cfg["scatterPays"].items()}
        fs = cfg["freeSpins"]
        self.fs_award = {int(k): v for k, v in fs["award"].items()}
        self.fs_retrigger = {int(k): v for k, v in fs["retrigger"].items()}
        self.mult_start = fs["multiplierStart"]
        self.mult_step = fs["multiplierStep"]
        self.mult_max = fs["multiplierMax"]
        self.max_win = cfg["maxWinMultiplier"]
        self.strips = cfg.get("strips")

    # ---- board -------------------------------------------------------------
    def draw(self, rng, mode: str):
        strips = self.strips[mode]
        stops = [rng.randrange(len(s)) for s in strips]
        board = [[s[(st + r) % len(s)] for r in range(ROWS)] for s, st in zip(strips, stops)]
        return stops, board

    # ---- evaluation --------------------------------------------------------
    def line_win(self, syms):
        """Left-to-right line evaluation. Wild substitutes for everything except scatter.
        Returns (symbol, count, pay_in_line_bets) or None."""
        wild_run = 0
        while wild_run < REELS and syms[wild_run] == WILD:
            wild_run += 1
        wild_pay = self.pays[WILD].get(wild_run, 0)
        if wild_run == REELS:
            return (WILD, REELS, wild_pay)

        base = syms[wild_run]
        if base == SCATTER:
            return (WILD, wild_run, wild_pay) if wild_pay else None

        count = wild_run
        for s in syms[wild_run:]:
            if s == base or s == WILD:
                count += 1
            else:
                break
        sub_pay = self.pays[base].get(count, 0)
        if wild_pay > 0 and wild_pay >= sub_pay:
            return (WILD, wild_run, wild_pay)
        if sub_pay > 0:
            return (base, count, sub_pay)
        return None

    def evaluate(self, board):
        wins = []
        for i, line in enumerate(self.paylines):
            res = self.line_win([board[r][line[r]] for r in range(REELS)])
            if res:
                sym, count, pay = res
                wins.append({"line": i, "symbol": sym, "count": count, "pay": pay})
        scatters = [[r, row] for r in range(REELS) for row in range(ROWS) if board[r][row] == SCATTER]
        line_total = sum(w["pay"] for w in wins) / self.n_lines
        scatter_total = self.scatter_pays.get(len(scatters), 0)
        return wins, scatters, line_total + scatter_total

    # ---- full round ---------------------------------------------------------
    def play_round(self, rng, record: bool = False) -> dict:
        events = []
        stops, board = self.draw(rng, "base")
        wins, scatters, base_win = self.evaluate(board)
        if record:
            events.append({"type": "reveal", "gameType": "basegame", "stops": stops, "board": board})
            if wins or base_win:
                events.append({"type": "winInfo", "wins": wins, "scatters": scatters, "amount": round(base_win, 4)})

        free_win = 0.0
        fs_spins = 0
        n_sc = len(scatters)
        if n_sc >= 3:
            left = self.fs_award[min(n_sc, 5)]
            mult = self.mult_start
            if record:
                events.append({"type": "freeSpinTrigger", "totalFs": left, "positions": scatters})
            while left > 0:
                left -= 1
                fs_spins += 1
                stops, board = self.draw(rng, "free")
                wins, scatters, raw = self.evaluate(board)
                win = raw * mult
                free_win += win
                if record:
                    events.append({"type": "reveal", "gameType": "freegame", "stops": stops, "board": board,
                                   "spin": fs_spins, "multiplier": mult})
                    if raw:
                        events.append({"type": "winInfo", "wins": wins, "scatters": scatters,
                                       "multiplier": mult, "amount": round(win, 4)})
                if raw > 0:
                    mult = min(mult + self.mult_step, self.mult_max)
                if len(scatters) >= 3:
                    add = self.fs_retrigger[min(len(scatters), 5)]
                    left += add
                    if record:
                        events.append({"type": "freeSpinRetrigger", "added": add, "positions": scatters})
                if base_win + free_win >= self.max_win:
                    break

        total = base_win + free_win
        capped = total >= self.max_win
        if capped:
            total = self.max_win
            free_win = max(0.0, total - base_win)
        if record:
            if capped:
                events.append({"type": "maxWinReached", "amount": total})
            events.append({"type": "finalWin", "amount": round(total, 4)})
        return {
            "total": total,
            "base": base_win,
            "free": free_win,
            "fsTriggered": n_sc >= 3,
            "fsSpins": fs_spins,
            "capped": capped,
            "events": events,
        }
