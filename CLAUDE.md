# CLAUDE.md: Island of Gems

Island of Gems is a 5x3, 20-line video slot built for **Stake Engine** (Stake's third-party game platform). It is aimed at a worldwide audience. The current state is a working vertical slice: Python math in `math/` and a single-file Canvas2D prototype in `frontend/index.html`. The production target is in [ARCHITECTURE.md](ARCHITECTURE.md), and the work queue is in [TODO.md](TODO.md).

## Hard rules (never break these)

### 1. Theme: culture and nature, never religion
The theme is a tropical island of gems, wildlife, landscapes and craft culture. Run the `theme-guard` skill before you commit any art, text, audio or naming change.

**Allowed:** gemstones (sapphire, ruby, cat's eye, moonstone *gem*, topaz, garnet); wildlife (elephant, leopard, peacock, sea turtle, blue whale); landscapes (Lion Rock fortress, rainforest, tea hills, waterfalls, coast, lighthouse, old fort ramparts); and non-religious craft and performance (gem mining, drums, dance, lanterns, batik, spices, trade ships).

**Banned:** temples, stupas, shrines, churches, mosques, kovils, relics, monks, priests, deities, gods, demons, prayer and ritual imagery, religious festivals or processions, lotus-throne or halo motifs, carved temple stones (including the carved "moonstone" step), cobra/naga crowns, and exorcism or devil masks. If an item has any religious reading, leave it out.

### 2. English only
Every player-facing string is plain English: UI, paytable, symbol names, feature names, big-win tiers, audio cue names, file and asset names, and code identifiers. That means no Sinhala or Tamil words, no transliterations (for example *perahera*, *jaya*, *maha*, *ratna*) and no non-Latin script. Use English descriptions for instruments ("hand drum", "reed horn"). Real place names are not needed in-game; use descriptive English ("Lion Rock").

### 3. The client never decides outcomes
The frontend only *replays* book events from the RGS (or from `LocalDemoProvider` in demo). Do not add any RNG-driven outcome logic to the client. Client randomness is for cosmetics only.

### 4. `math/game_design.json` is the source of truth
Change rules there, then run `python build.py`. The `<script id="game-config">` block in `frontend/index.html` is generated, so never edit it by hand. The JS `MathEngine` must stay 1:1 with `math/engine.py`, which the `parity-check` skill verifies.

### 5. Math changes need fresh numbers
Any change to the paytable, reels or features must re-run `python simulate.py exact` and `mc`, and update the stats table in `README.md`. RTP must stay inside the target band in `game_design.json` (`targetRtp` ±0.5% until tuned to ±0.1%). Follow the `math-tune` skill.

## Commands

```bash
cd math
python build.py                                  # strips + config + inject into frontend
python simulate.py exact                         # fast exact base RTP (+ FS EV)
python simulate.py mc --rounds 2400000 --workers 12
python simulate.py books --rounds 100000         # books_base.jsonl + lookUpTable_base_0.csv
cd .. && python -m http.server 8765 --directory frontend   # http://localhost:8765
```

QA in the browser console: `game.provider.force(r => r.events.some(e => e.type === 'freeSpinTrigger'))`

## Layout

| Path | Role |
|---|---|
| `math/game_design.json` | Rules: symbols, paytable, lines, reel weights, free spins, max win |
| `math/engine.py` | Reference evaluator and round player that emits book events |
| `math/build.py` | Seeded reel strips, writes `math/out/game_config.json`, injects the config into the frontend |
| `math/simulate.py` | Exact RTP, Monte Carlo, books and lookup tables |
| `frontend/index.html` | Prototype layers: MathEngine, OutcomeProvider, Game controller, View (canvas) and SoundEngine |
| `.claude/skills/` | Project workflows: theme-guard, math-tune, parity-check, new-feature, release-check |

## Symbol bible (v0.2)

| ID | Name | Kind | Notes |
|---|---|---|---|
| W | Golden Elephant | wild | Gem crown and jeweled saddle cloth. Substitutes for everything except S |
| S | Lion Rock | scatter | Rock fortress with giant lion paws. Triggers Gem Rush Free Spins |
| H1 | Leopard | high | |
| H2 | Blue Sapphire | high | |
| H3 | Star Ruby | high | |
| H4 | Cat's Eye | high | Chrysoberyl gem |
| H5 | Moonstone | high | The **gemstone** (blue sheen cabochon), never the carved step |
| L1–L4 | 10, 9, 8, 7 | low | |

The feature names are **Gem Rush Free Spins** and the **Gem Multiplier**. The big-win tiers are BIG, MEGA, EPIC and LEGENDARY.

## Conventions
- Python 3.12+ with type hints and no third-party dependencies in `engine.py`, which keeps it portable to the Stake math-sdk.
- In the frontend, match the existing compact style of `index.html` until the TypeScript port in ARCHITECTURE.md. Keep motion timings in sync with README §3.
- Amounts in books are integer multiples of 1/100 bet (`payoutMultiplier`). Amounts to the RGS use 6 decimal places (`× 1e6`).
- Write the commit message in Conventional Commits style.
- Never commit secrets, session IDs or RGS URLs.
