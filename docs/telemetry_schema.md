# Telemetry Schema

## MQTT Topic (ThingsBoard)
- `v1/devices/me/telemetry`

## JSON Payload Keys

| Key | Type | Unit | Notes |
| --- | --- | --- | --- |
| `foodcourt` | string | n/a | Site or zone identifier (e.g., `fc-a`) |
| `bin_id` | string | n/a | Unique bin identifier (e.g., `bin-01`) |
| `fill_level_pct` | number | % | 0-100 fill percentage |
| `distance_cm` | number | cm | Sensor distance from lid to trash surface |
| `temperature_c` | number | °C | Optional environmental reading |
| `battery_pct` | number | % | Optional battery level |
| `status` | string | n/a | Derived lifecycle state |
| `timestamp` | string | ISO-8601 | Event timestamp |

> Keep payload minimal when quotas are tight; `fill_level_pct`, `status`, `bin_id`, and `timestamp` are the critical fields.

## Status Derivation Rules
- `normal`: `fill_level_pct < 70`
- `warning`: `70 <= fill_level_pct < 90`
- `full`: `fill_level_pct >= 90`
- `emptied`: transition event when the previous reading is `>= 70` and current reading drops to `<= 20`

Suggested transition handling:
- Publish `status` every sample.
- Emit an `emptied` status once on reset, then resume `normal`/`warning`/`full` on subsequent samples.

## Suggested Sampling Strategy
- **Demo mode:** every `5s` for responsive dashboards.
- **Low-quota mode:** every `30-60s`.
- **Event-driven overrides:** publish immediately when:
  - status changes (`normal` -> `warning` -> `full`)
  - `emptied` is detected
  - battery crosses low threshold (e.g., `<20%`)

## Future AWS IoT Core Topic Mapping
- Suggested topic pattern:
  - `waste/{foodcourt}/{bin_id}/telemetry`
- Example resolved topic:
  - `waste/fc-a/bin-01/telemetry`

Notes for migration:
- Keep payload keys identical to minimize downstream parser changes.
- Add metadata in topic path (foodcourt/bin) while preserving JSON body for analytics.

## Example Payloads

### 1) Normal
```json
{
  "foodcourt": "fc-a",
  "bin_id": "bin-01",
  "fill_level_pct": 42,
  "distance_cm": 36.5,
  "temperature_c": 29.1,
  "battery_pct": 88,
  "status": "normal",
  "timestamp": "2026-02-27T10:15:00Z"
}
```

### 2) Warning
```json
{
  "foodcourt": "fc-a",
  "bin_id": "bin-01",
  "fill_level_pct": 78,
  "distance_cm": 18.2,
  "temperature_c": 30.0,
  "battery_pct": 86,
  "status": "warning",
  "timestamp": "2026-02-27T10:20:00Z"
}
```

### 3) Full
```json
{
  "foodcourt": "fc-a",
  "bin_id": "bin-01",
  "fill_level_pct": 95,
  "distance_cm": 7.1,
  "temperature_c": 30.4,
  "battery_pct": 85,
  "status": "full",
  "timestamp": "2026-02-27T10:25:00Z"
}
```

### 4) Emptied
```json
{
  "foodcourt": "fc-a",
  "bin_id": "bin-01",
  "fill_level_pct": 12,
  "distance_cm": 49.0,
  "temperature_c": 29.7,
  "battery_pct": 85,
  "status": "emptied",
  "timestamp": "2026-02-27T10:32:00Z"
}
```
