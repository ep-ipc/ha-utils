# Signals

Signal entries are added under the Home Assistant Utils integration. Each one reads a source entity and publishes a small set of entities an automation or scene can trigger on. The calculation stays inside the entry. There are no separate helpers to delete.

## Where to add one

1. Open **Settings → Devices & services → Home Assistant Utils**.
2. Choose **Add wind signal**, **Add hot day signal**, **Add cold day signal**, or **Add thunderstorm signal**.
3. Pick the source entities and save.

The new device is listed on that same page. Its entities are what automations use.

On the wind device page, the Configuration card has two selectors: **Weather station** (a wind-speed sensor from the station) and **Forecast** (a weather entity). Changing either one switches the sources for that device.

## Wind signal

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

## Hot day, cold day, thunderstorm

Each publishes one binary sensor named **Active**.

- Hot day is on while the weather temperature is above the threshold.
- Cold day is on while it is below the threshold.
- Thunderstorm is on while the weather state is one of the selected conditions.

An automation can require the state to hold for a duration. These signals do not run actions themselves. The existing weather blueprints remain for automations that should run actions directly.
