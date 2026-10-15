---
name: theme-guard
description: Check Island of Gems art, text, audio and naming against the theme rules (no religious imagery, English only). Use before committing any change to symbols, backgrounds, UI strings, feature names, audio cues or asset names, or when asked to "check the theme", "is this culturally safe" or "review the content".
---

# Theme guard

The game ships worldwide on Stake. It must read as **island culture and nature**, never religion, and every player-facing word must be **English**.

## 1. Run the scanner

```bash
python -I .claude/skills/theme-guard/scripts/check_theme.py            # frontend, math, apps, packages
python -I .claude/skills/theme-guard/scripts/check_theme.py path/to/file
```

The scanner exits with code 1 on any hit. It flags religious terms, known Sinhala and Tamil transliterations, and any Sinhala or Tamil script. Fix every hit. Do not add a word to an allowlist without asking the user.

## 2. Review what the scanner cannot see

The scanner only reads text. Review drawn and described art by hand against this table:

| Never | Use instead |
|---|---|
| Temple, stupa, shrine, any place of worship | Lion Rock fortress, lighthouse, fort ramparts, waterfalls, tea hills |
| Religious festival, procession, ceremonial parasol, festival lanterns | Elephant herd crossing, Lion Rock at night, torches, fireflies |
| Carved temple-step "moonstone" (half-circle with animal rings and lotus) | The moonstone **gem**: a milky cabochon with a blue sheen |
| Demon, exorcism or ritual masks; naga or cobra crowns | Leopard, peacock, sea turtle, blue whale |
| Halos, lotus thrones, prayer gestures, bells or chants | Gem glints, gold filigree, sun rays, marimba-style chimes |
| Sinhala or Tamil words, script or transliterations | Plain English ("Gem Rush", "Legendary Win", "hand drum") |

When an item is borderline (it has *any* religious association in any major culture), leave it out and propose a nature or gem alternative.

## 3. Report

List each finding as `path:line: term: replacement`. Then make the change (rename it, redraw it or reword it), re-run the scanner until it is clean, and run `python build.py` in `math/` if `game_design.json` changed.
