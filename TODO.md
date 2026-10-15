# Island of Gems: TODO

Status keys: `[x]` done · `[ ]` open · **P0** blocks release · **P1** needed for launch quality · **P2** growth and polish.
Details for each item are in [ARCHITECTURE.md](ARCHITECTURE.md). The rules are in [CLAUDE.md](CLAUDE.md).

---

## Phase 0: Theme and compliance reset (P0)
- [x] Remove the religious scatter (temple) and replace it with **Lion Rock**
- [x] Remove the stupa from the background and replace it with a coastal lighthouse on fort ramparts
- [x] Put **Lion Rock** large in the background (left of the reels, lion-paw platform, summit trees, mist)
- [x] Remove the hanging festival lanterns (religious reading); the scanner now flags "lantern"
- [x] Replace the Raksha mask (ritual/demon reading) with **Leopard**
- [x] Replace the carved temple-step moonstone with the **Moonstone gem**
- [x] Remove every Sinhala string and font, so the big-win tiers become BIG / MEGA / EPIC / LEGENDARY
- [x] Rename the "Perahera" free spins to **Gem Rush Free Spins** / **Gem Multiplier**
- [x] Rename the game from *Lanka Tusker Treasures* to **Island of Gems** (`gameId: island_of_gems`, v0.2.0)
- [x] Use English names for the audio cues (`chime`, `impact`, hand drum, reed horn)
- [ ] Write `tools/theme-guard` and add it to CI (the skill script exists in `.claude/skills/theme-guard/`)
- [ ] Get an independent cultural sensitivity review of the final art from 2+ reviewers outside the team
- [ ] Get legal advice on supplying gambling software from your jurisdiction, plus a Stake Engine onboarding check
- [ ] Register the trademark and domain for "Island of Gems", and check for conflicts with existing slot titles

## Phase 1: Math (P0)
- [ ] Port `engine.py` into the Stake **math-sdk** structure (`game_config`, `gamestate`, events)
- [ ] Add a `pytest` and `hypothesis` suite for board evaluation (wild substitution, wild-only lines, best-per-line)
- [ ] Use a numba-JIT evaluator, with a Rust/pyo3 core if 1B-round runs are needed
- [ ] Decide the feature set for v1.0 from ARCHITECTURE §6. The recommended set is Gem Rush, Bonus Buy, Super Buy and Elephant Stampede
- [ ] Add math for the **Bonus Buy** mode (100x) and **Super Buy** mode (300x, x3 start multiplier)
- [ ] Add math for **Elephant Stampede** (random expanding wild reels)
- [ ] (P1) Add math for **Lion Rock Hold & Win** with Mini, Minor, Major and Grand
- [ ] Raise the max win to 10,000x and shape the tail with the optimizer
- [ ] Add RTP variants (for example 96.0 / 94.0 / 92.0) using reel and LUT weights only **[verify Stake requirements]**
- [ ] Run 100M+ rounds per mode and per variant; RTP must land within ±0.1% of target
- [ ] Produce the math report notebook as HTML (RTP, hit rate, volatility index, win distribution, max-win odds, feature frequency)
- [ ] Do a book schema export plus zod validation in CI
- [ ] Move the large `books_*.jsonl` out of git (LFS or release assets)

## Phase 2: Art (P0 for launch)
- [ ] Moodboard and style frame: a jewel-toned tropical night, rainforest canopy, glowing gems and gold filigree
- [ ] Key art: the Golden Elephant in front of Lion Rock at sunset (for the lobby tile, social posts and the loading screen)
- [ ] Symbol set at 2x: Golden Elephant, Lion Rock, Leopard, Blue Sapphire, Star Ruby, Cat's Eye, Moonstone. Replace the numeric lows with gem-cut **A K Q J 10** or keep 10–7 (decide)
- [ ] (Optional) Use the `img2threejs` skill to turn approved concept art into procedural 3D models, then render them to PNG as symbol sprite sources and Spine reference
- [ ] Spine animations (idle, land, win) for every symbol, plus a full-screen Golden Elephant trumpet for big wins
- [ ] Backgrounds in 4 parallax layers × 2 modes (base dusk and the Gem Rush night with torches and fireflies, Lion Rock in the back), in landscape and portrait
- [ ] UI kit: spin button, bet pill, balance, autoplay panel, settings, paytable, and the buy-feature dialog
- [ ] Big-win cards for 4 tiers, the Gem Rush intro and outro, and the max-win screen
- [ ] Atlas pipeline (`tools/assets`) producing WebP at 2x and 1x, with KTX2 for backgrounds

## Phase 3: Audio (P1, run in parallel)
- [ ] Sound palette: hand drums, frame drums, a reed horn, marimba-style gem chimes, ocean and rainforest ambience, and an elephant trumpet (no religious bells or chants)
- [ ] Music stems: base calm, base tension, Gem Rush loop, and the big-win stingers ×4
- [ ] SFX for the full cue map in ARCHITECTURE §5.4
- [ ] Master to −16 LUFS and build the OGG and AAC sprites with `audiosprite`

## Phase 4: Frontend production port (P0)
- [ ] Monorepo scaffold: pnpm + Turborepo, `apps/web` (Vite + Svelte 5 + TS), `packages/book-schema`, `packages/engine-ts`, `packages/ui-kit`
- [ ] PixiJS v8 renderer: background, reel frame, masked ReelSet, WinLayer, FXLayer
- [ ] Reel physics port, keeping every timing from README §3 (wind-up, stagger, easeOutBack landing, anticipation)
- [ ] XState game FSM plus a pure `BookPlayer` that produces a timeline of commands
- [ ] `RGSClient`: authenticate, play and end-round, with a balance store **[verify the live spec]**
- [ ] `DemoProvider` (embedded books) and `ReplayProvider` (play a book by ID)
- [ ] Spine integration (`spine-pixi-v8`) with a static atlas fallback on the low tier
- [ ] FX: particle pool, bloom (big wins only), godrays on the Lion Rock trigger, shockwave on multiplier steps
- [ ] Howler AudioDirector with buses, ducking and state-driven stems
- [ ] Layouts for landscape 16:9, portrait 9:19.5 and tablet 4:3, plus safe areas. The prototype covers landscape and portrait; tablet is letterboxed
- [ ] Quality tiers detected automatically
- [ ] Buy Feature UI with a confirmation dialog that shows the cost and mode RTP
- [ ] Paytable and rules generated from config, showing RTP per mode and the max win
- [ ] Settings: sound and music volume, turbo, quick spin, reduced motion, and space-to-spin
- [ ] Autoplay with limits (count, loss limit, single-win limit, stop on feature). Done in the prototype; port it
- [ ] Jurisdiction profiles (minimum spin time, turbo, slam stop and autoplay switches)
- [x] `prefers-reduced-motion` mode in the prototype (OS setting plus an in-game switch; README §3.1). Port it.
- [ ] Colour-blind-safe payline palette
- [x] Touch targets in the prototype: ≥ 44 px in portrait, ≥ 40 px on phones in landscape (bet −/+ are 32 px there; recheck on real devices)
- [x] Prototype UI pass: spin gem, responsive control bar, menu (paytable, history, settings), autoplay with limits, bet picker, session clock (README §3.1). The Svelte UI kit should match it
- [ ] Self-hosted, subsetted fonts with no runtime Google Fonts
- [ ] Remove the legacy `frontend/index.html` once the port reaches parity

## Phase 5: QA (P0)
- [ ] Parity runner covering 1M random boards per mode across TS and Python, with zero mismatches
- [ ] Vitest golden timelines for each book fixture type
- [ ] Playwright visual regression across 3 layouts × key states
- [ ] Nightly soak test of 10,000 spins (memory, long tasks, audio leaks)
- [ ] Device matrix pass (low-end Android, iPhone SE, mid-range Android, desktop browsers)
- [ ] Replay every event type and every big-win tier from real books

## Phase 6: CI/CD (P1)
- [ ] GitHub Actions jobs: ruff, eslint, svelte-check, vitest, pytest, parity, theme-guard, build, size-limit and Playwright
- [ ] Lighthouse CI budgets (ARCHITECTURE §8)
- [ ] Release workflow: tag, then build the math and frontend artifacts and attach the math report
- [ ] Renovate or Dependabot, plus `pnpm audit`

## Phase 7: Launch and growth (P2)
- [ ] Stake Engine submission: math, frontend and review **[verify the process]**
- [ ] Lobby tile, a 15 s trailer showing a LEGENDARY win and Gem Rush, and a short vertical cut for social media
- [ ] Streamer kit: a feature explainer, max-win odds and the bonus-buy RTP sheet
- [ ] A high-volatility edition after the first-month data
- [ ] Follow-up title on the same engine (for example "Island of Gems: Monsoon Hold & Win")
