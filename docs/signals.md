# Signals

Signal entries are added under the Home Assistant Utils integration. Each one reads a source entity and publishes entities an automation can trigger on. The calculation stays inside the entry. There are no separate helpers, and these entries do not run actions.

Use them from your own automation: a state trigger on Level, Hot, Cold, or Bad weather, with whatever hold time and actions you want.

## Where to add one

1. Open **Settings → Devices & services → Home Assistant Utils**.
2. Choose **Add wind**, **Add temperature**, or **Add bad weather**.
3. Pick the source entities and save.

The new device is listed on that same page. Its entities are what automations use.

Each device page has a Configuration card for its sources. Changing a selector switches that device.

## Wind

A generic wind reading. It is not tied to shades or any other device.

Inputs:

- Gust sensor from a personal weather station
- Forecast `weather` entity
- Optional heartbeat sensor. Use a sensor on the same station that keeps updating when the gust number is steady. If omitted, the gust sensor is the heartbeat.
- Starting gust factor, default `1.4`
- Rise lines, default 30 then 60
- Fall lines, default 45 then 20

Entities on the device:

| Entity name | State | Use |
|---|---|---|
| Level | `safe`, `big`, or `all` | The automation trigger |
| Risk | speed | Raises the level. Higher of the 3-minute local gust and the next 2 hours of scaled forecast. |
| Calm | speed | Lowers the level. Higher of the 30-minute local gust and the next 1 hour of scaled forecast. |
| Gust factor | 1.0–3.0 | Learned scale from gust ÷ forecast sustained wind. Starts at the seed. |

The forecast is multiplied by the gust factor because it is a sustained wind and the lines are gust lines. The factor moves once an hour, 80 percent previous and 20 percent new, only when the 30-minute gust is at least 5 and the forecast sustained wind is at least 8. A calm forecast cannot pull a live gust down. If both sources are missing, the level stays where it was.

`big` means the lower rise line. `all` means the higher rise line.

The Configuration card selectors are **Weather station** and **Forecast**.

## Temperature

One entry for heat and cold. It is separate from Wind.

Inputs:

- Weather entity
- Hot above, default 90
- Cold below, default 32

Both thresholds use the weather entity's temperature unit.

Entities on the device:

| Entity name | State | Use |
|---|---|---|
| Temperature | number | The current weather temperature |
| Hot | on / off | On while temperature is above Hot above |
| Cold | on / off | On while temperature is below Cold below |

The Configuration card selector is **Weather**.

## Bad weather

Inputs:

- Weather entity
- Conditions, default lightning, lightning-rainy, pouring, and rainy

Entities on the device:

| Entity name | State | Use |
|---|---|---|
| Condition | weather state | The current condition, such as `rainy` or `sunny` |
| Bad weather | on / off | On while Condition is one of the selected states |

The Configuration card selector is **Weather**.
