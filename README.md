# Dashboard Waste Management Simulator

`simulate.py` publishes mock telemetry for waste bins to ThingsBoard Cloud via MQTT.

## Requirements

- Python 3.9+
- `paho-mqtt`

```bash
pip install paho-mqtt
```

## Usage

Default behavior is **one MQTT client per bin** (required for direct device-token auth in ThingsBoard Cloud).

```bash
python simulate.py \
  --bin bin-001:DEVICE_TOKEN_1 \
  --bin bin-002:DEVICE_TOKEN_2
```

### CLI flags

- `--bin BIN_ID:TOKEN` (repeatable, required): bin id + ThingsBoard device token.
- `--interval FLOAT`: seconds between telemetry publishes per bin (default `5.0`).
- `--tls`: enable TLS.
- `--host HOST`: MQTT host (default `mqtt.thingsboard.cloud`).
- `--port INT`: MQTT port (default `1883`).
- `--seed INT`: deterministic seed for reproducible telemetry values.
- `--mode {per-bin,single}`: connection mode. `single` exits with an error because gateway-style multi-device publish requires ThingsBoard gateway provisioning and is not compatible with plain ThingsBoard Cloud device-token setup.

### TLS example

```bash
python simulate.py \
  --bin bin-001:DEVICE_TOKEN_1 \
  --tls \
  --host mqtt.thingsboard.cloud \
  --port 8883
```

## Reliability behavior

- Each bin runs independently in its own MQTT client thread.
- `on_disconnect` triggers reconnect attempts with exponential backoff (1s to 30s).
- Publish failures for one bin do not stop telemetry publishing for other bins.
