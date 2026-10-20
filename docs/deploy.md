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
| `bundled/blueprints/script/ha_utils/control_all_by_domain.yaml` | `/config/blueprints/script/ha_utils/control_all_by_domain.yaml` |
| `bundled/packages/ha_utils.yaml` | `/config/packages/ha_utils.yaml` |
| `bundled/packages/ha_utils/scripts/expose_all_to_voice_assistant.yaml` | `/config/packages/ha_utils/scripts/expose_all_to_voice_assistant.yaml` |

Every file under `bundled/` is walked recursively and copied to the same relative path under `/config`.

## When deploy runs

| Trigger | When |
|---------|------|
| Integration setup | Every time **Home Assistant Utils** sets up, including restart and reload |
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

## Folder conventions

### 1. Top-level folder = HA config folder name

```
bundled/themes/       → /config/themes/
bundled/blueprints/   → /config/blueprints/
bundled/packages/     → /config/packages/
```

### 2. Namespace under `ha_utils/`

```
bundled/blueprints/script/ha_utils/       # script blueprint namespace
bundled/packages/ha_utils/                # package sub-resources
bundled/packages/ha_utils/scripts/        # scripts
```

### 3. One package entry file at `packages/` root

```yaml
# packages/ha_utils.yaml
script: !include ha_utils/scripts/expose_all_to_voice_assistant.yaml
```

### 4. Blueprints vs packages

| Type | Bundled path | Purpose |
|------|--------------|---------|
| Blueprint | `bundled/blueprints/<domain>/ha_utils/` | Template users create from the UI |
| Package | `bundled/packages/ha_utils/` | Ready-to-use entities (scripts) |

Blueprints are auto-discovered from `/config/blueprints/`. Packages require the `homeassistant.packages` include — see [Install](install.md).

## Current bundled layout

```text
bundled/
├── themes/
│   └── ha_utils_font_scale.yaml
├── blueprints/
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
- Deploy does **not** delete files that left the bundle. Remove stale files from `/config` yourself if needed.
- Existing files are updated on deploy by default. Set `overwrite_existing: false` for copy-if-missing.

## Adding a new bundled script

1. Add `bundled/packages/ha_utils/scripts/my_script.yaml`.
2. Reference it from `bundled/packages/ha_utils.yaml`.
3. Run deploy (or reinstall the integration).
4. Reload scripts or restart Home Assistant.
