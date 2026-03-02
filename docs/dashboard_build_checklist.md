# Dashboard Build Checklist

## 1) Create 10 devices
- Use a predictable naming pattern: `BIN-01` … `BIN-10` (or `FC-A-01` … `FC-B-05`).
- Add each device in the platform and confirm it appears as **online**.
- Generate and store a unique access token per device in a shared tracker.
- Keep token notes operational: device name, token created date, owner, and last rotation date.
- Validate telemetry from all 10 devices before building widgets.

## 2) Entity aliases strategy
Create aliases so widgets are easy to reuse:
- **All bins**: include all 10 devices/entities.
- **Foodcourt A bins**: include only Foodcourt A devices.
- **Foodcourt B bins**: include only Foodcourt B devices.

Tip: keep alias names stable (`all_bins`, `foodcourt_a_bins`, `foodcourt_b_bins`) so future dashboard clones need no edits.

## 3) Recommended widgets
- **Entities table** (primary operational view)
  - Columns: `status`, `level`, `weight`, `waste_type`, `last update`.
- **Gauges**
  - Separate gauges for `level` and `weight`.
- **Timeseries chart**
  - Plot `level` and `weight` trends over time.
- **Alarms widget** (if enabled)
  - Show active/unacknowledged alarms and latest triggered events.

## 4) Gauge colors and thresholds
Apply consistent ranges across all bins:
- **Safe (green):** 0–49%
- **Caution (yellow):** 50–74%
- **Warning (orange):** 75–89%
- **Full (red):** 90–100%

For weight, map the same color bands to percentage of configured max load.

## 5) Short client demo script
1. Start on **Entities table** with all bins; confirm live status and recent updates.
2. Filter to **Foodcourt A bins** and show normal behavior (safe/caution states).
3. Trigger a **warning** scenario (e.g., set one bin to ~80% level) and show gauge + alarm response.
4. Trigger a **full** scenario (>=90%) and show red state + escalation visibility.
5. Simulate an **offline** device and show how status/last update highlights non-reporting bins.
6. Return to **All bins** view and summarize how operators prioritize pickups.
