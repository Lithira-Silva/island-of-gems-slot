---
name: math-tune
description: Change or tune Island of Gems math (paytable, reel weights, free spins, multipliers, max win, bet modes) and re-verify RTP. Use for "tune RTP", "change the paytable", "make it more volatile", "add an RTP variant" or any edit to math/game_design.json.
---

# Math tune

`math/game_design.json` is the only place where rules live. Everything else is generated from it.

## Loop

1. **State the goal in numbers** before you edit. For example: "RTP 96.00% ±0.1, FS 1 in 180–220, hit rate ≥ 30%, std dev 6–8".
2. **Edit `math/game_design.json`.** Prefer changing reel weights over pay values, and change one lever at a time:
   - RTP up or down: low-symbol weights first, then wild weights.
   - Free-spin frequency: `S` weights. Keep the scatter spacing rule (at most one per reel window), or `build.py` raises an error.
   - Volatility: move value from the low symbols into the wild and the FS multiplier.
3. **Rebuild and measure:**
   ```bash
   cd math
   python build.py
   python simulate.py exact                                  # seconds; use while iterating
   ```
4. **Repeat until the exact result is on target**, then confirm with the full run:
   ```bash
   python simulate.py mc --rounds 2400000 --workers 12        # writes out/stats.json
   ```
   Exact and MC must agree within 3 standard errors. If they do not, there is a bug: stop and investigate.
5. **If rules changed** (not just weights), update `MathEngine` in `frontend/index.html` to match `engine.py`, then run the `parity-check` skill.
6. **Update the stats table** in `README.md` §1 from `out/stats.json`. Bump `version` in `game_design.json`.
7. **Regenerate the books** only when the math is final: `python simulate.py books --rounds 100000`.

## Guardrails
- Never edit `<script id="game-config">` in the frontend by hand.
- Never edit `math/out/*` by hand.
- The max win cap must be enforced in `engine.py` and reported in `stats.json` (`maxWinHits`).
- Free-spin multiplier and retrigger changes affect FS EV a lot. Re-run `exact` after each one.
- Before release, run 100M+ rounds per mode and per RTP variant (see TODO Phase 1).
