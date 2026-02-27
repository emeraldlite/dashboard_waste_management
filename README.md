# ThingsBoard Cloud Bin Monitoring POC (Python)

This repository contains a lightweight Python simulator that publishes smart-bin telemetry to **ThingsBoard Cloud** over MQTT.

It simulates 10 bins across two foodcourts:
- Foodcourt A: `A-01` .. `A-05`
- Foodcourt B: `B-01` .. `B-05`

Each bin uses its **own device access token** (MQTT username) and sends telemetry to:
- Topic: `v1/devices/me/telemetry`
- QoS: `1`

---

## 1) Setup

### Prerequisites
- Python 3.10+
- A ThingsBoard Cloud tenant/account

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment

Copy the sample env file and adjust values if needed:

```bash
cp .env.example .env
```

Environment fields:
- `TB_HOST`: ThingsBoard host (e.g. `demo.thingsboard.io` or your cloud endpoint)
- `TB_PORT`: MQTT port (`1883` non-TLS, typically `8883` TLS)
- `TB_USE_TLS`: `true`/`false`
- `PUBLISH_INTERVAL_SEC`: publish interval in seconds

---

## 2) Create devices in ThingsBoard Cloud and collect tokens

For each simulated bin (`A-01`..`A-05`, `B-01`..`B-05`):

1. Open **Devices** in ThingsBoard Cloud.
2. Click **+ Add new device**.
3. Set device name to the bin ID (e.g. `A-01`).
4. Save device.
5. Open device details → **Credentials**.
6. Ensure credential type is **Access token**.
7. Copy the token.

Repeat until all 10 devices are created.

---

## 3) Paste tokens into local config (kept out of git)

1. Copy example bins file:

```bash
cp bins.example.json bins.json
```

2. Edit `bins.json` and replace every `REPLACE_WITH_TOKEN_...` with the real token from ThingsBoard.

`bins.json` is ignored by git on purpose so secrets stay local.

---

## 4) Run the simulator

```bash
python simulate.py
```

You should see compact per-bin logs like:

```text
A-01 [Foodcourt A] lvl= 62.4% wt= 5.6kg st=caution (1) batt=3.952V rssi= -67 event=-       pub=ok
```

Press `Ctrl+C` to stop.

---

## 5) Telemetry schema sent per publish

Each message sends:
- `foodcourt`
- `bin_id`
- `waste_type`
- `waste_type_code`
- `weight_kg`
- `level_pct`
- `status`
- `status_code`
- `battery_v`
- `rssi_dbm`

Status is derived with these thresholds:
- `level_pct >= 90` → `full`
- `level_pct >= 80` **or** `weight_kg >= 8` → `warning`
- `level_pct >= 60` → `caution`
- else `safe`

Simulator behavior also includes periodic **emptied events** when a bin is near full, resetting level/weight and printing `event=EMPTIED` in the console.

---

## 6) Suggested dashboard design (ThingsBoard)

### Recommended widgets
Use a dashboard with 3 sections:

1. **KPI row**
   - Count of bins by status (`safe`, `caution`, `warning`, `full`)
   - Avg fill level by foodcourt
   - Bins emptied today (if you also add rule-chain/event tracking)

2. **Operational table**
   - Latest values table with columns:
     - Bin ID, Foodcourt
     - Level %, Weight kg
     - Status / Status code
     - Battery V, RSSI dBm
   - Add row color rules by `status_code`.

3. **Trend + map/floor area**
   - Time-series chart of `level_pct` and `weight_kg` by selected bin
   - Optional floorplan image cards grouped by foodcourt

### Entity aliases approach
Create aliases to make widgets reusable:

- **Alias: All bins**
  - Filter by device type/tag for this POC (e.g., type `smart_bin` if you define one)
- **Alias: Foodcourt A bins**
  - Name filter: `A-*`
- **Alias: Foodcourt B bins**
  - Name filter: `B-*`
- **Alias: Single selected bin**
  - Current entity (for drill-down timeseries widgets)

With aliases, one widget template can be reused for each scope without hardcoding device IDs.

---

## Security notes

- Never commit `.env` or `bins.json`.
- Rotate any token immediately if it is leaked.
- Prefer TLS (`TB_USE_TLS=true`, MQTT port `8883`) for non-local testing.
