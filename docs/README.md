# HA Utils Documentation

User and contributor docs for the Home Assistant Utils integration.

## Features

| Doc | Description |
|-----|-------------|
| [Install](install.md) | HACS install, integration setup, required `configuration.yaml` includes |
| [Signals](signals.md) | Overview of optional signal devices |
| [Devices](devices/README.md) | Per-device docs: Wind, Temperature, Bad weather |
| [Themes](themes.md) | Bundled themes (font scale pack) |
| [Scripts](scripts.md) | Bundled package scripts (expose-all to voice assistant) |
| [Blueprints](blueprints.md) | Bundled script blueprint |
| [Deploy](deploy.md) | How bundled resources are copied to `/config` |

Development rules: [AGENT.md](../AGENT.md)

## Doc layout

```text
docs/
├── README.md           # this index
├── signals.md          # short overview + links
├── devices/
│   ├── README.md       # device index and shared rules
│   ├── wind.md
│   ├── temperature.md
│   └── bad-weather.md
├── install.md
├── deploy.md
├── themes.md
├── scripts.md
└── blueprints.md
```

## Naming

- Doc files use lowercase kebab-case (`bad-weather.md`, `install.md`).
- Index files use `README.md`.
- Each signal device has one doc under `devices/`. Keep the same section order: publishes → how it decides → automations.
- When behavior changes, update the matching device doc, `signals.md` if the overview changed, and `AGENT.md` if an agent rule changed.
