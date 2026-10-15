# Island of Gems: architecture

This document is the target architecture for taking the vertical slice to a world-class, release-ready Stake Engine slot. It covers the system, the tech stack, the module boundaries, the data contracts, the rendering, audio and asset pipelines, testing, CI/CD, performance budgets and compliance.

> Everything marked **[verify]** depends on Stake Engine specifics (formats, limits, SDK APIs). Check those against the current Stake Engine docs and math-sdk / web-sdk repositories before building on them.

---

## 1. System overview

```
                       ┌──────────────────────── OFFLINE (studio) ───────────────────────┐
 game_design.json ──►  │ build ──► reel strips ──► simulate / optimize ──► books + LUTs   │
 (rules, paytable)     │            (seeded)        (Python + numba/Rust)   (per bet mode) │
                       └───────────────────────────────────────┬──────────────────────────┘
                                                               │ upload [verify]
                                                               ▼
 Player ──► Static web bundle (CDN) ──► Stake RGS ──► /wallet/authenticate · /wallet/play · /wallet/end-round
               ▲   (Svelte + PixiJS)       │  picks a book by weight, debits and credits the wallet
               │                           │
               └──── book events ◄─────────┘   reveal · winInfo · freeSpinTrigger · multiplier · finalWin …
```

**Core principle:** outcomes are pre-computed books, and the RGS selects one. The client is a deterministic **event player**, so the same book always renders the same presentation. That makes replays, QA reproduction and streamer clips exact.

---

## 2. Tech stack

### Math and simulation
| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Stake math-sdk is Python **[verify version]** |
| Framework | Stake Engine **math-sdk** (`game_config`, `gamestate`, events, optimizer) | Native book and LUT output plus the RTP optimizer |
| Fast simulation | `numba` JIT on the evaluator, and optionally a **Rust** core via `pyo3`/`maturin` for runs of 1B+ rounds | Certification wants 100M+ rounds per mode |
| Analysis | `numpy`, `pandas`, `pyarrow` (Parquet), `plotly` | Win-distribution and volatility reports |
| Reports | Jupyter notebook to HTML (`nbconvert`), committed per release | Auditable math sign-off |
| Tests | `pytest`, `hypothesis` (property tests on board evaluation) | Edge cases in wild substitution and line evaluation |

### Frontend (production)
| Concern | Choice | Notes |
|---|---|---|
| Language | **TypeScript 5** (strict) | |
| UI and state | **Svelte 5** (runes) | Stake web-sdk is Svelte-based **[verify]** |
| Renderer | **PixiJS v8** (WebGL2, with a WebGPU backend when available) | Batching, filters, ParticleContainer |
| Skeletal animation | **Spine 4.2** with `@esotericsoftware/spine-pixi-v8` | Symbol idle, land and win, plus character intros |
| Tweens and timelines | **GSAP 3** | Win sequences and UI motion |
| Shaders and filters | `pixi-filters`: AdvancedBloom, GodRay, Shockwave, Displacement, ColorMatrix | Gem glints, god rays, water shimmer, big-win punch |
| Particles | Custom emitter on Pixi v8 `ParticleContainer` | Coin fountains, gem shards, sparks, fireflies |
| Audio | **Howler.js** audio sprites (Web Audio, HTML5 fallback) | Stems, ducking, separate music and SFX buses |
| State machine | **XState 5** (or a hand-written typed FSM) | Spin and feature flow, fully testable |
| Build | **Vite 6**, static output | Code-split the free-spins and big-win scenes |
| Monorepo | **pnpm workspaces** plus **Turborepo** | `apps/`, `packages/`, shared configs |
| Lint and format | ESLint (typescript-eslint), Prettier, `svelte-check`, Ruff (Python) | |
| Unit tests | **Vitest** | Engine parity, FSM, formatters |
| E2E and visual | **Playwright** (screenshot diffs, device emulation) | Desktop, portrait mobile, landscape mobile |
| Component dev | **Storybook 8** (Svelte) | UI kit, HUD and paytable in isolation |
| i18n | `svelte-i18n` with an English-only string table at launch | All strings are externalized, so a locale can be added later without code changes |

### Assets and pipeline
| Concern | Choice |
|---|---|
| Atlases | TexturePacker (or `free-tex-packer-cli`), WebP plus a PNG fallback, at 2x and 1x tiers |
| GPU textures | KTX2 / Basis Universal for large backgrounds (optional tier) |
| Image processing | `sharp` scripts (resize, trim, WebP and AVIF) |
| Audio | DAW masters, then `ffmpeg` and `audiosprite` to OGG plus AAC sprites, loudness-normalized to −16 LUFS |
| Fonts | Subset Cinzel / Cinzel Decorative with `glyphhanger` and self-host them (no Google Fonts at runtime) |

### CI/CD and quality
| Concern | Choice |
|---|---|
| CI | GitHub Actions: lint, test, parity, build, bundle-size budget, Playwright, math smoke run |
| Budgets | `size-limit` for JS and Lighthouse CI for load and performance |
| Releases | Conventional Commits, `changesets` for versioning, and a tagged release that bundles math and frontend artifacts |
| Large math outputs | Git LFS or release assets for `books_*.jsonl` (they are not committed to `main` once they exceed about 20 MB) |
| Error tracking | Only if Stake allows outbound telemetry **[verify]**. Otherwise log to a ring buffer and surface it in a QA overlay |

---

## 3. Repository layout (target)

```
island-of-gems/
├── math/                         # Python, Stake math-sdk structure
│   ├── game_design.json          # source of truth (rules)
│   ├── game/                     # gamestate.py, events.py, config.py (math-sdk shape)
│   ├── engine/                   # evaluator (numba) + optional rust/ core
│   ├── modes/                    # base, bonus_buy, super_buy, ante
│   ├── optimize/                 # optimizer configs per mode and RTP variant
│   ├── reports/                  # notebooks + rendered HTML per release
│   └── tests/
├── apps/
│   └── web/                      # Svelte + Pixi game client (Vite)
│       ├── src/
│       │   ├── main.ts
│       │   ├── app/              # Svelte shell, HUD, menus, paytable, settings
│       │   ├── game/             # FSM, BookPlayer, feature controllers
│       │   ├── render/           # Pixi scenes, ReelSet, Symbol, WinLines, FX
│       │   ├── audio/            # Howler wrapper, cue map, music stems
│       │   ├── net/              # RGSClient, DemoProvider, ReplayProvider
│       │   └── i18n/en.json
│       └── public/assets/        # atlases, spine, audio sprites, fonts
├── packages/
│   ├── engine-ts/                # TS port of the evaluator (for demo and parity only)
│   ├── book-schema/              # zod schemas + TS types for book events
│   └── ui-kit/                   # buttons, pills, modals, Storybook stories
├── tools/
│   ├── parity/                   # cross-language parity runner
│   ├── assets/                   # sharp / texturepacker / audiosprite scripts
│   └── theme-guard/              # banned-term and script scanner
├── frontend/index.html           # legacy prototype (kept until the port reaches parity)
├── .claude/skills/               # Claude Code workflows
├── CLAUDE.md · ARCHITECTURE.md · TODO.md · README.md
└── .github/workflows/
```

---

## 4. Data contracts

### 4.1 Book (one per pre-computed round)
```jsonc
{
  "id": 1,
  "payoutMultiplier": 420,          // integer, in 1/100 of total bet
  "events": [
    { "type": "reveal", "gameType": "basegame", "stops": [41,19,50,6,9], "board": [["L1","L3","H1"], ...] },
    { "type": "winInfo", "wins": [{ "line": 0, "symbol": "L3", "count": 4, "pay": 25 }], "amount": 4.2, "multiplier": 1 },
    { "type": "freeSpinTrigger", "positions": [[0,1],[2,0],[4,2]], "totalFs": 10 },
    { "type": "multiplier", "value": 3 },
    { "type": "finalWin", "amount": 4.2 }
  ]
}
```
- Event types are a **closed union** in `packages/book-schema` (zod), and every book is validated in CI.
- **[verify]** Align event names and fields with the math-sdk conventions. Adapt them in one mapping layer (`BookAdapter`) and nowhere else.

### 4.2 Lookup table
`lookUpTable_<mode>_<n>.csv` has the rows `bookId,weight,payoutMultiplier`. The optimizer edits weights only and never edits books.

### 4.3 Bet modes (planned)
| Mode | Cost | Content |
|---|---|---|
| `base` | 1x | Normal play |
| `ante` | 1.25x | Free-spin trigger rate doubled |
| `bonus` | 100x | Buy Gem Rush Free Spins (guaranteed 3+ scatters) |
| `super` | 300x | Buy Super Gem Rush (multiplier starts at x3 and never resets) |

Each mode has its own books, LUT and RTP target. Every mode must sit in the same RTP band **[verify Stake rules on buy modes and their RTP]**.

---

## 5. Client architecture

```
 RGSClient / DemoProvider / ReplayProvider     (net)
            │  Round { events[] }
            ▼
 BookAdapter ──► BookPlayer ──► GameFSM (XState)            (game)
                    │  dispatches presentation commands
                    ▼
     ┌──────────────┼───────────────────────────────┐
     ▼              ▼                ▼               ▼
  ReelSet      WinPresenter     FeatureScenes      HUD (Svelte stores)       (render / app)
 (spin/stop)   (lines, counts)  (FS intro/outro,   (balance, bet, win,
                                 big win tiers)     autoplay, settings)
     └──────────── AudioDirector (cue map, stems, ducking) ───────────┘
```

### 5.1 Game FSM (top level)
`boot → loading → idle → spinning → stopping → evaluating → (presentingWins | freeSpinsIntro | bigWin) → idle`.
Free spins form a nested machine: `fsIntro → fsSpin ⇄ fsPresent → fsOutro`.
Autoplay is an outer controller that respects loss and win limits and stops on a feature.

### 5.2 Rules for the BookPlayer
- It is pure. Given `(book, bet, settings)`, it yields a timeline of commands. That makes it unit-testable without Pixi.
- Every visual is skippable (slam stop or skip count-up) without changing the outcome or the final balance.
- Turbo and quick-spin only change timing tables. They never change sequences.

### 5.3 Rendering
- **Scene graph:** `Background (parallax 4 layers) → ReelFrame → ReelSet (masked) → WinLayer → FXLayer → HUD`.
- **Reels:** each reel holds a symbol pool (`rows + 2` buffers), swaps to a motion-blur texture above the speed threshold, and lands with easeOutBack (`c=1`). The landing start velocity matches the spin speed (README §3).
- **Symbols:** Spine skeletons with `idle`, `land` and `win` animations, plus a static atlas fallback for low tier.
- **Wins:** line paths are drawn as a `Graphics` path with a GlowFilter. Non-winning symbols dim through a ColorMatrix.
- **FX:** a pooled particle system (cap of about 1,500 sprites), bloom only during big wins, and a godray shader behind Lion Rock on trigger.
- **Layouts:** landscape 16:9, portrait 9:19.5 and tablet 4:3. Positions come from a layout table per breakpoint, never from hard-coded pixels.
- **Quality tiers:** detected from `devicePixelRatio`, GPU renderer string and the first two seconds of frame time. Low tier turns off bloom and Spine meshes and halves particle caps.

### 5.4 Audio
- Buses: `master → music | sfx | ui`. Music ducks −8 dB under big wins.
- Music layers by game state: base calm, base tension (on anticipation), Gem Rush loop, and a separate stinger per big-win tier.
- **Cue map** (English names only): `spin_start`, `reel_loop`, `reel_stop_1..5`, `scatter_land_1..5`, `anticipation_riser`, `win_small|medium|large`, `count_tick`, `coin`, `multiplier_up`, `gem_rush_intro|outro`, `bigwin_big|mega|epic|legendary`, `ui_click`.
- Instruments: hand drums, frame drums, a reed horn, marimba-like gem chimes, ocean and rainforest ambiences, and an elephant trumpet. There are no bells or chants with religious associations.

---

## 6. Game design roadmap (features that drive trend)

What players and streamers reward: big readable moments, a reachable top win, a feature you can buy, and a signature mechanic people can name. In priority order:

| # | Feature | Mechanic | Math impact |
|---|---|---|---|
| 1 | **Gem Rush Free Spins** (exists) | A progressive multiplier that grows +1 on each winning spin | Baseline |
| 2 | **Bonus Buy / Super Buy** | Stake bet modes `bonus` and `super` (see §4.3) | A new mode, books and LUT each |
| 3 | **Elephant Stampede** | A random base-game event (about 1 in 70) that turns 1–3 full reels (2–4) into expanding Golden Elephant wilds | Base RTP up, so retune the low symbols |
| 4 | **Lion Rock Hold & Win** | 6+ Gem Coin symbols trigger 3 respins, and each new coin resets the count. Coins carry 1x–50x values, with Mini, Minor, Major and Grand (25x, 50x, 250x, 2,000x) | A second bonus, a new symbol and a separate reel set |
| 5 | **Max win 10,000x** | Raise the cap after features 2–4 so the top tier is reachable around 1 in 2–5M | Needs the optimizer to shape the distribution |
| 6 | **Ante bet** | `ante` mode doubles the scatter weight | Its own books |
| 7 | **Volatility variants** | A high-volatility edition for streamers, a medium one for casuals | Separate release, same art |

Presentation hooks that make clips spread:
- A 5-tier big-win sequence with a full-screen Golden Elephant trumpet and gem-shard explosion at LEGENDARY.
- Multiplier visible on screen at all times during Gem Rush, with a camera punch on each step.
- A max-win screen that lasts at least 6 s and is designed for screenshots.
- Replay links: the client can play any book ID in `ReplayProvider` mode **[verify Stake replay support]**.

---

## 7. Testing strategy

| Layer | Test | Gate |
|---|---|---|
| Math | `pytest` and `hypothesis` on evaluation; exact base RTP vs MC within 3σ | CI |
| Math | 100M+ rounds per mode, RTP within ±0.1% of target, max-win frequency reported | Release |
| Parity | JS/TS evaluator vs Python on 1M random boards per mode (`lineWin`, scatter and FS award) with zero mismatches | CI |
| Books | Every event validated with the zod schema; `payoutMultiplier` equals the sum of event amounts | CI |
| Client | Vitest on the FSM and BookPlayer timelines (golden snapshots per book fixture) | CI |
| Visual | Playwright screenshots of idle, each big-win tier, FS intro and outro, and paytable, across 3 layouts | CI |
| Soak | 10,000 auto-spins in a headless browser: no heap growth over 50 MB and no long tasks over 200 ms | Nightly |
| Devices | Low-end Android (4 GB RAM), iPhone SE, mid-range Android, desktop Chrome, Safari and Firefox | Release |
| Theme | `theme-guard` scan: zero banned terms and no non-Latin script in shipped files | CI |

---

## 8. Performance budgets

| Metric | Budget |
|---|---|
| Initial download (to playable) | ≤ 5 MB on the low tier, ≤ 9 MB on high (FS and big-win assets lazy) |
| JS (gzip) | ≤ 350 KB, excluding Spine data |
| Time to interactive | ≤ 3 s on 4G mid-range Android |
| Frame rate | 60 fps desktop and high mobile, at least 50 fps p95 on the low tier |
| GPU memory | ≤ 256 MB textures on high, ≤ 128 MB on low |
| Audio | Music streamed, SFX sprite ≤ 1.2 MB |

---

## 9. Compliance and responsible gambling
- Show RTP, max win and rules in the paytable, generated from config (no hard-coded numbers).
- Autoplay needs explicit limits (spin count, loss limit, single-win limit) and stops on a feature.
- A jurisdiction profile per launch market **[verify markets via Stake]**. Profiles can enforce a minimum spin time (for example 2.5 s), disable turbo and slam stop, block autoplay, show net position, and add a session clock and reality check.
- Anticipation and near-miss effects only show on real scatter states. Presentation must not imply a near-win that the outcome did not contain.
- `prefers-reduced-motion` turns off camera shake, flashes and parallax, and shortens the count-up.
- Colour-blind-safe payline palette, with labels on every line and not colour alone.
- Every player-facing string is in English and passes `theme-guard`. See CLAUDE.md for the theme rules.

---

## 10. Security
- The client holds no secrets. Session ID and RGS URL come from query params at launch and are never logged or persisted.
- All money values use integer micro-units on the wire (`× 1e6`), with no float arithmetic for balances.
- Assume replays and books are public, so they must not contain personal data.
- Pin dependencies through the lockfile, run Dependabot or Renovate, and run `pnpm audit` in CI.
