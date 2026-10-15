"""Build reel strips from game_design.json and publish the config.

Outputs:
  math/out/game_config.json   design + generated strips (input for simulate.py)
  frontend/index.html         config injected into <script id="game-config">

Strips are deterministic (seeded) so math and frontend always agree.
"""
from __future__ import annotations

import json
import random
import re

from engine import CONFIG_PATH, DESIGN_PATH, ROOT, ROWS, SCATTER

FRONTEND = ROOT.parent / "frontend" / "index.html"


def build_strip(weights: dict, rng: random.Random) -> list[str]:
    strip = [sym for sym, n in weights.items() for _ in range(n)]
    for _ in range(10_000):
        rng.shuffle(strip)
        idx = [i for i, s in enumerate(strip) if s == SCATTER]
        L = len(strip)
        # At most one scatter visible per reel window.
        ok = all(min((b - a) % L, (a - b) % L) >= ROWS for a in idx for b in idx if a != b)
        if ok:
            return strip
    raise RuntimeError("Could not space scatters; lower scatter weight or lengthen strip")


def main():
    with open(DESIGN_PATH, encoding="utf-8-sig") as f:
        design = json.load(f)
    rng = random.Random(design["stripSeed"])
    strips = {mode: [build_strip(w, rng) for w in reels] for mode, reels in design["reelWeights"].items()}
    cfg = {k: v for k, v in design.items() if not k.startswith("_") and k != "reelWeights"}
    cfg["strips"] = strips

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, separators=(",", ":"))
    print(f"wrote {CONFIG_PATH}")
    for mode, reels in strips.items():
        print(f"  {mode}: strip lengths {[len(s) for s in reels]}")

    if FRONTEND.exists():
        html = FRONTEND.read_text(encoding="utf-8")
        payload = json.dumps(cfg, separators=(",", ":"))
        pattern = re.compile(r'(<script id="game-config" type="application/json">)(.*?)(</script>)', re.S)
        if not pattern.search(html):
            raise SystemExit("frontend/index.html is missing <script id=\"game-config\">")
        html = pattern.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
        FRONTEND.write_text(html, encoding="utf-8")
        print(f"injected config into {FRONTEND}")


if __name__ == "__main__":
    main()
