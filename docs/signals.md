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
- Forecast look-ahead is about 2 hours.
- Changing a configuration entity reloads that signal.
