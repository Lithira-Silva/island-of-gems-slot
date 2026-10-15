"""Rule tests for math/engine.py (the reference engine).

Run:  .venv/Scripts/python -m pytest math/tests -q        (Windows)
      .venv/bin/python -m pytest math/tests -q            (macOS / Linux)
Dev-only dependencies: pytest, hypothesis. engine.py itself stays dependency-free.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Engine, load_config, REELS, ROWS, WILD, SCATTER  # noqa: E402

CFG = load_config()
ENG = Engine(CFG)
PAYING = [s for s in CFG["linePays"]]                 # every symbol with a line pay (wild included)
SYMBOLS = PAYING + [SCATTER]
symbol = st.sampled_from(SYMBOLS)
line = st.lists(symbol, min_size=REELS, max_size=REELS)
board = st.lists(st.lists(symbol, min_size=ROWS, max_size=ROWS), min_size=REELS, max_size=REELS)


def pay(sym: str, n: int) -> int:
    return ENG.pays[sym].get(n, 0)


def brute_line_pay(syms: list[str]) -> tuple[int, str | None]:
    """Independent oracle: try every paying symbol X, count the leading run of X-or-wild, keep the best pay.
    Ties go to the wild. Returns (pay, symbol)."""
    best, best_sym = 0, None
    for x in PAYING:
        n = 0
        for s in syms:
            if s == x or (s == WILD and x != WILD):
                n += 1
            else:
                break
        p = pay(x, n)
        if p > best or (p == best and p > 0 and x == WILD):
            best, best_sym = p, x
    return best, best_sym


# ---- configuration assumptions the evaluator relies on ------------------------------------
def test_wild_pays_most_for_every_count():
    # line_win only compares "wild-only" against "first symbol + wilds"; that is only complete if the wild
    # out-pays every other symbol at the same count.
    for n in (3, 4, 5):
        assert all(pay(WILD, n) >= pay(s, n) for s in PAYING), n


def test_strips_hold_at_most_one_scatter_per_reel_window():
    # build.py's spacing rule. It keeps the scatter count <= 5, which scatterPays and the FS award assume.
    for mode, strips in CFG["strips"].items():
        for r, strip in enumerate(strips):
            L = len(strip)
            for stop in range(L):
                window = [strip[(stop + k) % L] for k in range(ROWS)]
                assert window.count(SCATTER) <= 1, (mode, r, stop, window)


def test_paylines_shape():
    assert all(len(l) == REELS and all(0 <= row < ROWS for row in l) for l in CFG["paylines"])
    assert len({tuple(l) for l in CFG["paylines"]}) == len(CFG["paylines"]), "duplicate payline"


# ---- line evaluation: named rules ----------------------------------------------------------
@pytest.mark.parametrize("syms, expected", [
    (["H1", "W", "H1", "L1", "L2"], ("H1", 3, 50)),       # wild substitutes mid-line
    (["W", "H1", "H1", "L1", "L2"], ("H1", 3, 50)),       # leading wild joins the symbol run
    (["W", "W", "W", "W", "W"], ("W", 5, 2000)),          # all wilds
    (["W", "W", "W", "W", "L4"], ("W", 4, 500)),          # wild-only line beats L4 x5
    (["W", "W", "W", "H1", "H1"], ("H1", 5, 1000)),       # symbol line beats wild-only W x3
    (["W", "W", "W", "L4", "L4"], ("W", 3, 100)),         # tie (100 vs 100): the wild wins
    (["W", "W", "S", "H1", "H1"], None),                  # scatter breaks the run; W x2 pays nothing
    (["W", "W", "W", "S", "H1"], ("W", 3, 100)),          # wild run before a scatter still pays
    (["S", "W", "W", "W", "W"], None),                    # wild never substitutes for the scatter
    (["H1", "H1", "L1", "H1", "H1"], None),               # only adjacent reels from the left count
    (["L1", "L1", "L1", "L1", "L1"], ("L1", 5, 150)),
])
def test_line_win_rules(syms, expected):
    assert ENG.line_win(syms) == expected


@given(line)
@settings(max_examples=5000, deadline=None)
def test_line_win_matches_brute_force(syms):
    res = ENG.line_win(syms)
    best, best_sym = brute_line_pay(syms)
    assert (res[2] if res else 0) == best
    if res:
        sym, n, p = res
        assert sym == best_sym and sym != SCATTER and 1 <= n <= REELS and p == pay(sym, n) > 0


# ---- board evaluation ----------------------------------------------------------------------
@given(board)
@settings(max_examples=2000, deadline=None)
def test_evaluate_totals(b):
    wins, scatters, total = ENG.evaluate(b)
    assert scatters == [[r, row] for r in range(REELS) for row in range(ROWS) if b[r][row] == SCATTER]
    expect = sum(brute_line_pay([b[r][l[r]] for r in range(REELS)])[0] for l in CFG["paylines"]) / len(CFG["paylines"])
    expect += ENG.scatter_pays.get(len(scatters), 0)
    assert total == pytest.approx(expect, abs=1e-12)
    assert [w["line"] for w in wins] == sorted(w["line"] for w in wins)
    assert round(total * 100, 6) == int(round(total * 100)), "wins must be whole cents of the total bet"


def test_scatter_pays_anywhere():
    b = [["S", "L1", "L2"], ["L3", "S", "L2"], ["L3", "L1", "S"], ["H5", "H4", "H3"], ["H2", "H1", "L4"]]
    _, scatters, total = ENG.evaluate(b)
    assert len(scatters) == 3 and total >= ENG.scatter_pays[3]


# ---- full rounds ---------------------------------------------------------------------------
@given(st.integers(min_value=0, max_value=2**32 - 1))
@settings(max_examples=400, deadline=None)
def test_round_invariants(seed):
    r = ENG.play_round(random.Random(seed), record=True)
    ev = r["events"]
    assert 0 <= r["total"] <= ENG.max_win
    assert r["total"] == pytest.approx(r["base"] + r["free"])
    assert round(r["total"] * 100, 6) == int(round(r["total"] * 100)), "payoutMultiplier must be an integer"
    assert ev[-1]["type"] == "finalWin" and ev[-1]["amount"] == round(r["total"], 4)
    if not r["capped"]:
        assert sum(e["amount"] for e in ev if e["type"] == "winInfo") == pytest.approx(r["total"], abs=1e-3)
    reveals = [e for e in ev if e["type"] == "reveal"]
    assert reveals[0]["gameType"] == "basegame"
    for e in reveals:  # every revealed board is the strip window at the recorded stops
        strips = CFG["strips"]["base" if e["gameType"] == "basegame" else "free"]
        assert e["board"] == [[s[(stop + k) % len(s)] for k in range(ROWS)] for s, stop in zip(strips, e["stops"])]
    fs = [e for e in reveals if e["gameType"] == "freegame"]
    if r["fsTriggered"]:
        trig = next(e for e in ev if e["type"] == "freeSpinTrigger")
        awarded = trig["totalFs"] + sum(e["added"] for e in ev if e["type"] == "freeSpinRetrigger")
        assert len(fs) == awarded or r["capped"]
        assert [e["spin"] for e in fs] == list(range(1, len(fs) + 1))
        mult = ENG.mult_start
        for e in fs:  # Gem Multiplier: starts at multiplierStart, +step after each winning spin, capped
            assert e["multiplier"] == mult
            i = ev.index(e)
            won = i + 1 < len(ev) and ev[i + 1]["type"] == "winInfo"
            if won:
                mult = min(mult + ENG.mult_step, ENG.mult_max)
    else:
        assert not fs


def test_max_win_cap(monkeypatch):
    # Force a huge free-spin win: shrink max win so the cap triggers, then check the round stops and reports it.
    eng = Engine(CFG)
    eng.max_win = 5
    for seed in range(20000):
        r = eng.play_round(random.Random(seed), record=True)
        if r["capped"]:
            assert r["total"] == 5
            assert [e["type"] for e in r["events"]][-2:] == ["maxWinReached", "finalWin"]
            return
    pytest.fail("no capped round found")


# ---- Elephant Stampede and bet modes (v0.3) ------------------------------------------------
@given(st.integers(min_value=0, max_value=2**32 - 1))
@settings(max_examples=3000, deadline=None)
def test_stampede_rules(seed):
    rng = random.Random(seed)
    stops, board, wild_reels, played = ENG.base_spin(rng)
    cfg = CFG["stampede"]
    assert len(wild_reels) <= max(int(k) for k in cfg["countWeights"])
    assert wild_reels == sorted(set(wild_reels)) and set(wild_reels) <= set(cfg["reels"])
    for r in range(REELS):
        if r in wild_reels:
            assert SCATTER not in board[r], "a stampede must never cover a scatter"
            assert played[r] == [WILD] * ROWS
        else:
            assert played[r] == board[r]


def test_stampede_frequency_and_reel_counts():
    rng, n, counts = random.Random(5), 200_000, {}
    for _ in range(n):
        k = len(ENG.base_spin(rng)[2])
        counts[k] = counts.get(k, 0) + 1
    num, den = CFG["stampede"]["chance"]
    hit = 1 - counts.get(0, 0) / n
    assert abs(hit - num / den) < 4 * (num / den / n) ** .5 + 1e-3  # a few picks are lost to scatter-only reels
    w = CFG["stampede"]["countWeights"]
    shares = {k: counts.get(k, 0) / max(1, n - counts.get(0, 0)) for k in (1, 2, 3)}
    for k in (1, 2, 3):
        assert abs(shares[k] - w[str(k)] / sum(w.values())) < .04, shares


@pytest.mark.parametrize("mode", [m for m, c in CFG["betModes"].items() if c.get("buy")])
def test_buy_modes_always_trigger(mode):
    rng = random.Random(11)
    start = CFG["betModes"][mode].get("multiplierStart", CFG["freeSpins"]["multiplierStart"])
    for _ in range(150):
        r = ENG.play_round(rng, record=True, mode=mode)
        assert r["fsTriggered"] and r["cost"] == CFG["betModes"][mode]["cost"]
        first = next(e for e in r["events"] if e["type"] == "reveal" and e["gameType"] == "freegame")
        assert first["multiplier"] == start


@given(st.integers(min_value=0, max_value=2**32 - 1), st.sampled_from(list(CFG["betModes"])))
@settings(max_examples=150, deadline=None)
def test_round_invariants_all_modes(seed, mode):
    r = ENG.play_round(random.Random(seed), record=True, mode=mode)
    assert 0 <= r["total"] <= ENG.max_win
    assert round(r["total"] * 100, 6) == int(round(r["total"] * 100))
    types = [e["type"] for e in r["events"]]
    assert types[0] == "reveal" and types[-1] == "finalWin"
    if "elephantStampede" in types:
        assert types.index("elephantStampede") == 1, "the stampede plays right after the base reveal"
