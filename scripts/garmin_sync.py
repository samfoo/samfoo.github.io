#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "garminconnect>=0.3.6",
# ]
# ///
"""
Fetch Garmin Connect data (watch + smart scale) and write data/garmin.json
for the samfoo.github.io health page.

First run: set GARMIN_EMAIL and GARMIN_PASSWORD env vars. Tokens are cached
at ~/.garth so subsequent runs don't need credentials.

Usage:
    ./scripts/garmin_sync.py [--days N]   (default: 90)
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

TOKENSTORE = os.path.expanduser("~/.garth")
OUTFILE = Path(__file__).parent.parent / "data" / "garmin.json"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def init_api() -> Garmin:
    """Return an authenticated Garmin API client, using cached tokens when possible.

    On first run pass GARMIN_EMAIL / GARMIN_PASSWORD env vars (or answer the
    interactive prompts). Tokens are saved to ~/.garth; subsequent runs skip
    the full login entirely.
    """
    # --- token-cache path: skip credential login entirely ---
    if Path(TOKENSTORE).exists():
        try:
            api = Garmin()
            api.login(TOKENSTORE)
            print(f"Authenticated from token cache ({TOKENSTORE})")
            return api
        except Exception as e:
            print(f"Token cache invalid ({e}), falling back to credentials …", file=sys.stderr)

    # --- credential path ---
    email = os.getenv("GARMIN_EMAIL") or input("Garmin email: ")
    password = os.getenv("GARMIN_PASSWORD") or getpass("Garmin password: ")

    def prompt_mfa() -> str:
        return input("Garmin MFA code: ").strip()

    try:
        # prompt_mfa is only invoked if Garmin challenges for a 2FA code.
        api = Garmin(email, password, prompt_mfa=prompt_mfa)
        # Passing tokenstore here makes login() save tokens automatically after
        # a successful credential-based auth (no separate .dump() call needed).
        api.login(TOKENSTORE)
        print(f"Authenticated and saved tokens to {TOKENSTORE}")
        return api
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate limit" in msg.lower():
            print(
                "\nGarmin returned HTTP 429 (IP rate limited). This is the most "
                "common cause of 'auth not working' — it is NOT a bad password.\n"
                "Wait 15-30 minutes (avoid rapid retries, which extend the "
                "block) and try again.\n"
                "Tip: once you authenticate successfully, tokens are cached at "
                f"{TOKENSTORE} and subsequent runs skip login entirely.",
                file=sys.stderr,
            )
        else:
            print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------

def fetch_body_composition(api: Garmin, start: date, end: date) -> list[dict]:
    """Return list of daily body composition records."""
    records = []
    try:
        raw = api.get_body_composition(start.isoformat(), end.isoformat())
        entries = raw.get("dateWeightList") or raw.get("totalAverage", {})
        if not isinstance(entries, list):
            return records
        for entry in entries:
            cal_date = entry.get("calendarDate")
            if not cal_date:
                continue
            weight_g = entry.get("weight")
            muscle_g = entry.get("muscleMass")
            bone_g = entry.get("boneMass")
            # The scale occasionally logs weight but fails the body-fat
            # reading, storing 0.0 — treat that as missing.
            body_fat = entry.get("bodyFat")
            records.append({
                "date": cal_date,
                "weight_kg": round(weight_g / 1000, 2) if weight_g else None,
                "bmi": entry.get("bmi"),
                "body_fat_pct": body_fat if body_fat else None,
                "muscle_mass_kg": round(muscle_g / 1000, 2) if muscle_g else None,
                "bone_mass_kg": round(bone_g / 1000, 2) if bone_g else None,
            })
    except Exception as e:
        print(f"Warning: body composition fetch failed: {e}", file=sys.stderr)
    return records


def fetch_daily_stats(api: Garmin, start: date, end: date) -> list[dict]:
    """Return list of daily stats (steps, calories, HR, sleep)."""
    records = []
    current = start
    while current <= end:
        day_str = current.isoformat()
        record: dict = {"date": day_str}

        # Steps, calories, heart rate
        try:
            stats = api.get_stats(day_str)
            record["steps"] = stats.get("totalSteps")
            record["step_goal"] = stats.get("dailyStepGoal")
            record["calories"] = stats.get("totalKilocalories")
            record["active_calories"] = stats.get("activeKilocalories")
            record["avg_hr"] = stats.get("averageHeartRate")
            record["resting_hr"] = stats.get("restingHeartRate")
            record["intensity_minutes"] = (
                (stats.get("moderateIntensityMinutes") or 0)
                + (stats.get("vigorousIntensityMinutes") or 0) * 2
            )
        except Exception as e:
            print(f"Warning: stats fetch failed for {day_str}: {e}", file=sys.stderr)

        # VO2 max — the dominant input to Garmin's fitness age.
        # get_max_metrics returns a list; the "generic" (running) VO2 max
        # lives under vo2MaxPreciseValue (falls back to vo2MaxValue).
        try:
            mm = api.get_max_metrics(day_str)
            generic = (mm[0].get("generic") if mm else None) or {}
            record["vo2max"] = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")
        except Exception as e:
            print(f"Warning: vo2max fetch failed for {day_str}: {e}", file=sys.stderr)

        # Sleep
        try:
            sleep = api.get_sleep_data(day_str)
            dto = sleep.get("dailySleepDTO", {})
            secs = dto.get("sleepTimeSeconds")
            record["sleep_hours"] = round(secs / 3600, 2) if secs else None
            record["sleep_score"] = dto.get("sleepScores", {}).get("overall", {}).get("value") if dto.get("sleepScores") else None
        except Exception as e:
            print(f"Warning: sleep fetch failed for {day_str}: {e}", file=sys.stderr)

        records.append(record)
        current += timedelta(days=1)
    return records


def fetch_activities(api: Garmin, days: int) -> list[dict]:
    """Return recent activities."""
    records = []
    try:
        # Fetch more than we need; filter by date client-side
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        batch_size = 100
        start = 0
        while True:
            batch = api.get_activities(start, batch_size)
            if not batch:
                break
            for act in batch:
                act_date = (act.get("startTimeLocal") or "")[:10]
                if act_date < cutoff:
                    return records  # activities are newest-first; stop here
                dist_m = act.get("distance") or 0
                dur_s = act.get("duration") or 0
                records.append({
                    "date": act_date,
                    "name": act.get("activityName", ""),
                    "type": (act.get("activityType") or {}).get("typeKey", "other"),
                    "distance_km": round(dist_m / 1000, 2) if dist_m else None,
                    "duration_min": round(dur_s / 60, 1) if dur_s else None,
                    "avg_hr": act.get("averageHR"),
                    "calories": act.get("calories"),
                    "avg_speed_kph": round(act.get("averageSpeed", 0) * 3.6, 1) if act.get("averageSpeed") else None,
                })
            if len(batch) < batch_size:
                break
            start += batch_size
    except Exception as e:
        print(f"Warning: activities fetch failed: {e}", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sync Garmin data to data/garmin.json")
    parser.add_argument("--days", type=int, default=90, help="Number of days to fetch (default: 90)")
    args = parser.parse_args()

    end = date.today()
    start = end - timedelta(days=args.days - 1)

    print(f"Fetching {args.days} days of Garmin data ({start} → {end}) …")

    api = init_api()

    print("Fetching body composition …")
    weight = fetch_body_composition(api, start, end)

    print("Fetching daily stats and sleep …")
    daily = fetch_daily_stats(api, start, end)

    print("Fetching activities …")
    activities = fetch_activities(api, args.days)

    print("Fetching fitness age …")
    fitness_age = None
    try:
        fa = api.get_fitnessage_data(end.isoformat())
        fitness_age = fa.get("fitnessAge") or fa.get("fitnessage")
    except Exception as e:
        print(f"Warning: fitness age fetch failed: {e}", file=sys.stderr)

    payload = {
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "days": args.days,
        "fitness_age": fitness_age,
        "weight": sorted(weight, key=lambda r: r["date"]),
        "daily_stats": sorted(daily, key=lambda r: r["date"]),
        "activities": sorted(activities, key=lambda r: r["date"], reverse=True),
    }

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUTFILE}")
    print(f"  {len(weight)} body composition records")
    print(f"  {len(daily)} daily stat records")
    print(f"  {len(activities)} activities")


if __name__ == "__main__":
    main()
