# Home Assistant Utils

HACS custom integration for reusable Home Assistant pieces: wind, temperature, and bad-weather signals you trigger from your own automations, plus bundled themes, scripts, and one script blueprint.

## Features

| Feature | Summary |
|---------|---------|
| [Themes](docs/themes.md) | Bundled themes (font scale pack) |
| [Scripts](docs/scripts.md) | Bundled package scripts (expose-all to voice assistant) |
| [Blueprints](docs/blueprints.md) | Bundled script blueprint |
| [Signals](docs/signals.md) | Optional wind, temperature, and bad weather entries for your own automations |
| [Devices](docs/devices/README.md) | Per-device docs (Wind, Temperature, Bad weather) |
| [Install](docs/install.md) | HACS setup, integration install, required `configuration.yaml` includes |
| [Deploy](docs/deploy.md) | How bundled files map to `/config`, copy policy, and upgrade workflow |

Full doc index: [docs/README.md](docs/README.md)

## Quick start

1. Install in HACS as type **Integration**.
2. Restart Home Assistant and add **Home Assistant Utils** under **Settings → Devices & services**.
3. Add required includes to `configuration.yaml` — see [Install](docs/install.md).
4. Under that integration, add **Wind**, **Temperature**, or **Bad weather**. Trigger your own automations on the entities those devices publish. See [Signals](docs/signals.md).
5. Themes, the expose-all script, and the control-all blueprint are copied into `/config` on setup. See [Install](docs/install.md).

Setup refreshes bundled files and removes the retired weather-alert blueprints. See [Deploy](docs/deploy.md).

## Local development

Development rules are in [AGENT.md](AGENT.md).

```bash
make test
```
