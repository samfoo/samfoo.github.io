#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "garminconnect>=0.3.6",
# ]
# ///
"""
Build the structured *running* workout for a given plan week and push it to
Garmin Connect, so it shows up on the watch (Menu → Training → Workouts) with
guided intervals instead of you tapping it in by hand.

Only the quality session is generated per week — the one that benefits from
on-watch structure (strides / tempo / intervals / time-trial). Easy and long
runs are "just run at the right HR" and don't need a structured workout.

Auth reuses the token cache from garmin_sync.py (~/.garth). Run that first if
you've never authenticated.

Usage:
    ./scripts/garmin_workout.py                      # upload current ISO week's workout
    ./scripts/garmin_workout.py --week 2026-W31
    ./scripts/garmin_workout.py --week 2026-W31 --schedule 2026-07-29
    ./scripts/garmin_workout.py --dry-run            # print JSON, no upload
    ./scripts/garmin_workout.py --list               # list plan workouts on Garmin
    ./scripts/garmin_workout.py --week 2026-W31 --delete   # remove that week's workout

Re-uploading a week replaces the previous copy of the same name (idempotent),
so it's safe to re-run.
"""

import argparse
import json
import os
import sys
from datetime import date

TOKENSTORE = os.path.expanduser("~/.garth")
NAME_PREFIX = "[Plan]"  # marks workouts this script owns, for list/replace/delete

# ---------------------------------------------------------------------------
# Heart-rate zones (from training/principles.md — set off Sam's own data)
# ---------------------------------------------------------------------------
Z3 = (158, 168)   # tempo / threshold
Z4 = (170, 180)   # VO2 / intervals

# Garmin enum IDs
STEP = {"warmup": 1, "cooldown": 2, "interval": 3, "recovery": 4, "rest": 5, "repeat": 6}
COND = {"time": 2, "distance": 3, "iterations": 7}
TARGET_HR = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"}
TARGET_NONE = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}


# ---------------------------------------------------------------------------
# Tiny DSL for describing a session, compiled to Garmin JSON below.
# Each node is a dict; targets are (lo, hi) HR tuples or None.
# ---------------------------------------------------------------------------
def _t(minutes):  # minutes -> seconds
    return float(minutes) * 60.0

def warmup(minutes=10):            return {"k": "warmup",   "secs": _t(minutes)}
def cooldown(minutes=10):          return {"k": "cooldown", "secs": _t(minutes)}
def tempo(minutes, hr=Z3):         return {"k": "interval", "secs": _t(minutes), "hr": hr}
def vo2(minutes, hr=Z4):           return {"k": "interval", "secs": _t(minutes), "hr": hr}
def stride(seconds=20):            return {"k": "interval", "secs": float(seconds)}       # effort-based, no HR
def jog(seconds):                  return {"k": "recovery", "secs": float(seconds)}
def repeat(times, steps):          return {"k": "repeat", "times": times, "steps": steps}
def timetrial(meters):             return {"k": "interval", "dist": float(meters)}        # all-out, no target


# The quality session per plan week (mirrors training/plan.md's "quality run").
def workout_catalog():
    return {
        "2026-W28": ("Strides 6×20s",          [warmup(), repeat(6, [stride(20), jog(60)]), cooldown()]),
        "2026-W29": ("Strides + 2×5min tempo", [warmup(), repeat(6, [stride(20), jog(60)]),
                                                repeat(2, [tempo(5), jog(90)]), cooldown()]),
        "2026-W30": ("Tempo 3×5min Z3",        [warmup(), repeat(3, [tempo(5), jog(90)]), cooldown()]),
        "2026-W31": ("Strides 6×20s",          [warmup(), repeat(6, [stride(20), jog(60)]), cooldown()]),
        "2026-W32": ("Tempo 2×8min Z3",        [warmup(), repeat(2, [tempo(8), jog(120)]), cooldown()]),
        "2026-W33": ("Intervals 5×3min Z4",    [warmup(12), repeat(5, [vo2(3), jog(120)]), cooldown()]),
        "2026-W34": ("Deload strides 4×20s",   [warmup(), repeat(4, [stride(20), jog(90)]), cooldown()]),
        "2026-W35": ("Tempo 3×6min Z3",        [warmup(), repeat(3, [tempo(6), jog(120)]), cooldown()]),
        "2026-W36": ("Intervals 6×3min Z4",    [warmup(12), repeat(6, [vo2(3), jog(120)]), cooldown()]),
        "2026-W37": ("Tempo 2×10min Z3",       [warmup(), repeat(2, [tempo(10), jog(120)]), cooldown()]),
        "2026-W38": ("Intervals 4×4min Z4",    [warmup(12), repeat(4, [vo2(4), jog(150)]), cooldown()]),
        "2026-W39": ("Sharpening 4×2min Z4",   [warmup(12), repeat(4, [vo2(2), jog(120)]), cooldown()]),
        "2026-W40": ("Benchmark 5k time trial",[warmup(12), timetrial(5000), cooldown()]),
    }


# ---------------------------------------------------------------------------
# Compile the DSL to a Garmin workout payload
# ---------------------------------------------------------------------------
def _exec_step(order, node):
    if "dist" in node:
        end = {"conditionTypeId": COND["distance"], "conditionTypeKey": "distance"}
        end_val = node["dist"]
    else:
        end = {"conditionTypeId": COND["time"], "conditionTypeKey": "time"}
        end_val = node["secs"]
    step = {
        "type": "ExecutableStepDTO",
        "stepOrder": order,
        "stepType": {"stepTypeId": STEP[node["k"]], "stepTypeKey": node["k"]},
        "endCondition": end,
        "endConditionValue": end_val,
        "targetType": TARGET_NONE,
    }
    if node.get("hr"):
        lo, hi = node["hr"]
        step["targetType"] = TARGET_HR
        step["targetValueOne"] = float(lo)
        step["targetValueTwo"] = float(hi)
    return step


def _compile_steps(nodes, counter):
    out = []
    for node in nodes:
        if node["k"] == "repeat":
            order = next(counter)
            children = _compile_steps(node["steps"], counter)
            out.append({
                "type": "RepeatGroupDTO",
                "stepOrder": order,
                "stepType": {"stepTypeId": STEP["repeat"], "stepTypeKey": "repeat"},
                "numberOfIterations": node["times"],
                "smartRepeat": False,
                "endCondition": {"conditionTypeId": COND["iterations"], "conditionTypeKey": "iterations"},
                "endConditionValue": float(node["times"]),
                "workoutSteps": children,
            })
        else:
            out.append(_exec_step(next(counter), node))
    return out


def build_payload(name, nodes):
    def _counter():
        n = 0
        while True:
            n += 1
            yield n
    running = {"sportTypeId": 1, "sportTypeKey": "running"}
    return {
        "sportType": running,
        "workoutName": name,
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": running,
            "workoutSteps": _compile_steps(nodes, _counter()),
        }],
    }


def describe(nodes, indent="  "):
    """Human-readable one-liner-per-step summary for --dry-run / confirmation."""
    lines = []
    def walk(ns, depth):
        for n in ns:
            pad = indent * depth
            if n["k"] == "repeat":
                lines.append(f"{pad}repeat ×{n['times']}:")
                walk(n["steps"], depth + 1)
            elif "dist" in n:
                lines.append(f"{pad}{n['k']}: {n['dist']/1000:g} km, all-out")
            else:
                tgt = f" @ HR {n['hr'][0]}–{n['hr'][1]}" if n.get("hr") else ""
                mins = n["secs"] / 60
                dur = f"{n['secs']:.0f}s" if n["secs"] < 60 else f"{mins:g} min"
                lines.append(f"{pad}{n['k']}: {dur}{tgt}")
    walk(nodes, 0)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Garmin client
# ---------------------------------------------------------------------------
def init_api():
    from garminconnect import Garmin
    if not os.path.exists(TOKENSTORE):
        print(f"No token cache at {TOKENSTORE}. Run ./scripts/garmin_sync.py first to authenticate.",
              file=sys.stderr)
        sys.exit(1)
    api = Garmin()
    api.login(TOKENSTORE)
    return api


def current_iso_week():
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def plan_workouts(api):
    """Existing workouts on Garmin that this script owns (name starts with NAME_PREFIX)."""
    return [w for w in api.get_workouts(0, 200) if (w.get("workoutName") or "").startswith(NAME_PREFIX)]


def main():
    ap = argparse.ArgumentParser(description="Push a plan week's running workout to Garmin")
    ap.add_argument("--week", default=current_iso_week(), help="ISO week, e.g. 2026-W31 (default: current)")
    ap.add_argument("--schedule", metavar="YYYY-MM-DD", help="also schedule it on this date")
    ap.add_argument("--dry-run", action="store_true", help="print the workout, don't upload")
    ap.add_argument("--list", action="store_true", help="list plan workouts already on Garmin")
    ap.add_argument("--delete", action="store_true", help="delete this week's workout from Garmin")
    args = ap.parse_args()

    catalog = workout_catalog()

    if args.list:
        for w in plan_workouts(init_api()):
            print(f"  {w['workoutId']}  {w['workoutName']}")
        return

    if args.week not in catalog:
        print(f"No workout defined for {args.week}. Known: {', '.join(sorted(catalog))}", file=sys.stderr)
        sys.exit(1)

    label, nodes = catalog[args.week]
    name = f"{NAME_PREFIX} {args.week} · {label}"

    if args.dry_run:
        print(name)
        print(describe(nodes))
        print("\n--- payload ---")
        print(json.dumps(build_payload(name, nodes), indent=2))
        return

    api = init_api()

    if args.delete:
        existing = [w for w in plan_workouts(api) if w["workoutName"] == name]
        for w in existing:
            api.delete_workout(w["workoutId"])
            print(f"Deleted {w['workoutId']}  {name}")
        if not existing:
            print(f"Nothing to delete for {args.week}")
        return

    # Replace any previous copy of the same name so re-runs don't pile up duplicates.
    for w in plan_workouts(api):
        if w["workoutName"] == name:
            api.delete_workout(w["workoutId"])

    payload = build_payload(name, nodes)
    res = api.upload_workout(payload)
    wid = res.get("workoutId")
    print(f"Uploaded → {name}  (workoutId {wid})")
    print(describe(nodes))

    if args.schedule:
        api.schedule_workout(wid, args.schedule)
        print(f"Scheduled on {args.schedule} — it'll show on the watch that day.")
    else:
        print("On the watch: Menu → Training → Workouts → pick it. "
              "(Pass --schedule YYYY-MM-DD to pin it to a date.)")


if __name__ == "__main__":
    main()
