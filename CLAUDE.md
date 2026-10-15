# CLAUDE.md: Island of Gems

Island of Gems is a 5x3, 20-line video slot built for **Stake Engine** (Stake's third-party game platform). It is aimed at a worldwide audience. The current state is a working vertical slice: Python math in `math/` and a single-file Canvas2D prototype in `frontend/index.html`. The production target is in [ARCHITECTURE.md](ARCHITECTURE.md), and the work queue is in [TODO.md](TODO.md).

## Hard rules (never break these)

### 1. Theme: culture and nature, never religion
The theme is a tropical island of gems, wildlife, landscapes and craft culture. Lion Rock stands large in the background of both scenes. Run the `theme-guard` skill before you commit any art, text, audio or naming change.

**Allowed:** gemstones (sapphire, ruby, cat's eye, moonstone *gem*, topaz, garnet); wildlife (elephant, leopard, peacock, sea turtle, blue whale); landscapes (Lion Rock fortress, rainforest, tea hills, waterfalls, coast, lighthouse, old fort ramparts); and non-religious craft and performance (gem mining, drums, dance, batik, spices, trade ships).

**Banned:** temples, stupas, shrines, churches, mosques, kovils, relics, monks, priests, deities, gods, demons, prayer and ritual imagery, religious festivals or processions, lotus-throne or halo motifs, carved temple stones (including the carved "moonstone" step), lanterns of any kind (hanging festival lanterns read as religious), cobra/naga crowns, and exorcism or devil masks. If an item has any religious reading, leave it out.

### 2. English only
Every player-facing string is plain English: UI, paytable, symbol names, feature names, big-win tiers, audio cue names, file and asset names, and code identifiers. That means no Sinhala or Tamil words, no transliterations (for example *perahera*, *jaya*, *maha*, *ratna*) and no non-Latin script. Use English descriptions for instruments ("hand drum", "reed horn"). Real place names are not needed in-game; use descriptive English ("Lion Rock").

### 3. The client never decides outcomes
The frontend only *replays* book events from the RGS (or from `LocalDemoProvider` in demo). Do not add any RNG-driven outcome logic to the client. Client randomness is for cosmetics only.

### 4. `math/game_design.json` is the source of truth
Change rules there, then run `python build.py`. The `<script id="game-config">` block in `frontend/index.html` is generated, so never edit it by hand. The JS `MathEngine` must stay 1:1 with `math/engine.py`, which the `parity-check` skill verifies.

### 5. Math changes need fresh numbers
Any change to the paytable, reels or features must re-run `python simulate.py exact` and `mc` for every bet mode, update the stats table in `README.md` and the `rtp` of each mode in `betModes` (the paytable reads it). RTP must stay inside the target band in `game_design.json` (`targetRtp` ±0.5% until tuned to ±0.1%). Follow the `math-tune` skill.

## Commands

```bash
cd math
python build.py                                  # strips + config + inject into frontend
python simulate.py exact                         # fast exact base RTP (+ FS EV)
python simulate.py mc --mode base --rounds 24000000 --workers 16   # also --mode bonus / super (480k rounds is enough)
python simulate.py books --mode base --rounds 100000              # books_<mode>.jsonl + lookUpTable_<mode>_0.csv
cd .. && python tools/parity/gen_fixtures.py && node tools/parity/check.mjs   # JS engine vs engine.py, must print PASS
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # once (macOS/Linux: .venv/bin/pip)
.venv/Scripts/python -m pytest math/tests -q     # engine rule tests (pytest + hypothesis)
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

## Skills: which one to use, and when

Use a skill whenever its trigger matches. When a task touches several areas, run every matching skill, in the order shown below.

**Project skills** (`.claude/skills/`, checked in):

| Skill | Run it when | Notes |
|---|---|---|
| `theme-guard` | Any change to art, backgrounds, text, audio cue names, identifiers or asset names, and before every commit | Run `python -I .claude/skills/theme-guard/scripts/check_theme.py`. It scans code identifiers too, so a variable named `halo` fails. Do the manual art review from the skill as well |
| `math-tune` | Any edit to `math/game_design.json` (paytable, reels, free spins, max win, bet modes) | Rule 5 applies: fresh `exact` and `mc` numbers, then update the README stats |
| `parity-check` | Any change to evaluation rules, paylines, wilds, scatters or free spins, in `engine.py` or the JS `MathEngine` | Not needed for art-only or UI-only changes |
| `new-feature` | Any new mechanic, symbol or bet mode | Covers all six layers: spec, math, client engine, presentation, player info, docs/tests |
| `release-check` | Before tagging a version or submitting to Stake Engine | Report all 10 gates with evidence |

**User-level design skills** (installed in `~/.claude/skills/`, not in the repo):

| Skill | Run it when | Notes |
|---|---|---|
| `ui-ux-pro-max` | Any change to how the game looks, moves or is touched: backgrounds, HUD, paytable, dialogs, motion | Use targeted `--domain ux` / `--domain style` queries. Its product and design-system database has **no casino or slot match**: do not adopt its generated SaaS palettes or fonts, and keep the gold-on-night look of this game. Verified rules to apply: text contrast 4.5:1, touch targets ≥ 44 px, honour `prefers-reduced-motion`, subtle parallax, 1–2 animated focal elements per view, and clear silhouettes against the sky (layered depth) |
| `frontend-design`, `ui-styling`, `web-design-guidelines` | UI kit and HUD work during the production port (TODO Phase 4) | These advise only. The theme rules and the compact `index.html` style always come first |
| `img2threejs` | Turning a concept image of a symbol or prop (Golden Elephant, Leopard, Lion Rock, gems) into a procedural 3D model. Use its PNG turntable renders as 2D sprite sources or for Spine reference (TODO Phase 2) | It needs a reference image the user supplies or approves, and it builds the model in code (no downloaded art). It can also export GLB. The game itself renders in Canvas2D now and PixiJS later, so no Three.js ships in the game build. Run `theme-guard` on the model's names and do the manual art review on its renders |

Results from the design skills are only recommendations. The hard rules above win over them every time.

## Symbol bible (v0.2)

| ID | Name | Kind | Notes |
|---|---|---|---|
| W | Golden Elephant | wild | Realistic Asian elephant with a gem crown and a velvet saddle cloth, lit by a warm gold rim light. No face cover (it would read as a festival caparison). Substitutes for everything except S |
| S | Lion Rock | scatter | Sunset medallion in a gold ring: domed rock fortress, summit trees, giant lion paws and stairway, jungle. Triggers Gem Rush Free Spins |
| H1 | Leopard | high | |
| H2 | Blue Sapphire | high | Faceted oval brilliant in a four-claw gold setting |
| H3 | Star Ruby | high | Cabochon with a six-rayed star (asterism) |
| H4 | Cat's Eye | high | Chrysoberyl cabochon with one sharp band of light |
| H5 | Moonstone | high | The **gemstone**: milky cabochon with a floating blue sheen, never the carved step |
| L1–L4 | 10, 9, 8, 7 | low | |

The feature names are **Gem Rush Free Spins**, the **Gem Multiplier**, **Elephant Stampede**, **Bonus Buy** and **Super Buy**. The big-win tiers are BIG, MEGA, EPIC and LEGENDARY.

## Conventions
- Python 3.12+ with type hints and no third-party dependencies in `engine.py`, which keeps it portable to the Stake math-sdk.
- In the frontend, match the existing compact style of `index.html` until the TypeScript port in ARCHITECTURE.md. Keep motion timings in sync with README §3.
- Amounts in books are integer multiples of 1/100 bet (`payoutMultiplier`). Amounts to the RGS use 6 decimal places (`× 1e6`).
- Write the commit message in Conventional Commits style.
- Never commit secrets, session IDs or RGS URLs.
