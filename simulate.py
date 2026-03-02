#!/usr/bin/env python3
import json
import os
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class BinState:
    device_id: str
    fill_level_pct: int
    battery_pct: int
    temperature_c: float
    status: str

    def evolve(self) -> None:
        self.fill_level_pct = min(100, max(0, self.fill_level_pct + random.randint(-2, 5)))
        self.battery_pct = min(100, max(0, self.battery_pct - random.choice([0, 0, 1])))
        self.temperature_c = round(self.temperature_c + random.uniform(-0.4, 0.4), 1)

        if self.fill_level_pct >= 90:
            self.status = "full"
        elif self.fill_level_pct >= 75:
            self.status = "warning"
        else:
            self.status = "normal"


def build_payload(state: BinState) -> dict:
    payload = asdict(state)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    return payload


def make_mqtt_client() -> tuple[object, str]:
    import paho.mqtt.client as mqtt

    broker = os.getenv("MQTT_BROKER", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    topic = os.getenv("MQTT_TOPIC", "waste/bins/status")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if username:
        client.username_pw_set(username=username, password=password)

    client.connect(broker, port)
    client.loop_start()
    return client, topic


def main() -> None:
    random.seed(int(os.getenv("SIM_SEED", "42")))

    interval_s = float(os.getenv("PUBLISH_INTERVAL", "5"))
    dry_run = env_bool("DRY_RUN", False)

    state = BinState(
        device_id=os.getenv("DEVICE_ID", "bin-001"),
        fill_level_pct=int(os.getenv("INITIAL_FILL_PCT", "25")),
        battery_pct=int(os.getenv("INITIAL_BATTERY_PCT", "100")),
        temperature_c=float(os.getenv("INITIAL_TEMP_C", "20.0")),
        status="normal",
    )

    mqtt_client = None
    topic = ""
    if not dry_run:
        mqtt_client, topic = make_mqtt_client()

    while True:
        state.evolve()
        payload = build_payload(state)

        if dry_run:
            print(json.dumps(payload), flush=True)
        else:
            mqtt_client.publish(topic, json.dumps(payload), qos=1)

        time.sleep(interval_s)


if __name__ == "__main__":
    main()
