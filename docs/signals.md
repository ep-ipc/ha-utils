# Signals

Signal devices live under **Home Assistant Utils**. Each one reads weather sources and publishes entities your automations can trigger on. The calculation stays inside the device. These entries do not run actions.

## Device docs

| Device | Doc |
|--------|-----|
| Wind | [devices/wind.md](devices/wind.md) |
| Temperature | [devices/temperature.md](devices/temperature.md) |
| Bad weather | [devices/bad-weather.md](devices/bad-weather.md) |
| Index | [devices/README.md](devices/README.md) |

## Where to add one

1. Open **Settings → Devices & services → Home Assistant Utils**.
2. Choose **Add wind**, **Add temperature**, or **Add bad weather**.
3. Pick the source entities and save.

The device page Configuration card holds sources and thresholds. Each device also has a **Guide** diagnostic and a link to its doc (device menu → open configuration URL).

## Shared behavior

- Prefer a fresh local station (15 minutes). Forecast is fallback and early warning.
- Forecast may turn a signal on. It must not clear a live station reading that is still past the line.
- Forecast look-ahead is about 2 hours. Signals also publish the first forecast hour (up to 24 hours ahead) that would cross a line, as `*_expected_at` attributes.
- Forecast values are converted to the station's unit (Wind) or the station to the forecast's unit (Temperature).
- Starting lines follow your unit system (mph and °F, or km/h and °C).
- Rise and fall lines must keep their order. The setup form and the device page reject lines that would make a signal flap or stick.
- Each device has a **Reason** sensor. When the main entity changes (Level, Hot, Cold, Bad weather), its Reason sentence goes to the activity log.
- Each device offers **device triggers** (for example *Level became warning*, *Hot turned on*) in the automation editor.
- Freshness is re-checked every minute. A station that has not reported for 2 hours raises a repair under **Settings → System → Repairs**.
- Signals that share a weather entity share one forecast request.
- **Download diagnostics** on the integration includes each signal's sources and the numbers behind its state.
- Changing a configuration entity reloads that signal.
