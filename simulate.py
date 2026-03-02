#!/usr/bin/env python3
"""Waste-bin telemetry simulator with optional demo scenarios.

Environment variables:
- SEED: optional integer for deterministic output.
- DEMO_SCENARIO: one of normal, stale_one_bin, overflow_wave, organic_shift.
- PUBLISH_INTERVAL_SEC: publish cadence per bin (default: 5).
- MAX_TICKS: optional integer to stop after N ticks (useful for demos/tests).
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

WASTE_TYPES = ["organic", "plastic", "paper", "mixed"]
SCENARIOS = {"normal", "stale_one_bin", "overflow_wave", "organic_shift"}


@dataclass
class BinState:
    bin_id: str
    foodcourt: str
    level: float


def _parse_int(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from exc


def _setup_bins(rng: random.Random) -> List[BinState]:
    bins: List[BinState] = []
    for prefix, foodcourt in (("A", "Foodcourt A"), ("B", "Foodcourt B")):
        for idx in range(1, 6):
            bins.append(
                BinState(
                    bin_id=f"{prefix}-{idx:02d}",
                    foodcourt=foodcourt,
                    level=rng.uniform(20.0, 55.0),
                )
            )
    return bins


def _scenario_waste_weights(scenario: str, bin_state: BinState) -> Tuple[float, float, float, float]:
    if scenario != "organic_shift":
        return (0.35, 0.25, 0.2, 0.2)

    if bin_state.foodcourt == "Foodcourt A":
        return (0.72, 0.12, 0.1, 0.06)
    return (0.08, 0.34, 0.3, 0.28)


def _apply_base_level_drift(rng: random.Random, level: float) -> float:
    drift = rng.uniform(-1.8, 4.8)
    return max(0.0, min(100.0, level + drift))


def _apply_overflow_wave(level: float, tick: int, bin_state: BinState) -> float:
    # A bins rise first, then B bins. Ramp is deterministic and based on tick count.
    start_tick = 0 if bin_state.bin_id.startswith("A-") else 12
    if tick < start_tick:
        return level
    progress = tick - start_tick
    if level < 90.0:
        # Gradual rise toward overflow region.
        level = min(95.0, level + 2.6 + (0.25 * min(progress, 10)))
    return level


def _should_publish(scenario: str, bin_state: BinState, elapsed_seconds: int) -> bool:
    if scenario != "stale_one_bin":
        return True

    if bin_state.bin_id != "B-03":
        return True

    stale_start = 60
    stale_end = stale_start + 300
    return not (stale_start <= elapsed_seconds < stale_end)


def _build_payload(
    rng: random.Random,
    scenario: str,
    tick: int,
    elapsed_seconds: int,
    now: datetime,
    bin_state: BinState,
) -> Dict[str, object]:
    bin_state.level = _apply_base_level_drift(rng, bin_state.level)
    if scenario == "overflow_wave":
        bin_state.level = _apply_overflow_wave(bin_state.level, tick, bin_state)

    weights = _scenario_waste_weights(scenario, bin_state)
    waste_type = rng.choices(WASTE_TYPES, weights=weights, k=1)[0]

    return {
        "timestamp": now.isoformat(),
        "bin_id": bin_state.bin_id,
        "foodcourt": bin_state.foodcourt,
        "level": round(bin_state.level, 2),
        "waste_type": waste_type,
    }


def main() -> None:
    seed = _parse_int("SEED", None)
    rng = random.Random(seed)

    scenario = os.getenv("DEMO_SCENARIO", "normal").strip().lower() or "normal"
    if scenario not in SCENARIOS:
        valid = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unsupported DEMO_SCENARIO={scenario!r}. Expected one of: {valid}")

    interval_sec = _parse_int("PUBLISH_INTERVAL_SEC", 5)
    if interval_sec is None or interval_sec <= 0:
        raise ValueError("PUBLISH_INTERVAL_SEC must be > 0")

    max_ticks = _parse_int("MAX_TICKS", None)
    if max_ticks is not None and max_ticks <= 0:
        raise ValueError("MAX_TICKS must be > 0 when set")

    sleep_enabled = os.getenv("SLEEP_ENABLED", "1").strip().lower() not in {"0", "false", "no"}

    bins = _setup_bins(rng)
    start = datetime(2024, 1, 1, tzinfo=timezone.utc) if seed is not None else datetime.now(tz=timezone.utc)

    tick = 0
    while True:
        now = start + timedelta(seconds=tick * interval_sec)
        elapsed_seconds = tick * interval_sec

        for bin_state in bins:
            if not _should_publish(scenario, bin_state, elapsed_seconds):
                continue
            payload = _build_payload(rng, scenario, tick, elapsed_seconds, now, bin_state)
            print(json.dumps(payload), flush=True)

        tick += 1
        if max_ticks is not None and tick >= max_ticks:
            break

        if sleep_enabled:
            time.sleep(interval_sec)


if __name__ == "__main__":
    main()
