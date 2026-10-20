# Signal devices

HA Utils publishes optional signal devices under one integration entry. Each device reads weather sources and publishes entities your own automations can trigger on. Devices do not run actions, move covers, or call scenes.

## Devices

| Device | Doc | Publishes |
|--------|-----|-----------|
| [Wind](wind.md) | Wind risk latch | Level, Risk, Calm, Gust factor, Guide |
| [Temperature](temperature.md) | Heat and cold | Temperature, Hot, Cold, Guide |
| [Bad weather](bad-weather.md) | Storm / rain | Condition, Bad weather, Reason, Guide |

## Where to add one

1. **Settings → Devices & services → Home Assistant Utils**
2. Add **Wind**, **Temperature**, or **Bad weather**
3. Use the new device’s entities in automations

Each device page has a **Configuration** card for sources and thresholds, and a **Guide** diagnostic that summarizes how to set those values. The device menu also links to the matching doc on GitHub.

## Shared rules

- A fresh local station (updated in the last 15 minutes) is preferred over the forecast.
- The forecast can turn a signal on early. It must not clear a live station reading that is still past the line.
- Changing a configuration entity reloads that signal.
- Full overview: [Signals](../signals.md)
