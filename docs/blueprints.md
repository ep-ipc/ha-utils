# Blueprints

HA Utils deploys one script blueprint from `bundled/blueprints/` to `/config/blueprints/`. See [Deploy](deploy.md) for the copy rules.

Weather alerts are signal devices, not blueprints. See [Devices](devices/README.md).

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

## How to use

1. Install HA Utils and confirm blueprints are deployed — see [Deploy](deploy.md).
2. Open **Settings → Automations & scenes → Blueprints**.
3. Create a script from the control-all blueprint.

## Upgrading

Bundled blueprints are refreshed by default when deploy runs (`overwrite_existing: true`). See [Deploy](deploy.md).

## Adding blueprints

Add files under `bundled/blueprints/<domain>/ha_utils/` and run deploy. See [Deploy](deploy.md).
