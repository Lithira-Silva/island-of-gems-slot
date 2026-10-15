# Island of Gems: production blueprint

A 5x3, 20-line video slot with a tropical island theme (gems, wildlife and landscapes; no religious imagery, English only), built the way a studio would build it for **Stake Engine**, the platform Stake uses to publish third-party games on stake.com.

Start with [CLAUDE.md](CLAUDE.md) (rules), [ARCHITECTURE.md](ARCHITECTURE.md) (production target) and [TODO.md](TODO.md) (work queue). Project workflows live in `.claude/skills/`.

This repository holds a **working vertical slice**:

| Path | What it is |
|---|---|
| `math/game_design.json` | Source of truth for the game rules: symbols, paytable, paylines, reel weights, free spins, max win |
| `math/engine.py` | Reference math engine. It evaluates boards, plays rounds, and emits book events |
| `math/build.py` | Generates seeded reel strips, writes `math/out/game_config.json`, and injects that config into the frontend |
| `math/simulate.py` | Exact base-game RTP, Monte Carlo for the full game, and book/lookup-table output |
| `frontend/index.html` | Playable prototype: canvas renderer, reel physics, win presentation, free spins, big wins and procedural WebAudio. It replays the same event format as the books |

## Run it

```bash
cd math
python build.py
python simulate.py exact
python simulate.py mc --rounds 2400000 --workers 12
python simulate.py books --rounds 100000
cd ..
python -m http.server 8765 --directory frontend
```

Open http://localhost:8765. Press **Space** to spin. Pressing Space or clicking during a spin does a slam stop, and pressing it during a win skips the count-up.

QA helper (browser console, demo provider only):
`game.provider.force(r => r.events.some(e => e.type === 'freeSpinTrigger'))` queues a matching round for the next spin.
Add a mode to force a buy round: `game.provider.force(r => r.payoutMultiplier > 20000, 'bonus')`. Force a stampede with `e.type === 'elephantStampede'`.

---

## 1. Current math model (v0.3.0: Elephant Stampede, Bonus Buy, Super Buy, 10,000x cap)

| Metric | Base game (1x) | Bonus Buy (100x) | Super Buy (152x) |
|---|---|---|---|
| RTP, exact (`simulate.py exact`, 400k FS sessions per trigger size) | **96.01%** | **95.92%** | **96.25%** |
| RTP, Monte Carlo (`mc`) | 96.11% ± 0.17% (24M rounds) | 95.66% ± 0.13% (480k) | 96.01% ± 0.12% (480k) |
| Split | lines 53.5% · stampede 10.5% · scatter pays 1.2% · free spins 30.9% | trigger board 3.8% · free spins 91.9% | trigger board 2.5% · free spins 93.5% |
| Hit rate | 35.3% (1 in 2.83) | 100% | 100% |
| Gem Rush frequency | 1 in 299 spins, worth 92x on average | every round | every round |
| Elephant Stampede | 1 in 93 spins | as in base (trigger board only) | as in base |
| Volatility (std dev per unit of cost) | 8.1 | 0.89 | 0.81 |
| Max win | cap 10,000x; highest seen 1,540x | highest seen 2,055x | highest seen 2,410x |

The cap is not reachable in practice yet. Shaping the top of the distribution needs the Stake optimizer (TODO Phase 1).

**Features**
- **Golden Elephant** is the WILD. It substitutes for every symbol except the scatter and also pays on its own.
- **Lion Rock** is the SCATTER. Three, four or five scatters pay 3x, 15x or 100x the bet and award 10, 15 or 20 free spins.
- **Gem Rush Free Spins** use richer reels (more wilds). Each winning free spin raises the **Gem Multiplier** by +1, up to x20. Free spins can retrigger.
- **Elephant Stampede** (base game, about 1 in 93 spins) turns 1, 2 or 3 of reels 2–4 fully wild (65% / 27% / 8%). It only picks reels that show no scatter, so it never takes a Lion Rock away. Book event: `elephantStampede { reels }`, right after the base `reveal`; the win is evaluated on the wild board.
- **Bonus Buy** (100x) is the natural Gem Rush: the round repeats natural base spins, stampede included, until 3+ scatters land. **Super Buy** (152x) is the same with the Gem Multiplier starting at x3. Each mode has its own books and lookup table (`simulate.py books --mode bonus`).

**Symbols:** Golden Elephant (W), Lion Rock (S), Leopard, Blue Sapphire, Star Ruby, Cat's Eye, Moonstone (the gem), and the numbers 10, 9, 8 and 7.

### Before release
- **Target the RTP variants Stake asks for.** Studios usually ship several RTP versions. Tune each one by changing reel weights only, then re-run `exact`.
- **Run 100M+ rounds** for the certification report. The ±0.42% standard error at 2.4M rounds is too wide for sign-off.
- **Use Stake Engine's optimizer.** Stake Engine's math-sdk includes an optimization step that reweights books to hit the target RTP and win distribution. Port `engine.py` into the official math-sdk structure (game_config / gamestate / events) so that you use their tooling directly.
- **Check every format against the current Stake Engine docs.** That covers book and lookup-table formats, event names, the RTP range, the max-win rules and amount scaling. Our formats are modelled on them but have not been checked against the live spec.

---

## 2. System architecture (how Stake games actually work)

```
 game_design.json ──► build.py ──► reel strips ──► simulate.py ──► books_*.jsonl + lookUpTable_*.csv
                                                                     │  (uploaded to Stake Engine)
                                                                     ▼
 Player ──► Frontend (static web build) ──► RGS /wallet/play ──► picks a book by weight, debits/credits
              ▲                                                         │
              └──────────── book events (reveal / winInfo / freeSpinTrigger / finalWin) ◄──┘
```

**Rule: the client never decides outcomes.** The frontend is a *player* of event lists. In this repo, `LocalDemoProvider` stands in for the RGS, and `StakeRGSProvider` is the skeleton for the real one. `Game.playBook()` is the same code path for both.

Production frontend stack (Stake Engine's web-sdk follows this pattern):
- **PixiJS (WebGL)** for rendering, replacing this prototype's Canvas2D
- **Svelte or TypeScript** for UI and state machines
- **Spine 2D** for skeletal symbol and character animation
- **GSAP** for tweens and timelines
- **Howler.js** or Pixi Sound for audio sprites
- **Vite** as the build tool, producing a static bundle

---

## 3. Motion spec (implemented in the prototype; hand these to animators)

| Moment | Spec |
|---|---|
| Spin start | 120 ms wind-up (symbols lift 0.2 cell), 200 ms ease-in acceleration, 60 ms stagger per reel |
| Spin | 27 cells/s (turbo 42), with a vertical motion-blur texture swap above 7 cells/s |
| Stop | 150 ms stagger. Target symbols are spliced in four or more cells above the window. The landing curve is easeOutBack (c=1, about 3.7% overshoot), with its start velocity matched to the spin speed so there is no visible jerk |
| Land | Thud and click per reel. Scatters and wilds pop (+22% scale, 400 ms), with a particle burst and a gem chime whose pitch rises with each scatter |
| Anticipation | Triggered by 2 scatters on reels 1 to 3. The previous reels settle first, then the next reel spins another 1.5 s with a pulsing gold frame, rising sparks and a riser sound |
| Line win | Lines draw on over 500 ms with a glow; winning symbols pulse; other symbols dim to 45%. After 1.8 s the display cycles one line at a time with a label, 1.25 s per line |
| Count-up | 0.5 to 2.4 s depending on win size, with ticks every 60 ms |
| Big win | 15x, 40x, 100x and 300x tiers: BIG, MEGA, EPIC, LEGENDARY. Includes rays, a coin fountain, an elastic tier-up and a fanfare |
| Free spins | Impact hit plus fanfare, then an intro with an elephant herd crossing. The scene switches to the torch-lit Gem Rush night under Lion Rock with a faster drum loop and a reed-horn melody. The multiplier pill pops on each step |

Production art replaces the procedural placeholders. Each symbol needs **idle, land and win** Spine animations:
- **Golden Elephant:** ears flap, trunk raises, crown gems twinkle
- **Lion Rock:** paws flex, sun rays sweep, dust falls from the cliff
- **Leopard:** blinks, ears twitch, a snarl on win
- **Gems:** specular sweep and sparkle
- **Elephant Stampede:** the herd charges down each chosen reel on a gold column, with dust, a short screen shake (off with reduced motion), a ground rumble, a hand-drum run and a reed-horn call; then the reel locks as full wilds
- **Moonstone:** the blue sheen drifts across the stone
- **Numbers:** a gold shine sweep

Export at 2x for desktop and at a 1x tier for low-end mobile. Use WebP atlases and keep the initial load under about 5 MB.

### 3.1 UI spec (implemented in the prototype; the UI kit and PixiJS port should match it)

| Element | Spec |
|---|---|
| Palette | Night lagoon `#070b1a`, sapphire panels `#0e1a3a` / `#15264f`, filigree gold `#f2c14e` (pale `#ffe7a3`), moonstone text `#c9d6f0`, muted `#8d9cc0`. Emerald `#14b85f` means "go" and ruby `#d4142f` means "stop" |
| Type | Cinzel Decorative only for the game title; Cinzel for the win amount and panel headings; Manrope (tabular figures) for labels and numbers |
| Spin gem | The signature control. An octagon-cut gem in a gold setting with four prongs. Emerald when idle with a slow glint every 5 s; ruby with a stop square while the reels run (press to skip); sapphire with the spins-left count during autoplay (press to stop). It rises 30% above the control bar |
| Control bar | Landscape: menu and mute · balance · bet (−, tap the value to choose, +) · **spin** · win · Auto · Turbo. Phone landscape (height ≤ 520 px) hides mute, the session clock and the button labels. Portrait: reels on top, then a grid of balance and win / Auto, −, spin, +, Turbo / menu, bet, mute |
| Portrait camera | The canvas fits the reel frame (world x 200–1080) to the screen width and sits the stage on the control bar. Extra height shows open sky |
| Menu | One panel with Paytable, History and Settings tabs (arrow keys move between tabs). Panels open centred in landscape and as bottom sheets in portrait |
| Autoplay | Limits must be chosen before it starts: spin count (10 / 25 / 50 / 100 / 250), loss limit (10x / 25x / 50x / 100x bet, checked before each bet) and single-win limit (off / 20x / 50x / 100x). Option to stop when Gem Rush starts, on by default. A toast gives the reason it stopped |
| History | The last 50 rounds (time, bet, win, multiplier, Gem Rush spins), plus session rounds, total bet, total won and net |
| Settings | Volume, sound effects, music, turbo, spin with the space bar, reduced motion. Saved per device in `localStorage` (optional) |
| Session clock | Wall clock, session length and net, top left (bottom of the stage in portrait). A reality-check aid |
| Reduced motion | Follows `prefers-reduced-motion` by default, with an in-game switch. It turns off fireflies, embers, coin showers, the title shimmer, ray rotation and the spin-gem glint, and shortens win counts (×0.4) and big wins (×0.5) |
| Accessibility | Buttons are at least 40 px on phones in landscape and 44 px in portrait. Every control has a visible focus ring and an accessible name. Panels trap Tab, close on Escape or a backdrop tap, and return focus to the button that opened them. Wins are announced through a polite live region |
| Keys | Space spins or skips (it can be turned off); Escape closes a panel |

---

## 4. Audio plan

The prototype synthesizes everything in WebAudio so it runs with no assets. For production:
- **Record or license real instruments:** hand drums, frame drums, a reed horn, marimba-style gem chimes, an elephant trumpet, and ocean and rainforest ambience. Use no religious bells or chants. Driving island drumming carries the identity of this game.
- **Music:** a base loop, a free-spins loop (more intense), and big-win stingers. Use stems so that layers can be added as tension builds.
- **SFX map:** spin start, reel loop, reel stop ×5 variants, scatter land 1/2/3, anticipation riser, win tiers 1 to 3, count tick, coin, multiplier up, free-spins intro and outro, and button clicks.
- **Delivery:** master to about −16 LUFS integrated, deliver OGG and AAC sprites, duck the music under big wins, and keep separate mute controls for music and SFX (already in the UI).

---

## 5. Theme and legal checks

1. **Theme rules (applied in v0.2.0).** No religious imagery and no Sinhala or Tamil words; every player-facing string is English. The temple scatter, stupa, ritual mask, carved moonstone and Sinhala text were removed. The full rules are in [CLAUDE.md](CLAUDE.md), and the scanner is `.claude/skills/theme-guard`. Still to do: an independent sensitivity review of the final commissioned art.
2. **Your own jurisdiction.** Get local legal advice on developing and supplying gambling software, and on receiving revenue from it.
3. **Stake Engine terms.** Check the onboarding requirements, the revenue share, the jurisdictions where your game will be offered, and the required responsible-gambling features (for example autoplay limits and reality checks).

## 6. Delivery roadmap

| Phase | Output | Rough time (small team) |
|---|---|---|
| 0. Concept | GDD, theme review, symbol sheet, moodboard | 1–2 wks |
| 1. Math | Final model, RTP variants, 100M-round reports, optimized books | 2–3 wks |
| 2. Art | Key art, symbols, background layers, Spine animations, UI kit | 6–8 wks |
| 3. Audio | Recorded or licensed instruments, music stems, SFX, mix | 3–4 wks (parallel) |
| 4. Frontend | Port to PixiJS + Stake web-sdk, RGS integration, portrait mobile layout, i18n | 4–6 wks |
| 5. QA | JS↔Python parity tests over 1M+ boards, visual regression, device matrix, soak tests, replay of every book event type | 2–3 wks |
| 6. Submission | Upload math and frontend to Stake Engine, then go through their review | per Stake |

**Team:** game designer and mathematician, a 2D artist, a Spine animator, a frontend developer, a sound designer, and QA. One person can cover several roles, but keep math review independent.

## 7. Known prototype gaps
- **Placeholder art.** Symbols are drawn in code; production needs commissioned art.
- **Layout.** Landscape, phone landscape and portrait work (see §3.1). Tablet 4:3 uses the landscape layout with letterboxing.
- **Parity is checked, not yet in CI.** `tools/parity/` compares the JS `MathEngine` with `engine.py` on base, free, uniform-random and edge-case boards, and replays full rounds (free spins, multiplier, retriggers, max-win cap) from Python's recorded reel stops. Run 1M boards per mode before release.
- **Responsible-gambling profiles.** Autoplay limits, reduced motion and a session clock are in. Jurisdiction switches (minimum spin time, no turbo, no autoplay) and a timed reality-check dialog are not.
- **`StakeRGSProvider` is untested.** It is a skeleton and must be validated against the live RGS spec.
