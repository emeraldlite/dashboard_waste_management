#!/usr/bin/env python3
"""Simulate smart-bin telemetry by publishing MQTT messages to ThingsBoard."""

from __future__ import annotations

import argparse
import json
import random
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt


@dataclass
class BinConfig:
    bin_id: str
    token: str


class BinPublisher:
    def __init__(
        self,
        config: BinConfig,
        host: str,
        port: int,
        use_tls: bool,
        telemetry_interval: float,
        rng: random.Random,
    ) -> None:
        self.config = config
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.telemetry_interval = telemetry_interval
        self.rng = rng

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"bin-sim-{config.bin_id}",
        )
        self.client.username_pw_set(username=config.token)

        if self.use_tls:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            self.client.tls_insecure_set(False)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        self._stop = threading.Event()
        self._connected = threading.Event()
        self._retry_delay = 1.0

    def on_connect(self, client: mqtt.Client, userdata: Any, flags: dict[str, Any], reason_code: mqtt.ReasonCode, properties: Any) -> None:
        if reason_code == mqtt.CONNACK_ACCEPTED:
            self._connected.set()
            self._retry_delay = 1.0
            print(f"[{self.config.bin_id}] Connected")
        else:
            self._connected.clear()
            print(f"[{self.config.bin_id}] Connect rejected: {reason_code}")

    def on_disconnect(self, client: mqtt.Client, userdata: Any, flags: dict[str, Any], reason_code: mqtt.ReasonCode, properties: Any) -> None:
        self._connected.clear()
        if self._stop.is_set():
            return
        print(f"[{self.config.bin_id}] Disconnected ({reason_code}). Starting reconnect loop...")
        self._reconnect_loop()

    def _connect(self) -> bool:
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[{self.config.bin_id}] Initial connect failed: {exc}")
            return False

    def _reconnect_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.client.reconnect()
                self._connected.set()
                self._retry_delay = 1.0
                print(f"[{self.config.bin_id}] Reconnected")
                return
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[{self.config.bin_id}] Reconnect failed ({exc}). "
                    f"Retrying in {self._retry_delay:.1f}s"
                )
                time.sleep(self._retry_delay)
                self._retry_delay = min(self._retry_delay * 2, 30.0)

    def _build_telemetry(self) -> dict[str, Any]:
        fill_level = self.rng.randint(0, 100)
        temperature_c = round(self.rng.uniform(12, 37), 1)
        battery = self.rng.randint(35, 100)
        return {
            "binId": self.config.bin_id,
            "fillLevel": fill_level,
            "temperature": temperature_c,
            "battery": battery,
        }

    def run(self) -> None:
        if not self._connect():
            self._reconnect_loop()

        self.client.loop_start()
        while not self._stop.is_set():
            if not self._connected.wait(timeout=1.0):
                continue

            payload = self._build_telemetry()
            try:
                info = self.client.publish("v1/devices/me/telemetry", json.dumps(payload), qos=1)
                info.wait_for_publish(timeout=10)
                if info.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise RuntimeError(f"MQTT publish rc={info.rc}")
                print(f"[{self.config.bin_id}] Telemetry -> {payload}")
            except Exception as exc:  # noqa: BLE001
                print(f"[{self.config.bin_id}] Publish failed: {exc}")

            time.sleep(self.telemetry_interval)

        self.client.loop_stop()
        self.client.disconnect()

    def stop(self) -> None:
        self._stop.set()


def parse_bins(raw_bins: list[str]) -> list[BinConfig]:
    bins: list[BinConfig] = []
    for item in raw_bins:
        if ":" not in item:
            raise ValueError(f"Invalid --bin format '{item}'. Expected BIN_ID:TOKEN")
        bin_id, token = item.split(":", 1)
        if not bin_id or not token:
            raise ValueError(f"Invalid --bin format '{item}'. Expected BIN_ID:TOKEN")
        bins.append(BinConfig(bin_id=bin_id, token=token))

    if not bins:
        raise ValueError("At least one --bin BIN_ID:TOKEN must be provided")
    return bins


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ThingsBoard MQTT bin simulator")
    parser.add_argument(
        "--bin",
        action="append",
        required=True,
        metavar="BIN_ID:TOKEN",
        help="Bin identifier and ThingsBoard device token. Repeat for multiple bins.",
    )
    parser.add_argument("--interval", type=float, default=5.0, help="Telemetry interval in seconds (default: 5.0)")
    parser.add_argument("--tls", action="store_true", help="Use TLS for MQTT (default disabled)")
    parser.add_argument("--host", default="mqtt.thingsboard.cloud", help="MQTT host (default: mqtt.thingsboard.cloud)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port (default: 1883)")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible telemetry")
    parser.add_argument(
        "--mode",
        choices=["per-bin", "single"],
        default="per-bin",
        help="Connection mode. 'single' is unavailable for ThingsBoard Cloud without gateway setup.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "single":
        print(
            "Single-connection gateway style publishing is not compatible with ThingsBoard Cloud "
            "without gateway provisioning. Use --mode per-bin."
        )
        return 2

    bins = parse_bins(args.bin)

    base_rng = random.Random(args.seed)
    publishers: list[BinPublisher] = []
    threads: list[threading.Thread] = []

    for config in bins:
        publisher = BinPublisher(
            config=config,
            host=args.host,
            port=args.port,
            use_tls=args.tls,
            telemetry_interval=args.interval,
            rng=random.Random(base_rng.randint(0, 2**31 - 1)),
        )
        publishers.append(publisher)
        thread = threading.Thread(target=publisher.run, daemon=True, name=f"publisher-{config.bin_id}")
        threads.append(thread)
        thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping publishers...")
        for publisher in publishers:
            publisher.stop()

        for thread in threads:
            thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
