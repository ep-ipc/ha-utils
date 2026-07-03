# Home Assistant Utils

HACS custom integration that bundles utility **packages** and **blueprints**, and registers **actions** (services) for theme typography scaling.

See **[docs/PLAN.md](docs/PLAN.md)** for the full phased implementation guide (all 9 phases, file-by-file specs, testing checklist, and v1.1+ roadmap).

## Features

- **Actions** (`ha_utils.patch_themes`, `ha_utils.reload_themes`, `ha_utils.deploy_bundled`) — run from **Settings → Developer tools → Actions**
- **Runtime font scaling** on the **default HA theme** — no `/config/themes` folder required
- **Optional YAML patching** when custom theme files exist (Mushroom, card-mod, etc.)
- **Copy-if-missing deploy** of `packages/ha_utils.yaml`, script blueprints, and optional starter theme on integration setup
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

4. **Restart Home Assistant** after first install (loads the deployed package and frontend module)

### Default theme (out of the box)

If you use Home Assistant’s built-in default theme, you do **not** need a `themes/` folder. Run `ha_utils.patch_themes` with your desired `scale` — the integration injects `--ha-font-size-scale` at runtime on every page load.

Refresh the browser tab (or reload the HA app) after the first apply if you do not see a change immediately.

### Optional: custom theme YAML

For Mushroom card font keys, card-mod dividers, and persistent scale in theme files:

```yaml
frontend:
  themes: !include_dir_merge_named themes
```

Create `/config/themes/` and install themes via HACS or copy `.yaml` files there. On first setup, `deploy_bundled` may copy a starter `themes/ha_utils_typography.yaml` if missing.

## Running utilities (primary)

**Settings → Developer tools → Actions**

### Preview changes (dry run)

- Action: `ha_utils.patch_themes`
- `scale`: `1.2`
- `line_height`: `1.8`
- `dry_run`: `true`

Check **Settings → System → Logs** for `Would apply runtime font scale` and `Would patch theme` lines.

### Apply patches

- Action: `ha_utils.patch_themes`
- `scale`: `1.2`
- `dry_run`: `false`

Applies runtime scale immediately. When theme YAML exists, creates a `.bak` file next to each modified file.

### Optional: custom themes path

If themes live elsewhere, set **Themes path** on the action (e.g. `themes`, `custom/themes`, or a full path).

Auto-detection reads `frontend.themes` from `configuration.yaml` (`!include`, `!include_dir_merge_named`, etc.).

### Reload themes

- Action: `ha_utils.reload_themes` — only needed after YAML theme file changes (not required for runtime-only scaling).

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

**Always (default theme included):**

- Sets `--ha-font-size-scale` and `--ha-line-height-normal` via a frontend module

**When theme YAML files exist:**

- `ha-font-size-scale` and `ha-line-height-normal` in YAML
- Fixed `ha-font-size-*` / `title-font-size` px values → `calc(... * var(--ha-font-size-scale))`
- Mushroom card font keys → scaled HA or token variables
- `--text-divider-font-size` in card-mod CSS blocks

## Upgrade policy

Bundled files are **copy-if-missing only** — existing `packages/ha_utils.yaml` and blueprints are never overwritten on upgrade. Use `ha_utils.deploy_bundled` to copy newly added bundle files.

## Limitations

- Cannot edit `configuration.yaml` automatically — enable `packages:` manually
- Package YAML loads at startup — restart required after first deploy
- Legacy custom cards with hardcoded px may not respect the typography scale
