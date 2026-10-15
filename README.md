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

---

## 1. Current math model (v0.2.0, the same math as v0.1.0 with the theme renamed)

| Metric | Value |
|---|---|
| RTP | **96.10%** (exact base + 300k FS sessions per trigger size). The full Monte Carlo of 2.4M rounds gives 96.19% ± 0.42% |
| Base game / free spins split | 65.2% / 30.9% |
| Hit rate | 36.9% (1 in 2.71) |
| Free spins frequency | 1 in 195 spins |
| Volatility (std dev per round) | 6.5, medium |
| Max win cap | 5,000x |

**Features**
- **Golden Elephant** is the WILD. It substitutes for every symbol except the scatter and also pays on its own.
- **Lion Rock** is the SCATTER. Three, four or five scatters pay 3x, 15x or 100x the total bet and award 10, 15 or 20 free spins.
- **Gem Rush Free Spins** use richer reels (more wilds). Each winning free spin raises the **Gem Multiplier** by +1, up to x10. Free spins can retrigger.

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
| Free spins | Impact hit plus fanfare, then an intro with an elephant herd crossing. The scene switches to the lantern-lit Gem Rush night with a faster drum loop and a reed-horn melody. The multiplier pill pops on each step |

Production art replaces the procedural placeholders. Each symbol needs **idle, land and win** Spine animations:
- **Golden Elephant:** ears flap, trunk raises, crown gems twinkle
- **Lion Rock:** paws flex, sun rays sweep, dust falls from the cliff
- **Leopard:** blinks, ears twitch, a snarl on win
- **Gems:** specular sweep and sparkle
- **Moonstone:** the blue sheen drifts across the stone
- **Numbers:** a gold shine sweep

Export at 2x for desktop and at a 1x tier for low-end mobile. Use WebP atlases and keep the initial load under about 5 MB.

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
- **Layout.** Landscape only; a portrait mobile layout is still needed.
- **No automated parity test.** Nothing yet checks the JS engine against `engine.py`; write one that compares `lineWin` on random boards.
- **No `prefers-reduced-motion` mode** and no autoplay limits yet.
- **`StakeRGSProvider` is untested.** It is a skeleton and must be validated against the live RGS spec.
