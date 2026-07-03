# Home Assistant Utils

Small HACS custom integration for changing the **default Home Assistant theme font size** from **Settings > Developer tools > Actions**.

This project currently does one thing:

- Registers the action `ha_utils.set_font_scale`
- Loads a small frontend module
- Stores the selected scale in Home Assistant frontend system storage
- Applies `--ha-font-size-scale` at runtime on every frontend page load

No `/config/themes` folder or custom theme YAML is required.

## Install

1. Install via HACS as a custom repository, or copy `custom_components/ha_utils` into `/config/custom_components/`
2. Restart Home Assistant
3. Go to **Settings > Devices & services > Add integration > Home Assistant Utils**

## Use

Open **Settings > Developer tools > Actions**.

Run:

- Action: `ha_utils.set_font_scale`
- `scale`: `1.2`

Refresh the browser tab or reload the HA app if the change is not immediately visible.

## Action

### `ha_utils.set_font_scale`

| Field | Description |
|-------|-------------|
| `scale` | Multiplier for Home Assistant font-size tokens. Default: `1.0`; range: `0.5` to `2.5`. |

## Local Development

```bash
make test
```

## Current Scope

Included:

- HACS custom integration
- Config flow
- Developer Tools action
- Runtime frontend font scaling for the default HA theme
- Minimal tests for runtime scale payloads

Removed from scope for now:

- Custom theme YAML patching
- Theme path discovery
- `frontend.reload_themes` wrapper action
- Bundle deployment for packages/blueprints
- Repair issues for `packages:`
- Local CLI for patching theme files
