# Scripts

HA Utils deploys ready-to-run scripts through Home Assistant packages. Script definitions live under `bundled/packages/ha_utils/scripts/` and are loaded via `bundled/packages/ha_utils.yaml`.

See [Deploy](deploy.md) for the copy rules and package conventions.

## Deployed location

```
/config/packages/ha_utils.yaml
/config/packages/ha_utils/scripts/
```

Bundled source:

```
custom_components/ha_utils/bundled/packages/ha_utils.yaml
custom_components/ha_utils/bundled/packages/ha_utils/scripts/
```

The package entry file wires scripts with `!include`:

```yaml
script: !include ha_utils/scripts/expose_all_to_voice_assistant.yaml
```

## Prerequisites

Add to `/config/configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant once after adding this include. If it already exists, use **Developer tools → YAML → Reload scripts** after package files are copied.

See [Install](install.md).

## Bundled scripts

### Expose all to voice assistant

**Settings → Automations & scenes → Scripts → HA Utils - Expose all to voice assistant**

Entity: `script.ha_utils_expose_all_to_voice_assistant`

File: `expose_all_to_voice_assistant.yaml`

Home Assistant makes it easy to unexpose entities you do not want in Assist, but there is no built-in way to expose everything at once. This script exposes all currently unexposed entities to Assist.

The script YAML does not contain exposure logic. It calls the integration service:

```yaml
action: ha_utils.expose_entities_to_voice_assistant
data:
  assistants:
    - conversation
```

That service is implemented in `custom_components/ha_utils/voice.py` and uses Home Assistant's `async_expose_entity` API. Because `entity_ids` is omitted, all currently **unexposed** entities are exposed to Assist (`conversation`). Already-exposed entities are skipped.

Unexpose individual entities later in **Settings → Voice assistants → Expose entities** if needed.

## Related integration action

**Settings → Developer tools → Actions → `ha_utils.expose_entities_to_voice_assistant`**

Use this when you want more control than the bundled script.

| Field | Default | Behavior |
|-------|---------|----------|
| `entity_ids` | empty | Empty = all unexposed entities; set values to expose only selected entities |
| `assistants` | `conversation` | Also supports `cloud.alexa` and `cloud.google_assistant` when available |

Behavior:

- If entities are selected, expose only those entities.
- If no entities are selected, expose all currently unexposed entities.
- Already exposed entities are skipped.

Home Assistant's action form does not support dynamic filtering of already-exposed entities or select-all/unselect-all buttons for custom service fields. The integration handles filtering on the server side.

## Implementation

| Layer | Location | Role |
|-------|----------|------|
| Script | `custom_components/ha_utils/bundled/packages/ha_utils/scripts/expose_all_to_voice_assistant.yaml` | Triggers the service |
| Service | `custom_components/ha_utils/services.py` | Registers `ha_utils.expose_entities_to_voice_assistant` |
| Logic | `custom_components/ha_utils/voice.py` | Loops entities and calls `async_expose_entity` |

## Adding scripts

1. Add `bundled/packages/ha_utils/scripts/my_script.yaml`.
2. Reference it from `bundled/packages/ha_utils.yaml`.
3. Run deploy — see [Deploy](deploy.md).
4. Reload scripts or restart Home Assistant.
