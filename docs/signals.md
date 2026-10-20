# Signals

Signal entries are added under the Home Assistant Utils integration. Each one reads a source entity and publishes entities an automation can trigger on. The calculation stays inside the entry. There are no separate helpers, and these entries do not run actions.

Use them from your own automation: a state trigger on Level, Hot, Cold, or Bad weather, with whatever hold time and actions you want.

## Where to add one

1. Open **Settings → Devices & services → Home Assistant Utils**.
2. Choose **Add wind**, **Add temperature**, or **Add bad weather**.
3. Pick the source entities and save.

The new device is listed on that same page. Its entities are what automations use.

Each device page has a Configuration card. Changing a selector or a hot/cold number reloads that signal with the new settings. The weather-station list fills in after those sensors finish loading, and it does not include this signal's own entities. Choose `none` on Temperature or Bad weather to use the forecast only.

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

`big` means the lower rise line. `all` means the higher rise line. Those lines are yours to set. They start at 30 and 60 for rising, and 45 and 20 for falling, in the gust sensor's speed unit.

The Configuration card has **Weather station**, **Forecast**, **Rise to big**, **Rise to all**, **Fall from all**, and **Fall to safe**.

## Temperature

One entry for heat and cold. It is separate from Wind. Hot and cold are your lines, not a fixed definition. They start at 90 and 32, in the forecast temperature unit, and you can change them on the device page.

Inputs:

- Optional weather-station temperature sensor. A fresh reading (updated in the last 15 minutes) is the published temperature.
- Forecast `weather` entity. Used when the station is missing or stale. The high and low over the next 2 hours can turn Hot or Cold on early. A cooler or warmer forecast cannot turn them off while the live station is still past the line.
- Hot above, default 90
- Cold below, default 32

Entities on the device:

| Entity name | State | Use |
|---|---|---|
| Temperature | number | Live station temperature, or the forecast temperature when the station is stale |
| Hot | on / off | On while the live reading or the forecast high is above Hot above |
| Cold | on / off | On while the live reading or the forecast low is below Cold below |

The Configuration card has **Weather station**, **Forecast**, **Hot above**, and **Cold below**. Weather station can be set to `none`.

## Bad weather

Inputs:

- Optional weather-station rain sensor. A moisture sensor that is on, or a rain amount above 0, counts as rain when that sensor was updated in the last 15 minutes.
- Forecast `weather` entity
- Conditions, default lightning, lightning-rainy, pouring, and rainy

Either source can turn the signal on. Station rain stays on even if the forecast still says sunny. A forecast hour in the next 2 hours whose condition is in the list turns it on even if the station is dry and the current condition is still sunny.

**Condition** is the current forecast state, or `rainy` when only the station sees rain. It can say `sunny` while **Bad weather** is on, because On includes rain that has not arrived yet.

**Reason** is one sentence for the current decision, for example: `On because the forecast is rainy at 4:00 PM. The station is dry.` The same sentence is written to the activity log when it changes. Home Assistant still shows “No cause was recorded” on the state-change row, because that box is only filled when a person or an automation made the change. Read **Reason**, or the activity line that carries the sentence.

Entities on the device:

| Entity name | State | Use |
|---|---|---|
| Condition | weather state | Current forecast condition, or `rainy` when only the station sees rain |
| Bad weather | on / off | On while the station reports rain or an upcoming forecast hour is in the selected list |
| Reason | sentence | Why Bad weather is on or off |

The Configuration card has **Weather station** and **Forecast**. Weather station can be set to `none`. The station list is rain sensors: moisture, precipitation, and precipitation intensity.
