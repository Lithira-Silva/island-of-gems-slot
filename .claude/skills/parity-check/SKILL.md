---
name: parity-check
description: Verify the JavaScript/TypeScript MathEngine matches math/engine.py exactly on random boards. Use after any change to evaluation rules, paylines, wilds, scatters or free spins, or when asked "are the engines in sync" or "run the parity test".
---

# Parity check

The client's evaluator only exists for the demo and for presentation (line highlights). It must still agree with Python on every board, or the paytable and win lines will lie to the player.

## Run it

1. Rebuild the config: `cd math && python build.py`.
2. Generate fixtures from `engine.py` with a fixed seed. It writes boards from the `base` and `free` strips, uniform-random boards (these reach ties and 5-scatter boards the strips rarely produce), hand-picked edge cases, and full recorded rounds (half of them forced free-spin rounds):
   ```bash
   python tools/parity/gen_fixtures.py                       # 100k boards per source + 20k rounds (~1 min)
   python tools/parity/gen_fixtures.py --boards 1000000 --rounds 200000   # before release
   ```
3. Check them in JS. `check.mjs` loads the injected config and the `MathEngine` class exactly as they ship in `frontend/index.html` (later: import from `packages/engine-ts`). Boards are compared field by field; rounds are replayed from Python's recorded reel stops and the whole event stream must match.
   ```bash
   node tools/parity/check.mjs                               # prints PASS or the first mismatches, exit 1 on fail
   ```
   The fixture file is gitignored; regenerate it, never commit it.
4. **The pass condition is zero mismatches.** On a mismatch, print the board, both results and the line index, fix the side that disagrees with `engine.py`, and re-run.

## Notes
- Python is the reference. Never "fix" Python to match JS unless the user confirms the rule change.
- Include edge cases in the fixtures: all wilds, a wild-only line versus a symbol line (best pays), 5 scatters, and scatters plus wilds on the same reel.
- Wire this into CI once it exists (TODO Phase 6).
