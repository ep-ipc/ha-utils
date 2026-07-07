# Themes

HA Utils deploys theme files from `bundled/themes/` to `/config/themes/`. See [Deploy](deploy.md) for the copy rules and folder conventions.

## Deployed location

```
/config/themes/
```

Bundled source: `custom_components/ha_utils/bundled/themes/`

## Prerequisites

Add to `/config/configuration.yaml`:

```yaml
frontend:
  themes: !include_dir_merge_named themes
```

Restart Home Assistant once after adding this include. If it already exists, use **Developer tools → YAML → Reload themes** after installing or updating HA Utils.

See [Install](install.md) for setup steps.

## How to use

1. Install HA Utils and confirm theme files are deployed — see [Deploy](deploy.md).
2. Reload themes or restart Home Assistant.
3. Open your profile / theme selector.
4. Choose an HA Utils theme.

Themes work in the web UI and Companion App through Home Assistant's normal theme system.

## Bundled themes

### Font scale

File: `ha_utils_font_scale.yaml`

Increases Home Assistant UI font size without replacing the default light/dark color scheme.

| Theme name | Scale |
|------------|-------|
| HA Font 100% | 1.0 |
| HA Font 110% | 1.1 |
| HA Font 115% | 1.15 |
| HA Font 120% | 1.2 |
| HA Font 125% | 1.25 |
| HA Font 130% | 1.3 |
| HA Font 140% | 1.4 |
| HA Font 150% | 1.5 |

Each variant only sets `ha-font-size-scale` in both `light` and `dark` modes. Home Assistant keeps its default light/dark bases and the Auto/Light/Dark selector still works.

## Notes

- Home Assistant's primary/accent color pickers are special to the built-in `Home Assistant` theme. Custom themes can define colors in YAML, but they cannot keep those picker controls.
- If you previously tested `ha_utils_typography`, delete `/config/themes/ha_utils_typography.yaml`. That old theme used scale `1` and will not increase font size.

## Adding themes

Add a new file under `bundled/themes/` and run deploy. See [Deploy](deploy.md).
