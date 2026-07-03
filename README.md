# HA Utils Font Scale Themes

Theme pack for making the default Home Assistant UI font larger without a custom integration, action, script, or frontend JavaScript.

The themes only set one variable:

```yaml
ha-font-size-scale: "1.2"
```

Everything else falls back to Home Assistant's built-in default theme.

## Included Themes

- `HA Utils Default Font 100%`
- `HA Utils Default Font 110%`
- `HA Utils Default Font 115%`
- `HA Utils Default Font 120%`
- `HA Utils Default Font 125%`
- `HA Utils Default Font 130%`
- `HA Utils Default Font 140%`
- `HA Utils Default Font 150%`

The number is the font scale percentage. For example, `HA Utils Default Font 120%` sets `ha-font-size-scale` to `1.2`.

## Install

Install with HACS as a custom repository of type **Theme**. HACS will automatically copy `themes/ha_utils_font_scale.yaml` into Home Assistant's `/config/themes/` directory during install/update.

Manual fallback: copy `themes/ha_utils_font_scale.yaml` into `/config/themes/` yourself.

Enable themes in `/config/configuration.yaml` if you have not already:

```yaml
frontend:
  themes: !include_dir_merge_named themes
```

Restart Home Assistant once after adding the `frontend.themes` include. If themes were already enabled, use **Developer tools > YAML > Reload themes** after installing/updating the theme.

## Use

1. Open **Settings > System > Restart Home Assistant** after first install, or run **Developer tools > YAML > Reload themes** after changing only theme files.
2. Open your profile/theme selector.
3. Choose one of the `HA Utils Default Font ...` themes.

This works in the web UI and Companion App because it uses Home Assistant's normal theme system.

## Upgrading From The Old Integration

If you previously tested the custom integration version, remove the old theme file:

```text
/config/themes/ha_utils_typography.yaml
```

Then reload themes or restart Home Assistant. The old `ha_utils_typography` theme used scale `1`, so selecting it will not increase font size.

## Notes

- Home Assistant's built-in UI does not provide a numeric editor for arbitrary theme variables. To choose font size from the UI without automations or scripts, this repo ships multiple prebuilt theme sizes.
- Theme selection can be per user/browser/app depending on how you select it in Home Assistant. To apply broadly, set the theme as the default/backend-selected theme and avoid per-device overrides.
- Existing users of the previous `ha_utils` custom integration can remove `custom_components/ha_utils`; it is no longer needed for this theme-only version.

## Local Development

```bash
make test
```
