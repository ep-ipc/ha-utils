# Bad weather

On/off storm and rain signal from an optional live rain sensor and a forecast weather entity.

## What it publishes

| Entity | Category | State | Use |
|--------|----------|-------|-----|
| Condition | sensor | weather state | Current forecast condition, or `rainy` when only the station sees rain |
| Bad weather | binary | on / off | Automation trigger |
| Reason | sensor | sentence | Why it is on or off; also written to the activity log when it changes |
| Guide | diagnostic | short summary | How sources and conditions work |
| Weather station | config | rain sensor or `none` | Live source (moisture / precipitation) |
| Weather forecast | config | weather entity id | Forecast source |

Default bad conditions: `lightning`, `lightning-rainy`, `pouring`, `rainy`. Edit them in the subentry reconfigure flow under Home Assistant Utils.

## How it decides

- Station rain: a moisture sensor that is on, or a precipitation amount above 0, counts when that sensor reported in the last 15 minutes.
- Forecast: current condition, or any hour in the next 2 hours, matching the selected list.
- Either source can turn **Bad weather** on.
- **Condition** can stay `sunny` while Bad weather is on, because On includes rain that has not arrived yet.
- Home Assistant’s activity “What happened” box still says no cause was recorded for state changes. Read **Reason** instead.

## Automations

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.YOUR_BAD_WEATHER
    to: "on"
```

Use Reason in notifications if you want the same sentence the device shows.
