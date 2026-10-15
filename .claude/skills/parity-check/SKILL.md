---
name: parity-check
description: Verify the JavaScript/TypeScript MathEngine matches math/engine.py exactly on random boards. Use after any change to evaluation rules, paylines, wilds, scatters or free spins, or when asked "are the engines in sync" or "run the parity test".
---

# Parity check

The client's evaluator only exists for the demo and for presentation (line highlights). It must still agree with Python on every board, or the paytable and win lines will lie to the player.

## Run it

1. Rebuild the config: `cd math && python build.py`.
2. Generate fixtures in Python with a fixed seed: N random boards from both the `base` and `free` strips, plus the `engine.py` results (line wins, scatter count and pay, FS award) as JSON lines:
   ```bash
   python -c "import engine, json, random; ..."   # write tools/parity/fixtures.jsonl
   ```
   If `tools/parity/` does not exist yet, create `tools/parity/gen_fixtures.py` and `tools/parity/check.mjs`. Start with 100k boards per mode, then use 1M before release.
3. Evaluate the same boards in JS. Load `MathEngine` from the prototype (extract the `<script>` block) or import from `packages/engine-ts` once the port exists. Compare field by field.
   ```bash
   node tools/parity/check.mjs tools/parity/fixtures.jsonl
   ```
4. **The pass condition is zero mismatches.** On a mismatch, print the board, both results and the line index, fix the side that disagrees with `engine.py`, and re-run.

## Notes
- Python is the reference. Never "fix" Python to match JS unless the user confirms the rule change.
- Include edge cases in the fixtures: all wilds, a wild-only line versus a symbol line (best pays), 5 scatters, and scatters plus wilds on the same reel.
- Wire this into CI once it exists (TODO Phase 6).
