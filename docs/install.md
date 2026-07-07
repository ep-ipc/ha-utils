# Install

HA Utils is a HACS custom integration. It installs into `/config/custom_components/ha_utils` and deploys bundled resources (themes, packages, blueprints) into your Home Assistant config directory.

## HACS install

1. Add this repository to HACS as a custom repository of type **Integration**.
2. Install **Home Assistant Utils** from HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Add **Home Assistant Utils**.

On first setup, the integration copies bundled resources into `/config` using [copy-if-missing deploy](deploy.md).

If HACS says it will install to `/config/custom_components/ha_utils`, that is expected. The integration then mirrors bundled files to their real destinations, such as `/config/themes` and `/config/packages`.

## Required configuration

Deploy copies files only. Home Assistant still needs the correct includes in `/config/configuration.yaml`.

### Themes

```yaml
frontend:
  themes: !include_dir_merge_named themes
```

Restart Home Assistant once after adding this include. If it already exists, use **Developer tools → YAML → Reload themes** after installing or updating HA Utils.

See [Themes](themes.md).

### Packages

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant once after adding this include. If it already exists, use **Developer tools → YAML → Reload scripts** after the package files are copied.

Required for bundled [scripts](scripts.md).

## After install

| Resource | Where to find it |
|----------|------------------|
| Font themes | Profile / theme selector |
| Weather blueprints | **Settings → Automations & scenes → Blueprints** |
| Expose-all script | **Settings → Automations & scenes → Scripts** |
| Deploy action | **Settings → Developer tools → Actions → `ha_utils.deploy_bundled`** |
| Voice exposure action | **Settings → Developer tools → Actions → `ha_utils.expose_entities_to_voice_assistant`** |

## Troubleshooting

| Issue | What to do |
|-------|------------|
| HACS: `No manifest.json` / `custom_components/None` | Re-add as **Integration**; remove stale HACS cache entry |
| HACS: `No content to download` | Install from a GitHub **release** tag, not a raw commit hash |
| Themes not listed | Confirm `frontend.themes` include; reload themes or restart |
| Script not listed | Confirm `homeassistant.packages` include; reload scripts or restart |
| Old test theme still visible | Delete `/config/themes/ha_utils_typography.yaml` and reload themes |

## Local development

```bash
make test
```
