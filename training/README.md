# Training

A 3-month (13-week) adaptive training system. Goals, in priority order:

1. **Lose body fat** — from ~23% toward 16% (≈ 87 kg → ~80 kg at current lean mass).
2. **Improve endurance & cardiovascular health** — build the aerobic base, raise VO2max / lactate threshold.
3. **Improve strength** — maintain and modestly build, focused on **squat, deadlift, bench**.

The plan is built to survive real life: work travel, no-gym days, and days where nothing
happens. Missed sessions are expected, not failures — see the adaptation rules.

## The files

| File | What it is |
|------|-----------|
| [`plan.md`](plan.md) | The 13-week block plan, weekly template, and benchmarks. Start here. |
| [`principles.md`](principles.md) | HR zones, RPE, nutrition targets, autoregulation, and the travel tiers (A/B/C). The "rules of the game." |
| [`strength.md`](strength.md) | The lifting program (Day A / Day B), progression scheme, and your working-weight log. |
| [`templates/week.md`](templates/week.md) | Copyable weekly log template. |
| [`logs/`](logs/) | One file per week (`YYYY-Www.md`): planned vs. actual, notes, and a Garmin summary. |

## How a week works

1. **Monday:** copy [`templates/week.md`](templates/week.md) to `logs/<iso-week>.md` (or run the
   helper script below to seed it with the plan + any activities already logged).
2. **During the week:** log what you actually did — sets/weights/reps for lifts, and let
   Garmin capture the runs. Jot notes on energy, sleep, niggles.
3. **Sunday:** 2-minute review. Did you hit the essentials (see priority order in `principles.md`)?
   Update working weights in `strength.md` if you progressed. Note anything to adjust next week.

## Updating from Garmin

Runs, resting HR, sleep, weight, and body-fat trend all come from the watch + smart scale and
already land in [`../data/garmin.json`](../data/garmin.json) via `scripts/garmin_sync.py`.

To pull a given week's **actual activities** into its log file:

```sh
./scripts/garmin_sync.py            # refresh data/garmin.json first (optional)
./scripts/training_log.py           # current ISO week
./scripts/training_log.py --week 2026-W29
```

Garmin only sees the runs (and any activity you record on the watch). **Strength and climbing
are logged by hand** in the week file — or just tell me in a session what you did and I'll write
it up.

## Two ways to keep it current

- **Automatic:** `training_log.py` fills the run rows from Garmin; you add lifts/climbs by hand.
- **Conversational:** in a future session, tell me what you did ("did Day A, squat 100×5×3,
  ran 8k easy") and I'll update the log and adjust working weights / next week's plan.

## A note

I'm not a doctor or a certified coach — this is a well-structured amateur plan built from your
data. If something hurts (not "hard", *hurts*), back off and get it looked at. Re-check the fat-loss
approach against how you actually feel and perform, not just the scale.
