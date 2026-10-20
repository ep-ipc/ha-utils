# Temperature

Heat and cold signal from an optional live temperature sensor and a forecast weather entity. Hot and cold are your lines, not a fixed definition.

## What it publishes

| Entity | Category | State | Use |
|--------|----------|-------|-----|
| Temperature | sensor | number | Live station reading, or forecast when the station is stale |
| Hot | binary | on / off | Automation trigger for heat |
| Cold | binary | on / off | Automation trigger for cold |
| Guide | diagnostic | short summary | How to set the Configuration values |
| Weather station | config | temperature sensor or `none` | Live source |
| Weather forecast | config | weather entity id | Forecast source |
| Hot above | config | temperature, default 90 | Hot turns on above this |
| Cold below | config | temperature, default 32 | Cold turns on below this |

Thresholds use the forecast temperature unit (or the station unit when that is all you have).

## How it decides

- A station reading updated in the last 15 minutes is the published **Temperature**.
- Hot is on if the live reading is above Hot above, or the forecast high over the next 2 hours is above Hot above.
- Cold is on if the live reading is below Cold below, or the forecast low over the next 2 hours is below Cold below.
- The forecast can turn Hot or Cold on early. It cannot turn them off while the live station is still past the line.
- Weather station may be `none` to use forecast only.

## Automations

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.YOUR_TEMPERATURE_HOT
    to: "on"
    for:
      minutes: 15
```

Hold duration and actions stay in your automation.
