# Wind

Generic wind risk signal. Not tied to shades or any other device. Reads a live gust sensor and a forecast weather entity, then publishes a latched **Level** your automations can watch.

## What it publishes

| Entity | Category | State | Use |
|--------|----------|-------|-----|
| Level | sensor | `safe`, `advisory`, or `warning` | Automation trigger |
| Risk | sensor | speed | Raises Level |
| Calm | sensor | speed | Lowers Level |
| Gust factor | sensor | 1.0–3.0 | Scales forecast sustained wind toward gust lines |
| Guide | diagnostic | rise and fall ladders | How to use Wind and what each Configuration speed means |
| Weather station | config | gust entity id | Local lane source |
| Weather forecast | config | weather entity id | Forecast lane source |
| Rise to advisory | config | speed, default 30 | Risk ≥ this → `advisory` |
| Rise to warning | config | speed, default 60 | Risk ≥ this → `warning` |
| Fall from warning | config | speed, default 45 | Calm &lt; this leaves `warning` for `advisory` |
| Fall to safe | config | speed, default 20 | Calm &lt; this → `safe` |

Open the device page to change Configuration. **Guide** (Diagnostics) shows the current rise and fall ladders with your numbers, plus a short how-to. Dashboards can link to this device page so people can open Guide without hunting for it.

## How Level moves

Rise (Risk):

| From | To | When |
|------|----|------|
| safe | advisory | Risk ≥ Rise to advisory |
| safe or advisory | warning | Risk ≥ Rise to warning |

Fall (Calm):

| From | To | When |
|------|----|------|
| warning | advisory | Calm &lt; Fall from warning |
| advisory or warning | safe | Calm &lt; Fall to safe |
| anything | unchanged | Risk and Calm both unknown |

Example with defaults: ↑ `safe → advisory (30) → warning (60)` · ↓ `warning → advisory (<45) → safe (<20)`.

Risk is the higher of the fresh 3-minute local gust and the next 2 hours of forecast wind × Gust factor. Calm is the higher of the fresh 30-minute local gust and the next 1 hour of scaled forecast. Missing numbers never count as calm. A calm forecast cannot pull a live gust down.

## Gust factor

Starts at `1.4` (ordinary open-air gust ÷ sustained ≈ 1.3–1.5). Each accepted hour blends `80%` previous + `20%` sample, step `0.05`, range `1.0`–`3.0`. A sample needs a fresh station heartbeat, 30-minute gust ≥ 5, and raw forecast sustained ≥ 8. The sample uses raw forecast wind so the factor cannot chase its own scaled output.

## Lanes

- **Local.** Gust sensor, heartbeat optional (defaults to the gust entity). Fresh for 15 minutes after the last heartbeat report.
- **Forecast.** `weather.get_forecasts` hourly, refreshed about every 15 minutes. Stale after 3 hours.
- **Both missing.** Level stays where it was.

## Automations

Trigger on Level, for example:

```yaml
trigger:
  - platform: state
    entity_id: sensor.YOUR_WIND_LEVEL
action:
  - choose:
      - conditions: "{{ trigger.to_state.state == 'warning' }}"
        sequence: []  # your strongest response
      - conditions: "{{ trigger.to_state.state == 'advisory' }}"
        sequence: []  # your medium response
      - conditions: "{{ trigger.to_state.state == 'safe' }}"
        sequence: []  # clear / restore
```

Hold times and actions stay in your automation. This device only publishes the signal.
