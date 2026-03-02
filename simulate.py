#!/usr/bin/env python3
"""Waste-bin telemetry simulator.

Loads bin definitions from ``bins.json`` and publishes evolving fill-level payloads.
Supports a mock mode for local testing without MQTT credentials.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

LOGGER = logging.getLogger("simulator")


@dataclass(frozen=True)
class BinConfig:
    """Static configuration for a waste bin."""

    bin_id: str
    latitude: float
    longitude: float
    capacity_liters: float
    fill_start_pct: float = 0.0
    growth_per_tick_pct: float = 1.0


@dataclass
class BinState:
    """Mutable simulation state for a waste bin."""

    config: BinConfig
    fill_pct: float
    battery_pct: float = 100.0


@dataclass(frozen=True)
class AppConfig:
    broker_host: str
    broker_port: int
    mqtt_username: Optional[str]
    mqtt_password: Optional[str]
    topic_prefix: str
    interval_seconds: float
    iterations: int
    bins_path: Path
    mock_mode: bool


class Publisher:
    """Publisher abstraction so we can swap mock/real clients."""

    def publish(self, topic: str, payload: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MockPublisher(Publisher):
    def publish(self, topic: str, payload: str) -> None:
        LOGGER.info("[mock] topic=%s payload=%s", topic, payload)


class MqttPublisher(Publisher):
    def __init__(self, host: str, port: int, username: Optional[str], password: Optional[str]) -> None:
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime environment specific
            raise RuntimeError(
                "paho-mqtt is required for non-mock mode. Install with: pip install paho-mqtt"
            ) from exc

        self._mqtt = mqtt
        self._client = mqtt.Client()
        if username:
            self._client.username_pw_set(username=username, password=password)

        LOGGER.info("Connecting to MQTT broker %s:%s", host, port)
        rc = self._client.connect(host, port, keepalive=60)
        if rc != 0:
            raise RuntimeError(f"Failed to connect to MQTT broker (result code={rc})")
        self._client.loop_start()

    def publish(self, topic: str, payload: str) -> None:
        result = self._client.publish(topic, payload=payload)
        if result.rc != 0:
            LOGGER.warning(
                "Publish failed with rc=%s for topic=%s; attempting reconnect",
                result.rc,
                topic,
            )
            self._client.reconnect()
            retry = self._client.publish(topic, payload=payload)
            if retry.rc != 0:
                raise RuntimeError(f"Publish failed after reconnect with rc={retry.rc}")


def _load_dotenv(env_path: Path = Path(".env")) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values

    for idx, raw_line in enumerate(env_path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env line {idx}: expected KEY=VALUE format")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _require_number(value: Any, *, name: str, bin_id: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"Bin '{bin_id}' field '{name}' must be a number, got {type(value).__name__}")
    return float(value)


def _validate_bins_content(raw: Any) -> List[BinConfig]:
    bins_raw: Iterable[Mapping[str, Any]]
    if isinstance(raw, list):
        bins_raw = raw
    elif isinstance(raw, dict) and isinstance(raw.get("bins"), list):
        bins_raw = raw["bins"]
    else:
        raise ValueError("bins.json must be a JSON array or an object with a 'bins' array")

    bins: List[BinConfig] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(bins_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entry #{idx} in bins.json must be an object")

        try:
            bin_id = str(item["id"])
            lat = _require_number(item["latitude"], name="latitude", bin_id=bin_id)
            lon = _require_number(item["longitude"], name="longitude", bin_id=bin_id)
            cap = _require_number(item["capacity_liters"], name="capacity_liters", bin_id=bin_id)
            fill_start = _require_number(item.get("fill_start_pct", 0.0), name="fill_start_pct", bin_id=bin_id)
            growth = _require_number(item.get("growth_per_tick_pct", 1.0), name="growth_per_tick_pct", bin_id=bin_id)
        except KeyError as exc:
            raise ValueError(f"Entry #{idx} missing required field: {exc.args[0]}") from exc

        if not bin_id:
            raise ValueError(f"Entry #{idx} has empty 'id'")
        if bin_id in seen_ids:
            raise ValueError(f"Duplicate bin id found: '{bin_id}'")
        seen_ids.add(bin_id)

        if not 0 <= fill_start <= 100:
            raise ValueError(f"Bin '{bin_id}' fill_start_pct must be between 0 and 100")
        if growth < 0:
            raise ValueError(f"Bin '{bin_id}' growth_per_tick_pct must be >= 0")

        bins.append(
            BinConfig(
                bin_id=bin_id,
                latitude=lat,
                longitude=lon,
                capacity_liters=cap,
                fill_start_pct=fill_start,
                growth_per_tick_pct=growth,
            )
        )

    if not bins:
        raise ValueError("bins.json does not contain any bins")
    return bins


def load_config(args: argparse.Namespace) -> tuple[AppConfig, List[BinState]]:
    env = _load_dotenv()

    bins_path = Path(args.bins_file)
    if not bins_path.exists():
        raise FileNotFoundError(
            f"Could not find bins file at '{bins_path}'. Create bins.json with an array of bin objects."
        )

    try:
        raw = json.loads(bins_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {bins_path}: {exc}") from exc

    bin_configs = _validate_bins_content(raw)
    states = [BinState(config=b, fill_pct=b.fill_start_pct) for b in bin_configs]

    cfg = AppConfig(
        broker_host=args.broker_host or env.get("BROKER_HOST", "localhost"),
        broker_port=int(args.broker_port or env.get("BROKER_PORT", 1883)),
        mqtt_username=args.username or env.get("MQTT_USERNAME"),
        mqtt_password=args.password or env.get("MQTT_PASSWORD"),
        topic_prefix=args.topic_prefix or env.get("TOPIC_PREFIX", "waste/bins"),
        interval_seconds=float(args.interval),
        iterations=int(args.iterations),
        bins_path=bins_path,
        mock_mode=bool(args.mock),
    )
    return cfg, states


def connect_clients(config: AppConfig) -> Publisher:
    if config.mock_mode:
        LOGGER.info("Using mock publisher")
        return MockPublisher()
    return MqttPublisher(
        host=config.broker_host,
        port=config.broker_port,
        username=config.mqtt_username,
        password=config.mqtt_password,
    )


def evolve_state(state: BinState) -> BinState:
    growth = random.uniform(0.4, 1.2) * state.config.growth_per_tick_pct
    next_fill = min(100.0, state.fill_pct + growth)
    next_battery = max(0.0, state.battery_pct - random.uniform(0.01, 0.05))

    if next_fill >= 100.0:
        next_fill = random.uniform(4.0, 12.0)

    return BinState(config=state.config, fill_pct=round(next_fill, 2), battery_pct=round(next_battery, 2))


def make_payload(state: BinState) -> Dict[str, Any]:
    return {
        "bin_id": state.config.bin_id,
        "timestamp": int(time.time()),
        "location": {"lat": state.config.latitude, "lon": state.config.longitude},
        "capacity_liters": state.config.capacity_liters,
        "fill_pct": state.fill_pct,
        "battery_pct": state.battery_pct,
    }


def publish_loop(config: AppConfig, states: List[BinState], publisher: Publisher) -> None:
    for tick in range(config.iterations):
        updated: List[BinState] = []
        for state in states:
            next_state = evolve_state(state)
            payload = make_payload(next_state)
            topic = f"{config.topic_prefix}/{next_state.config.bin_id}"
            publisher.publish(topic, json.dumps(payload))
            updated.append(next_state)

        avg_fill = sum(s.fill_pct for s in updated) / len(updated)
        LOGGER.info(
            "Published tick=%s bins=%s avg_fill=%.2f%%",
            tick + 1,
            len(updated),
            avg_fill,
        )

        states[:] = updated
        if tick < config.iterations - 1:
            time.sleep(config.interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Waste bin telemetry simulator")
    parser.add_argument("--bins-file", default="bins.json", help="Path to bins configuration JSON")
    parser.add_argument("--broker-host", default=None, help="MQTT broker host")
    parser.add_argument("--broker-port", type=int, default=None, help="MQTT broker port")
    parser.add_argument("--username", default=None, help="MQTT username")
    parser.add_argument("--password", default=None, help="MQTT password")
    parser.add_argument("--topic-prefix", default=None, help="MQTT topic prefix")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between publish ticks")
    parser.add_argument("--iterations", type=int, default=10, help="Number of publish ticks")
    parser.add_argument("--mock", action="store_true", help="Use mock publisher (no MQTT connection)")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ...)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    config, states = load_config(args)
    publisher = connect_clients(config)
    publish_loop(config, states, publisher)


if __name__ == "__main__":
    main()
