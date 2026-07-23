# Deploy

HA Utils deploys bundled resources from inside the integration into your Home Assistant `/config` directory.

## Core rule

Bundled paths mirror the Home Assistant config tree:

```
custom_components/ha_utils/bundled/<path>  →  /config/<path>
```

Examples:

| Bundled source | Deployed destination |
|----------------|----------------------|
| `bundled/themes/ha_utils_font_scale.yaml` | `/config/themes/ha_utils_font_scale.yaml` |
| `bundled/blueprints/automation/ha_utils/hot_day.yaml` | `/config/blueprints/automation/ha_utils/hot_day.yaml` |
| `bundled/packages/ha_utils.yaml` | `/config/packages/ha_utils.yaml` |
| `bundled/packages/ha_utils/scripts/expose_all_to_voice_assistant.yaml` | `/config/packages/ha_utils/scripts/expose_all_to_voice_assistant.yaml` |

There is no per-resource deploy logic. Every file under `bundled/` is walked recursively and copied to the same relative path under `/config`.

## When deploy runs

| Trigger | When |
|---------|------|
| Integration setup | First time you add **Home Assistant Utils** |
| `ha_utils.deploy_bundled` | Manually from **Settings → Developer tools → Actions** |

## Copy policy

| Situation | Result |
|-----------|--------|
| Destination file missing | Copy → logged as `copied` |
| Destination exists, `overwrite_existing: true` (default), content differs | Optional `.bak` backup, then replace → logged as `updated` |
| Destination exists, `overwrite_existing: false` | Keep existing file → logged as `skipped` |
| Source and destination identical | Skip even when overwrite is enabled |

After each run, a marker file is written to `/config/.ha_utils_deployed` with version, timestamp, and deploy results.

## Manual deploy

Run **Developer tools → Actions → `ha_utils.deploy_bundled`**.

Fields:

| Field | Default | Purpose |
|-------|---------|---------|
| `overwrite_existing` | `true` | Replace existing deployed files with bundled versions |
| `backup_existing` | `true` | Write `.bak` files before overwriting |

### Upgrade workflow

After upgrading HA Utils in HACS:

1. Open **Settings → Developer tools → Actions**.
2. Run `ha_utils.deploy_bundled`.
3. Keep `overwrite_existing: true` (default).
4. Keep `backup_existing: true` unless you do not want `.bak` files.

This refreshes blueprints and other bundled files that were skipped on first install.

## Folder conventions

Use these patterns when adding new bundled resources.

### 1. Top-level folder = HA config folder name

```
bundled/themes/       → /config/themes/
bundled/blueprints/   → /config/blueprints/
bundled/packages/     → /config/packages/
```

### 2. Namespace under `ha_utils/`

Group project content so it does not clash with user files:

```
bundled/blueprints/automation/ha_utils/   # automation blueprint namespace
bundled/blueprints/script/ha_utils/       # script blueprint namespace
bundled/packages/ha_utils/                # package sub-resources
bundled/packages/ha_utils/scripts/        # scripts
bundled/packages/ha_utils/automations/    # future
```

### 3. One package entry file at `packages/` root

Home Assistant loads only top-level `packages/*.yaml` files. Subfolders are wired with `!include`:

```yaml
# packages/ha_utils.yaml
script: !include ha_utils/scripts/expose_all_to_voice_assistant.yaml
```

After deploy, includes resolve relative to `/config/packages/ha_utils.yaml`.

### 4. Blueprints vs packages

| Type | Bundled path | Purpose |
|------|--------------|---------|
| Blueprint | `bundled/blueprints/<domain>/ha_utils/` | Template users create from the UI |
| Package | `bundled/packages/ha_utils/` | Ready-to-use entities (scripts, automations) |

Blueprints are auto-discovered from `/config/blueprints/`. Packages require the `homeassistant.packages` include — see [Install](install.md).

## Current bundled layout

```text
bundled/
├── themes/
│   └── ha_utils_font_scale.yaml
├── blueprints/
│   ├── automation/ha_utils/
│   │   ├── cold_day.yaml
│   │   ├── high_wind.yaml
│   │   ├── hot_day.yaml
│   │   └── possible_thunderstorm.yaml
│   └── script/ha_utils/
│       └── control_all_by_domain.yaml
└── packages/
    ├── ha_utils.yaml
    └── ha_utils/
        └── scripts/
            └── expose_all_to_voice_assistant.yaml
```

## Limitations

- Deploy does **not** edit `configuration.yaml`. You must add theme and package includes yourself.
- Deploy does **not** delete removed bundled files from `/config`. Delete stale files manually if needed.
- Existing files are updated on deploy by default. Set `overwrite_existing: false` if you want a copy-if-missing run.

## Adding a new bundled script

1. Add `bundled/packages/ha_utils/scripts/my_script.yaml`.
2. Reference it from `bundled/packages/ha_utils.yaml` (or use `!include_dir_merge_named`).
3. Run deploy (or reinstall the integration).
4. Reload scripts or restart Home Assistant.
