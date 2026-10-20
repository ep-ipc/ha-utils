# Bad weather

On/off storm and rain signal from an optional live rain sensor and a forecast weather entity.

## What it publishes

| Entity | Category | State | Use |
|--------|----------|-------|-----|
| Condition | sensor | weather state | Current forecast condition, or `rainy` when only the station sees rain |
| Bad weather | binary | on / off | Automation trigger |
| Reason | sensor | sentence | Why it is on or off; written to the activity log when Bad weather turns on or off |
| Guide | diagnostic | short summary | How sources and conditions work |
| Weather station | config | rain sensor or `none` | Live source (moisture / precipitation) |
| Weather forecast | config | weather entity id | Forecast source |
| Hold for | config | minutes, default 30 | Stay on this long after the last bad weather |

Default bad conditions: `lightning`, `lightning-rainy`, `pouring`, `rainy`. Edit them in the subentry reconfigure flow under Home Assistant Utils.

## How it decides

- Station rain counts when that sensor reported in the last 15 minutes and:
  - a moisture sensor is on, or
  - a rain rate (`precipitation_intensity`, or a unit per hour such as `in/h`) is above 0, or
  - a rain total (`precipitation`, such as rain today) rose in the last 30 minutes. A total that is above 0 but not rising is dry. The first reading after a restart only sets the baseline.
- Forecast: current condition, or any hour in the next 2 hours, matching the selected list.
- Either source can turn **Bad weather** on. It stays on for **Hold for** minutes after the last one, so a forecast that swings between rainy and cloudy does not flap. `held_until` shows when the hold ends.
- `next_bad_at` is the first forecast hour (next 24 hours) with a matching condition.
- A station that has not reported for 2 hours raises a repair.
- **Condition** can stay `sunny` while Bad weather is on, because On includes rain that has not arrived yet.
- Home Assistant’s activity “What happened” box still says no cause was recorded for state changes. Read **Reason** instead.

## Automations

In the automation editor, pick the Bad weather device and **Bad weather turned on** or **turned off**. Or:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.YOUR_BAD_WEATHER
    to: "on"
```

Use Reason in notifications if you want the same sentence the device shows.
