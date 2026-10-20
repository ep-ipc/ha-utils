# Temperature

Heat and cold signal from an optional live temperature sensor and a forecast weather entity. Hot and cold are your lines, not a fixed definition.

## What it publishes

| Entity | Category | State | Use |
|--------|----------|-------|-----|
| Temperature | sensor | number | Live station reading, or forecast when the station is stale |
| Hot | binary | on / off | Automation trigger for heat |
| Cold | binary | on / off | Automation trigger for cold |
| Reason | sensor | sentence | Why Hot or Cold is on or off; written to the activity log when Hot or Cold changes |
| Guide | diagnostic | short summary | How to set the Configuration values |
| Weather station | config | temperature sensor or `none` | Live source |
| Weather forecast | config | weather entity id | Forecast source |
| Hot above | config | temperature, default 90 °F / 32 °C | Hot turns on above this |
| Cold below | config | temperature, default 32 °F / 0 °C | Cold turns on below this |
| Clear margin | config | temperature, default 2 °F / 1 °C | How far back past the line before Hot or Cold turns off |

Thresholds use the forecast temperature unit (or the station unit when that is all you have). A station in another unit is converted to the forecast unit. Cold below must be lower than Hot above.

Hot and Cold carry `hot_expected_at` / `cold_expected_at`: the first forecast hour (next 24 hours) past each line.

## How it decides

- A station reading updated in the last 15 minutes is the published **Temperature**.
- Hot is on if the live reading is above Hot above, or the forecast high over the next 2 hours is above Hot above.
- Cold is on if the live reading is below Cold below, or the forecast low over the next 2 hours is below Cold below.
- The forecast can turn Hot or Cold on early. It cannot turn them off while the live station is still past the line.
- Once on, Hot stays on until the live reading and the forecast high are both at or below Hot above minus Clear margin. Cold works the same way upward. This stops flapping around the line.
- A station that has not reported for 2 hours raises a repair.
- Weather station may be `none` to use forecast only.

## Automations

In the automation editor, pick the Temperature device and **Hot turned on**, **Cold turned off**, and so on. Or:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.YOUR_TEMPERATURE_HOT
    to: "on"
    for:
      minutes: 15
```

Hold duration and actions stay in your automation.
