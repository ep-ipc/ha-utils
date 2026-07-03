# Home Assistant Utils

HACS custom integration that bundles utility **packages** and **blueprints**, and registers **actions** (services) for theme typography patching.

Logic is ported from [ha-helper](https://github.com/parthkheni/ha-helper) `scale_theme_fonts.py`.

## Features

- **Actions** (`ha_utils.patch_themes`, `ha_utils.reload_themes`, `ha_utils.deploy_bundled`) — run from **Settings → Developer tools → Actions**
- **Copy-if-missing deploy** of `packages/ha_utils.yaml` and script blueprints on integration setup
- **Repair issues** when `packages:` is not enabled in `configuration.yaml`
- **CLI** (`make fonts`) for local theme directories

## Install

1. Install via HACS (custom repository) or copy `custom_components/ha_utils` into `/config/custom_components/`
2. **Settings → Devices & services → Add integration → Home Assistant Utils**
3. Add to `configuration.yaml` if not already present:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

4. **Restart Home Assistant** after first install (loads the deployed package)

## Running utilities (primary)

**Settings → Developer tools → Actions**

### Preview changes (dry run)

- Action: `ha_utils.patch_themes`
- `scale`: `1.2`
- `line_height`: `1.8`
- `dry_run`: `true`

Check **Settings → System → Logs** for `Would patch theme: ...` lines.

### Apply patches

- Action: `ha_utils.patch_themes`
- `scale`: `1.2`
- `dry_run`: `false`

Creates a `.bak` file next to each modified theme YAML.

### Reload themes

- Action: `ha_utils.reload_themes`

### Re-deploy missing bundle files

- Action: `ha_utils.deploy_bundled`

## Package scripts (optional)

After restart, these scripts are available for automations:

| Script | Description |
|--------|-------------|
| `script.ha_utils_patch_themes` | Patch + reload |
| `script.ha_utils_patch_themes_dry_run` | Dry-run preview |

## Blueprints

Deployed to `/config/blueprints/script/ha_utils/patch_and_reload_themes.yaml`.

Create a script from **Settings → Automations & scenes → Blueprints**.

## Local development

```bash
cp .env.dist .env
mkdir -p themes && cp /path/to/your/themes/*.yaml themes/
make fonts FONT_SCALE=1.2
make test
```

## What `patch_themes` changes

- `ha-font-size-scale` and `ha-line-height-normal`
- Fixed `ha-font-size-*` / `title-font-size` px values → `calc(... * var(--ha-font-size-scale))`
- Mushroom card font keys → scaled HA or token variables
- `--text-divider-font-size` in card-mod CSS blocks

## Upgrade policy

Bundled files are **copy-if-missing only** — existing `packages/ha_utils.yaml` and blueprints are never overwritten on upgrade. Use `ha_utils.deploy_bundled` to copy newly added bundle files.

## Limitations

- Cannot edit `configuration.yaml` automatically — enable `packages:` manually
- Package YAML loads at startup — restart required after first deploy
- Legacy custom cards with hardcoded px may not respect the typography scale
