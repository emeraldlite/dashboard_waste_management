#!/usr/bin/env python3
"""ThingsBoard Cloud bin telemetry simulator."""

from __future__ import annotations

import json
import os
import random
import signal
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

TELEMETRY_TOPIC = "v1/devices/me/telemetry"
STATUS_CODES = {"safe": 0, "caution": 1, "warning": 2, "full": 3}


@dataclass
class BinState:
    foodcourt: str
    bin_id: str
    waste_type: str
    waste_type_code: int
    access_token: str
    level_pct: float
    weight_kg: float
    battery_v: float
    rssi_dbm: int
    total_empties: int = 0


def env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_bins(path: Path) -> list[BinState]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Copy bins.example.json to bins.json and set each access_token."
        )

    with path.open("r", encoding="utf-8") as fp:
        raw_bins = json.load(fp)

    bins: list[BinState] = []
    for item in raw_bins:
        required = {"foodcourt", "bin_id", "waste_type", "waste_type_code", "access_token"}
        missing = required - set(item)
        if missing:
            raise ValueError(f"Bin entry missing keys {sorted(missing)}: {item}")

        token = str(item["access_token"]).strip()
        if not token or token.startswith("REPLACE_WITH_TOKEN"):
            raise ValueError(
                f"Bin {item['bin_id']} has a placeholder token. Update bins.json with real access tokens."
            )

        bins.append(
            BinState(
                foodcourt=str(item["foodcourt"]),
                bin_id=str(item["bin_id"]),
                waste_type=str(item["waste_type"]),
                waste_type_code=int(item["waste_type_code"]),
                access_token=token,
                level_pct=random.uniform(15, 75),
                weight_kg=random.uniform(1.5, 6.5),
                battery_v=random.uniform(3.65, 4.15),
                rssi_dbm=random.randint(-88, -58),
            )
        )

    return bins


def derive_status(level_pct: float, weight_kg: float) -> tuple[str, int]:
    if level_pct >= 90:
        status = "full"
    elif level_pct >= 80 or weight_kg >= 8:
        status = "warning"
    elif level_pct >= 60:
        status = "caution"
    else:
        status = "safe"

    return status, STATUS_CODES[status]


def evolve_bin_reading(state: BinState) -> tuple[dict[str, Any], bool]:
    emptied = False

    if state.level_pct >= 95 or state.weight_kg >= 9.5:
        if random.random() < 0.35:
            state.level_pct = random.uniform(4, 18)
            state.weight_kg = random.uniform(0.3, 1.4)
            state.total_empties += 1
            emptied = True
        else:
            state.level_pct = min(100.0, state.level_pct + random.uniform(0.5, 2.0))
            state.weight_kg = min(12.0, state.weight_kg + random.uniform(0.1, 0.4))
    else:
        state.level_pct = min(100.0, state.level_pct + random.uniform(0.8, 5.0))
        state.weight_kg = min(12.0, state.weight_kg + random.uniform(0.05, 0.5))

    state.battery_v = max(3.3, state.battery_v - random.uniform(0.0004, 0.0040))
    state.rssi_dbm = max(-110, min(-45, state.rssi_dbm + random.randint(-2, 2)))

    status, status_code = derive_status(state.level_pct, state.weight_kg)

    payload = {
        "ts": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        "values": {
            "foodcourt": state.foodcourt,
            "bin_id": state.bin_id,
            "waste_type": state.waste_type,
            "waste_type_code": state.waste_type_code,
            "weight_kg": round(state.weight_kg, 2),
            "level_pct": round(state.level_pct, 1),
            "status": status,
            "status_code": status_code,
            "battery_v": round(state.battery_v, 3),
            "rssi_dbm": state.rssi_dbm,
        },
    }

    return payload, emptied


def build_client(bin_state: BinState, host: str, port: int, use_tls: bool) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"tb-sim-{bin_state.bin_id}-{random.randint(1000, 9999)}",
        clean_session=True,
    )
    client.username_pw_set(bin_state.access_token)

    def on_connect(
        _client: mqtt.Client,
        _userdata: Any,
        _flags: dict[str, Any],
        reason_code: int,
        _properties: Any,
    ) -> None:
        if reason_code == 0:
            print(f"[connect] {bin_state.bin_id} connected")
        else:
            print(f"[connect] {bin_state.bin_id} failed rc={reason_code}")

    def on_disconnect(
        _client: mqtt.Client,
        _userdata: Any,
        _disconnect_flags: Any,
        reason_code: int,
        _properties: Any,
    ) -> None:
        if reason_code != 0:
            print(f"[disconnect] {bin_state.bin_id} unexpected rc={reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    if use_tls:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)

    client.connect(host, port, keepalive=60)
    client.loop_start()
    return client


def main() -> int:
    load_dotenv()

    host = os.getenv("TB_HOST", "demo.thingsboard.io").strip()
    port = int(os.getenv("TB_PORT", "1883"))
    use_tls = env_bool("TB_USE_TLS", False)
    interval_s = float(os.getenv("PUBLISH_INTERVAL_SEC", "5"))

    bins = load_bins(Path("bins.json"))
    clients: dict[str, mqtt.Client] = {}

    print(
        f"Starting ThingsBoard simulation for {len(bins)} bins -> {host}:{port} "
        f"(tls={'on' if use_tls else 'off'}, interval={interval_s}s)"
    )

    should_stop = False

    def stop_handler(_signum: int, _frame: Any) -> None:
        nonlocal should_stop
        should_stop = True
        print("\nStopping simulator...")

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    try:
        for state in bins:
            clients[state.bin_id] = build_client(state, host, port, use_tls)

        while not should_stop:
            for state in bins:
                payload, emptied = evolve_bin_reading(state)
                client = clients[state.bin_id]
                result = client.publish(TELEMETRY_TOPIC, json.dumps(payload), qos=1)

                status = payload["values"]["status"]
                status_code = payload["values"]["status_code"]
                level = payload["values"]["level_pct"]
                weight = payload["values"]["weight_kg"]
                batt = payload["values"]["battery_v"]
                rssi = payload["values"]["rssi_dbm"]
                marker = "EMPTIED" if emptied else "-"
                delivery = "ok" if result.rc == mqtt.MQTT_ERR_SUCCESS else f"rc={result.rc}"

                print(
                    f"{state.bin_id} [{state.foodcourt}] lvl={level:>5.1f}% wt={weight:>4.1f}kg "
                    f"st={status:<7}({status_code}) batt={batt:.3f}V rssi={rssi:>4} "
                    f"event={marker:<7} pub={delivery}"
                )

            time.sleep(interval_s)

    finally:
        for client in clients.values():
            client.loop_stop()
            client.disconnect()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Fatal error: {exc}", file=sys.stderr)
        raise
