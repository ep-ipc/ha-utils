# Home Assistant Utils

HACS custom integration that deploys reusable Home Assistant resources into your `/config` directory.

Current bundled resource:

- `themes/ha_utils_font_scale.yaml` → copied to `/config/themes/ha_utils_font_scale.yaml`
- `blueprints/automation/ha_utils/*.yaml` → copied to `/config/blueprints/automation/ha_utils/`

The font-scale theme provides these selectable themes:

- `HA Font 100%`
- `HA Font 110%`
- `HA Font 115%`
- `HA Font 120%`
- `HA Font 125%`
- `HA Font 130%`
- `HA Font 140%`
- `HA Font 150%`

Each theme only sets `ha-font-size-scale` in both light and dark modes, so Home Assistant uses the default light/dark bases and still shows the Auto/Light/Dark selector.

## Install

Install this repository in HACS as a custom repository of type **Integration**.

After HACS downloads the integration:

1. Restart Home Assistant.
2. Go to **Settings > Devices & services > Add integration**.
3. Add **Home Assistant Utils**.
4. The integration copies bundled resources into `/config` using copy-if-missing.

If HACS says it will install to `/config/custom_components/ha_utils`, that is expected for this project. The integration then copies bundled resources to their real destinations, such as `/config/themes`, when Home Assistant sets it up.

## Required HA Theme Config

For Home Assistant to load copied theme files, make sure `/config/configuration.yaml` contains:

```yaml
frontend:
  themes: !include_dir_merge_named themes
```

Restart Home Assistant once after adding this include. If the include already exists, use **Developer tools > YAML > Reload themes** after installing/updating HA Utils.

## Use The Font Theme

1. Reload themes or restart Home Assistant after the theme file is copied.
2. Open your profile/theme selector.
3. Choose one of the `HA Font ...` themes, for example `HA Font 120%`.

This works in the web UI and Companion App because it uses Home Assistant's normal theme system.

## Automation Blueprints

The integration also deploys these automation blueprints:

- `HA Utils - High wind alert`
- `HA Utils - Hot day alert`
- `HA Utils - Cold day alert`
- `HA Utils - Possible thunderstorm alert`

After install, find them in **Settings > Automations & scenes > Blueprints**.

Each blueprint lets you choose the relevant sensor/weather entity, thresholds or conditions, cooldown, and the actions to run.

## Deploy Policy

Bundled resources are **copy-if-missing only**. Existing files in `/config` are never overwritten.

Run **Developer tools > Actions > `ha_utils.deploy_bundled`** to copy any bundled files that are missing.

## Planned Resource Types

This integration is intended to grow into a small HA utility package. Future bundled resources can be added under:

- `custom_components/ha_utils/bundled/themes/`
- `custom_components/ha_utils/bundled/packages/`
- `custom_components/ha_utils/bundled/blueprints/`

The deployer mirrors that folder structure into `/config`.

## Notes

- Home Assistant's primary/accent color pickers are special to the built-in `Home Assistant` theme. Custom themes can define colors in YAML, but they cannot keep those color picker controls.
- If you previously tested `ha_utils_typography`, delete `/config/themes/ha_utils_typography.yaml`; it used scale `1` and will not increase font size.

## Local Development

```bash
make test
```
