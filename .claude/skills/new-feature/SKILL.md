---
name: new-feature
description: Add a new game feature to Island of Gems end to end (math rule, book events, client presentation, paytable, audio, tests). Use for "add bonus buy", "add Elephant Stampede", "add Hold & Win", "add a new symbol" or any new mechanic from ARCHITECTURE.md §6.
---

# New feature pipeline

A feature is only done when it exists in all six layers. Work in this order, because every later layer depends on the earlier ones.

## 1. Spec (write it down first)
- Trigger, frequency target, payout logic, interaction with wilds and multipliers, and max-win cap behaviour.
- New book events with exact fields. Add them to the closed event union (ARCHITECTURE §4.1).
- Name and art: English only, nature or gem themed. Run `theme-guard` on the names now.
- Ask the user to confirm the spec if any number is unspecified.

## 2. Math
- Rules go in `math/game_design.json` and logic goes in `math/engine.py`. Emit the new events from `play_round`.
- A new bet mode gets its own reel set, books and LUT.
- Tune with the `math-tune` skill. Record the feature's RTP contribution and frequency.

## 3. Client engine
- Mirror the rule in the JS `MathEngine` (later `packages/engine-ts`).
- Run `parity-check`. It must show zero mismatches.

## 4. Presentation
- Handle each new event in the Game controller / `BookPlayer`. It must be skippable, and turbo-aware through the timing tables only.
- Add art (a procedural placeholder is fine in the prototype), FX and an intro/outro if it is a bonus.
- Add the audio cues using English names from the cue map.
- Use the demo QA hook to force it: `game.provider.force(r => r.events.some(e => e.type === '<newEvent>'))`.

## 5. Player information
- Paytable and rules text generated from config, with no hard-coded numbers.
- If it is a buy mode: a confirmation dialog with the cost and the mode's RTP.

## 6. Docs and tests
- Update `README.md` (features, stats), the CLAUDE.md symbol bible if symbols changed, and tick the item in `TODO.md`.
- Add fixtures to the parity and golden-timeline tests.
- Run `theme-guard` and `python build.py` one final time.
