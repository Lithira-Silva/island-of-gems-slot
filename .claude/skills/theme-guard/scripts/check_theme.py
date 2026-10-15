"""Scan shipped game files for religious imagery terms and non-English text.

Usage:  python .claude/skills/theme-guard/scripts/check_theme.py [paths...]
Default paths: frontend math apps packages (whichever exist).
Exit code 1 when anything is found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATHS = ["frontend", "math", "apps", "packages"]
TEXT_EXT = {".html", ".js", ".ts", ".svelte", ".css", ".json", ".py", ".md", ".csv", ".txt", ".svg", ".atlas"}
SKIP_DIRS = {"node_modules", ".git", "dist", "out", "__pycache__", ".venv"}

# Religious places, people, objects and events.
RELIGIOUS = [
    "temple", "stupa", "dagoba", "pagoda", "shrine", "church", "chapel", "mosque", "kovil", "devale",
    "buddha", "buddhist", "bodhi", "hindu", "deity", "deities", "god", "gods", "goddess", "demon", "devil",
    "monk", "priest", "nun", "relic", "tooth relic", "prayer", "pray", "praying", "holy", "sacred", "blessing",
    "ritual", "exorcism", "pilgrim", "pilgrimage", "vesak", "poson", "esala", "perahera", "maligawa", "dalada",
    "pirith", "lantern", "lanterns", "naga", "hamsa", "halo", "lotus throne", "sandakada", "pahana",
]
# Sinhala / Tamil words and transliterations that crept in before.
NON_ENGLISH = [
    "lanka", "tusker treasures", "raksha", "sanni", "kolam", "ratnapura", "ratna", "maha", "jaya", "ayubowan",
    "horanewa", "geta bera", "yak bera", "davula", "thammattama", "udekki", "nettipattam", "pattirippuwa",
    "ruwanwelisaya", "sri ",
]
SCRIPT = re.compile(r"[඀-෿஀-௿]")  # Sinhala, Tamil
TERMS = re.compile(r"\b(" + "|".join(re.escape(t.strip()) for t in RELIGIOUS + NON_ENGLISH) + r")\b", re.I)


def files(paths: list[str]):
    for p in paths:
        base = (ROOT / p)
        if base.is_file():
            yield base
        elif base.is_dir():
            for f in base.rglob("*"):
                if f.is_file() and f.suffix.lower() in TEXT_EXT and not SKIP_DIRS & set(f.parts):
                    yield f


def main() -> int:
    paths = sys.argv[1:] or [p for p in DEFAULT_PATHS if (ROOT / p).exists()]
    hits = 0
    for f in files(paths):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            found = [m.group(0) for m in TERMS.finditer(line)]
            if SCRIPT.search(line):
                found.append("<non-Latin script>")
            if found:
                hits += 1
                print(f"{f.relative_to(ROOT)}:{n}: {', '.join(sorted(set(found)))}")
    print(f"theme-guard: {hits} line(s) flagged" if hits else "theme-guard: clean")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
