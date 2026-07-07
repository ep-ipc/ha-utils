# Home Assistant Utils

HACS custom integration that deploys reusable Home Assistant resources into your `/config` directory — themes, packages, blueprints, and integration services.

## Features

| Feature | Summary |
|---------|---------|
| [Install](docs/install.md) | HACS setup, integration install, required `configuration.yaml` includes |
| [Deploy](docs/deploy.md) | How bundled files map to `/config`, copy policy, and upgrade workflow |
| [Themes](docs/themes.md) | Bundled themes (font scale pack) |
| [Scripts](docs/scripts.md) | Bundled package scripts (expose-all to voice assistant) |
| [Blueprints](docs/blueprints.md) | Bundled automation blueprints (weather alerts) |

Full doc index: [docs/README.md](docs/README.md)

## Quick start

1. Install in HACS as type **Integration**.
2. Restart Home Assistant and add **Home Assistant Utils** under **Settings → Devices & services**.
3. Add required includes to `configuration.yaml` — see [Install](docs/install.md).
4. Use deployed resources from the theme selector, Blueprints, or Scripts UI.

Bundled resources are **copy-if-missing** on setup. Run `ha_utils.deploy_bundled` to copy missing files or refresh after upgrades — see [Deploy](docs/deploy.md).

## Local development

```bash
make test
```
