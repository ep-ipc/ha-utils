# Blueprints

HA Utils deploys blueprints from `bundled/blueprints/` to `/config/blueprints/`. See [Deploy](deploy.md) for the copy rules and folder conventions.

Weather alerts are not blueprints. Add a [Wind, Temperature, or Bad weather](devices/README.md) entry and trigger your own automation on the entities it publishes.

## Control all by device type

Location: `bundled/blueprints/script/ha_utils/` (deployed to `/config/blueprints/script/ha_utils/`)

Script blueprint that turns on or off every entity of a chosen device type (domain), with optional exceptions.

| Blueprint | Behavior |
|-----------|----------|
| HA Utils - Control all by device type | Turn on/off all entities of a domain, skipping any listed exceptions |

Configurable inputs:

- **Device type** — domain to control (`light`, `fan`, `switch`, `media_player`, `cover`, `humidifier`, `siren`, `input_boolean`)
- **Action** — turn on or turn off
- **Exceptions** — entities to leave alone; leave empty to control all entities of that type

Create a script from this blueprint (for example “All lights off”), then run it from the UI, Assist, a dashboard button, or another automation.

## Deployed location

```
/config/blueprints/
```

Bundled source: `custom_components/ha_utils/bundled/blueprints/`

Home Assistant auto-discovers blueprints under `/config/blueprints/`. No extra `configuration.yaml` include is required.

Deploy removes these retired weather-alert blueprints if they are still in `/config`:

- `blueprints/automation/ha_utils/high_wind.yaml`
- `blueprints/automation/ha_utils/hot_day.yaml`
- `blueprints/automation/ha_utils/cold_day.yaml`
- `blueprints/automation/ha_utils/possible_thunderstorm.yaml`

A `.bak` copy is kept when backup is enabled. Automations already created from those blueprints stop loading, because the blueprint file is gone. Replace each one with a normal automation that triggers on a [signal entity](signals.md). New automations should use those entities directly.

## How to use

1. Install HA Utils and confirm blueprints are deployed — see [Deploy](deploy.md).
2. Open **Settings → Automations & scenes → Blueprints**.
3. Create a script from the control-all blueprint.

## Upgrading blueprints

Bundled blueprints are refreshed by default when deploy runs (`overwrite_existing: true`). Set `overwrite_existing: false` if you want copy-if-missing behavior. See [Deploy](deploy.md).

## Adding blueprints

Add files under `bundled/blueprints/<domain>/ha_utils/` and run deploy. See [Deploy](deploy.md).
