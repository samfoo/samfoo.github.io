#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
Seed or update a weekly training log from data/garmin.json.

Runs (and anything else recorded on the watch) are pulled from the already-synced
Garmin data into the week's log file under training/logs/YYYY-Www.md. Strength and
climbing are still logged by hand — Garmin doesn't see the barbell.

If the log file doesn't exist yet it's created from the plan schedule; if it does,
only the "## Garmin summary" block is refreshed (your hand-written notes are kept).

Usage:
    ./scripts/training_log.py                 # current ISO week
    ./scripts/training_log.py --week 2026-W29
    ./scripts/garmin_sync.py && ./scripts/training_log.py   # refresh data first
"""

import argparse
import json
import re
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
GARMIN = ROOT / "data" / "garmin.json"
LOGDIR = ROOT / "training" / "logs"

# Plan schedule: ISO week -> (plan_wk, block, lifting focus, quality run, long-run km)
PLAN = {
    "2026-W28": (1,  "Block 1 — Foundation", "main lifts 3×6–8 @ RPE7, groove technique", "strides 6×20s", "12–14"),
    "2026-W29": (2,  "Block 1 — Foundation", "add load, 3×6–8", "strides + short tempo 2×5 min Z3", "13–15"),
    "2026-W30": (3,  "Block 1 — Foundation", "4×6–8 @ RPE7–8", "tempo 3×5 min Z3", "15–16"),
    "2026-W31": (4,  "Block 1 — Deload", "2×5 @ RPE6, light", "easy strides only", "8–10 (deload)"),
    "2026-W32": (5,  "Block 2 — Build", "4×4–6 @ RPE7–8", "tempo 2×8 min Z3", "15–17"),
    "2026-W33": (6,  "Block 2 — Build", "add load, 4×4–6", "intervals 5×3 min Z4", "16–18"),
    "2026-W34": (7,  "Block 2 — Build", "4×4–6 @ RPE8", "tempo 20 min continuous Z3", "17–18"),
    "2026-W35": (8,  "Block 2 — Deload", "2×5 @ RPE6, light", "easy strides only", "9–11 (deload)"),
    "2026-W36": (9,  "Block 3 — Progress", "4×3–5 @ RPE8", "intervals 6×3 min Z4", "18"),
    "2026-W37": (10, "Block 3 — Progress", "add load, 5×3", "tempo 2×10 min Z3", "18–20"),
    "2026-W38": (11, "Block 3 — Progress", "4×3–5 @ RPE8", "intervals 4×4 min Z4", "18–20"),
    "2026-W39": (12, "Block 3 — Progress", "top singles/triples @ RPE8", "sharpening 4×2 min Z4", "16"),
    "2026-W40": (13, "Test / Deload", "re-test big 3 (top set @ RPE8)", "benchmark run (5k TT or HR@6:30/km)", "12 easy"),
}


def week_bounds(iso_week: str) -> tuple[date, date]:
    """'2026-W28' -> (Monday, Sunday) dates for that ISO week."""
    year, wk = iso_week.split("-W")
    monday = date.fromisocalendar(int(year), int(wk), 1)
    return monday, monday + timedelta(days=6)


def current_iso_week() -> str:
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def garmin_block(iso_week: str) -> str:
    """Build the '## Garmin summary' section for the given week from garmin.json."""
    mon, sun = week_bounds(iso_week)
    lo, hi = mon.isoformat(), sun.isoformat()

    if not GARMIN.exists():
        rows = "| _(data/garmin.json not found — run scripts/garmin_sync.py)_ | | | | | |"
        return _summary(rows, "—", "—", "—")

    data = json.loads(GARMIN.read_text())

    acts = [a for a in data.get("activities", []) if lo <= a.get("date", "") <= hi]
    acts.sort(key=lambda a: a["date"])
    if acts:
        rows = "\n".join(
            f"| {a['date']} | {a.get('type','')} | {a.get('distance_km') or ''} | "
            f"{a.get('duration_min') or ''} | {a.get('avg_hr') or ''} | |"
            for a in acts
        )
    else:
        rows = "| _(no activities recorded this week)_ | | | | | |"

    daily = [d for d in data.get("daily_stats", []) if lo <= d.get("date", "") <= hi]
    rhr = [d["resting_hr"] for d in daily if d.get("resting_hr")]
    sleep = [d["sleep_hours"] for d in daily if d.get("sleep_hours")]
    wt = [w["weight_kg"] for w in data.get("weight", []) if lo <= w.get("date", "") <= hi and w.get("weight_kg")]

    wt_s = f"{min(wt):.1f}–{max(wt):.1f} (avg {statistics.mean(wt):.1f})" if wt else "—"
    rhr_s = f"{statistics.mean(rhr):.0f}" if rhr else "—"
    sleep_s = f"{statistics.mean(sleep):.1f}" if sleep else "—"
    return _summary(rows, wt_s, rhr_s, sleep_s)


def _summary(rows: str, wt: str, rhr: str, sleep: str) -> str:
    return (
        "## Garmin summary\n"
        f"_Auto-filled from data/garmin.json on {date.today().isoformat()}. "
        "Strength & climbing are logged by hand above._\n\n"
        "| Date | Type | km | min | avg HR | notes |\n"
        "|------|------|----|----|--------|-------|\n"
        f"{rows}\n\n"
        f"- Weight this week: {wt} kg\n"
        f"- Resting HR avg: {rhr} · Sleep avg: {sleep} h\n"
    )


def seed_file(iso_week: str) -> str:
    """Create a fresh week log from the plan schedule."""
    mon, sun = week_bounds(iso_week)
    plan_wk, block, focus, quality, km = PLAN.get(
        iso_week, ("?", "(outside the 13-week plan)", "—", "—", "—")
    )
    return f"""# {iso_week} · Plan week {plan_wk} · {block}

**Dates:** {mon.isoformat()} → {sun.isoformat()}
**Focus:** {focus} · quality run = {quality} · long run target {km} km

## Readiness / context
- Travel this week? _no / where_
- Notes (sleep, energy, niggles):

## Planned vs. actual

| Day | Planned | Actual | Tier | Notes |
|-----|---------|--------|------|-------|
| Mon | Lift Day A | | A/B/C | |
| Tue | Run easy Z2 40–50 min | | A/B/C | |
| Wed | rest / climb | | | |
| Thu | Lift Day B | | A/B/C | |
| Fri | Run quality: {quality} | | A/B/C | |
| Sat | Run long easy {km} km | | A/B/C | |
| Sun | rest / walk | | | |

## Lifts (fill in — Garmin doesn't see these)
- **Day A:** squat ___×___  bench ___×___  RDL ___  row ___  core ___
- **Day B:** deadlift ___×___  OHP/incline ___  front squat/lunge ___  pull-up ___  core ___
- Working-weight changes → update `../strength.md`

{garmin_block(iso_week)}
## Sunday review
- Hit the essentials (1 lift + 1 long/quality run)? _yes/no_
- What to adjust next week:
"""


def update_file(text: str, iso_week: str) -> str:
    """Replace the existing '## Garmin summary' block, keep everything else."""
    block = garmin_block(iso_week)
    # Match from the Garmin summary header up to (but not including) the next '## '
    pattern = re.compile(r"## Garmin summary.*?(?=\n## )", re.DOTALL)
    if pattern.search(text):
        return pattern.sub(block, text, count=1)
    # No block found — append before the Sunday review if present, else at end.
    if "## Sunday review" in text:
        return text.replace("## Sunday review", block + "\n## Sunday review", 1)
    return text.rstrip() + "\n\n" + block


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed/update a weekly training log from Garmin data")
    ap.add_argument("--week", default=current_iso_week(), help="ISO week, e.g. 2026-W29 (default: current)")
    args = ap.parse_args()

    iso_week = args.week
    LOGDIR.mkdir(parents=True, exist_ok=True)
    path = LOGDIR / f"{iso_week}.md"

    if path.exists():
        new = update_file(path.read_text(), iso_week)
        path.write_text(new)
        print(f"Updated Garmin summary in {path.relative_to(ROOT)}")
    else:
        path.write_text(seed_file(iso_week))
        print(f"Created {path.relative_to(ROOT)} from the plan schedule")


if __name__ == "__main__":
    main()
