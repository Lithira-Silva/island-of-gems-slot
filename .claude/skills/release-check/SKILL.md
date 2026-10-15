---
name: release-check
description: Pre-submission checklist for an Island of Gems build going to Stake Engine. Use for "is it ready to ship", "prepare the release", "submission check" or before tagging a version.
---

# Release check

Run every gate and report pass or fail with evidence (command output, numbers). Do not tick a gate you did not run.

## Gates

| # | Gate | How |
|---|---|---|
| 1 | Theme | `python -I .claude/skills/theme-guard/scripts/check_theme.py` reports clean, and the manual art review in the theme-guard skill is done |
| 2 | Math final | `game_design.json` version is bumped. The `exact` result is on target. 100M+ rounds per mode and variant with RTP within ±0.1%. Max win is reachable and capped |
| 3 | Books | Books and LUTs are regenerated from the final strips. Every book passes schema validation. `payoutMultiplier` equals the sum of event amounts |
| 4 | Parity | `parity-check` shows 0 mismatches on 1M boards per mode |
| 5 | Client | Build succeeds, size budget is met (ARCHITECTURE §8), and Playwright visual tests pass |
| 6 | Player info | Paytable RTP, max win and rules match `stats.json` and config, for every mode |
| 7 | Responsible gambling | Autoplay limits work, jurisdiction profile switches work, and reduced motion works |
| 8 | Devices | Pass on low-end Android, iPhone SE and desktop Chrome, Safari and Firefox |
| 9 | Stake spec | Event names, amount scaling, RGS calls and the upload format were checked against the **current** Stake Engine docs. Record the doc date |
| 10 | Repo | `README.md` stats are updated, `TODO.md` is updated, the version tag is created, and no secrets are in the diff |

## Output
A table of the 10 gates with a status and evidence for each, then a list of the blockers. Only if every gate passes, and the user approves, tag the release:
```bash
git tag -a vX.Y.Z -m "Island of Gems vX.Y.Z" && git push origin vX.Y.Z
```
