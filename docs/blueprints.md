# Blueprints

HA Utils deploys automation blueprints from `bundled/blueprints/` to `/config/blueprints/`. See [Deploy](deploy.md) for the copy rules and folder conventions.

## Deployed location

```
/config/blueprints/
```

Bundled source: `custom_components/ha_utils/bundled/blueprints/`

Home Assistant auto-discovers blueprints under `/config/blueprints/`. No extra `configuration.yaml` include is required.

## How to use

1. Install HA Utils and confirm blueprints are deployed — see [Deploy](deploy.md).
2. Open **Settings → Automations & scenes → Blueprints**.
3. Create an automation from an HA Utils blueprint.
4. Configure inputs and actions.

## Bundled blueprints

### Weather alerts

Location: `bundled/blueprints/automation/ha_utils/` (deployed to `/config/blueprints/automation/ha_utils/`)

Automation blueprints for weather-based alerts. Each uses a `weather` entity as the trigger source and lets you configure thresholds, hold duration, cooldown, and actions.

| Blueprint | Trigger |
|-----------|---------|
| HA Utils - High wind alert | `wind_speed` attribute above threshold |
| HA Utils - Hot day alert | `temperature` attribute above threshold |
| HA Utils - Cold day alert | `temperature` attribute below threshold |
| HA Utils - Possible thunderstorm alert | Weather state in storm-like conditions |

Configurable inputs:

- **Weather entity** — must be a `weather` domain entity
- **Threshold or conditions** — varies by blueprint
- **Hold duration** — how long the condition must remain true
- **Cooldown** — minimum time between automation runs
- **Actions** — what to run when triggered

## Upgrading blueprints

Bundled blueprints are copy-if-missing by default. After upgrading HA Utils, run `ha_utils.deploy_bundled` with `overwrite_existing: true` to refresh them. See [Deploy](deploy.md).

## Adding blueprints

Add files under `bundled/blueprints/<domain>/ha_utils/` and run deploy. See [Deploy](deploy.md).
