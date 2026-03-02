# Dashboard Waste Management Simulator

This repository contains a lightweight telemetry simulator for waste bins.

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

- `SEED`: Set an integer for deterministic behavior.
- `DEMO_SCENARIO`: Scenario profile for demo behavior (default: `normal`).
- `PUBLISH_INTERVAL_SEC`: Seconds between publish cycles.
- `SLEEP_ENABLED`: Set to `0`/`false` to run ticks without real-time sleeping (handy for tests).

## Demo scenarios

`DEMO_SCENARIO` accepts the following values:

- `normal`:
  - Baseline behavior with modest random level drift and balanced-ish waste type distribution.

- `stale_one_bin`:
  - Bin `B-03` pauses publishing for 5 minutes, then resumes.
  - Other bins continue publishing as normal.

- `overflow_wave`:
  - Bin levels rise in a controlled wave to overflow range (`>= 90`).
  - Group `A-*` bins rise first, followed by `B-*` bins.

- `organic_shift`:
  - `Foodcourt A` strongly favors `organic` waste type.
  - `Foodcourt B` is biased toward non-organic categories.

## Run

```bash
python simulate.py
```

For quick checks without waiting, you can override interval and tick count:

```bash
SEED=42 DEMO_SCENARIO=overflow_wave PUBLISH_INTERVAL_SEC=1 MAX_TICKS=20 SLEEP_ENABLED=0 python simulate.py
```
