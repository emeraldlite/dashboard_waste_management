# Waste Dashboard Simulator

`simulate.py` generates synthetic bin telemetry and publishes it at a fixed interval.

## Environment variables

- `MQTT_BROKER` (default: `localhost`)
- `MQTT_PORT` (default: `1883`)
- `MQTT_TOPIC` (default: `waste/bins/status`)
- `MQTT_USERNAME` / `MQTT_PASSWORD` (optional)
- `PUBLISH_INTERVAL` in seconds (default: `5`)
- `DEVICE_ID` (default: `bin-001`)
- `SIM_SEED` (default: `42`)
- `DRY_RUN` (default: `false`)

## Run with MQTT

```bash
python simulate.py
```

## DRY_RUN mode (no MQTT connection)

Set `DRY_RUN=true` to avoid connecting to MQTT and print payloads to stdout at each publish interval.

```bash
DRY_RUN=true PUBLISH_INTERVAL=1 python simulate.py
```

This is useful for validating payload shape and evolution/status behavior locally without broker credentials or tokens.
