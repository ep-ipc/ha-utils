# HA Utils — Font Scale Theme Pack

Current plan for the simplified repository.

---

## Current Goal

Provide Home Assistant themes that increase the default UI font size without running any custom integration code.

Users choose the font size through Home Assistant's normal theme selector:

- `HA Utils Default Font 100%`
- `HA Utils Default Font 110%`
- `HA Utils Default Font 115%`
- `HA Utils Default Font 120%`
- `HA Utils Default Font 125%`
- `HA Utils Default Font 130%`
- `HA Utils Default Font 140%`
- `HA Utils Default Font 150%`

Each theme only sets `ha-font-size-scale`; all other values fall back to Home Assistant's built-in default theme.

---

## Current Tracker

| Area | Status |
|------|--------|
| Theme YAML file | Done |
| Multiple selectable font sizes | Done |
| No custom integration/runtime JS/actions | Done |
| README/docs for theme-only install | Done |
| Theme-pack validation test | Done |

---

## Repository Layout

```text
ha-utils/
├── themes/
│   └── ha_utils_font_scale.yaml
├── tests/
│   └── test_theme_pack.py
├── docs/
│   └── PLAN.md
├── Makefile
├── hacs.json
└── README.md
```

---

## Install/Test Flow

1. Install through HACS as a custom repository of type **Theme**. HACS copies `themes/ha_utils_font_scale.yaml` to `/config/themes/` automatically.
   - Manual fallback: copy `themes/ha_utils_font_scale.yaml` to `/config/themes/`.
2. Ensure `/config/configuration.yaml` contains:

   ```yaml
   frontend:
     themes: !include_dir_merge_named themes
   ```

3. Restart Home Assistant once after enabling themes.
4. Select a theme such as `HA Utils Default Font 120%` from the HA theme selector.
5. Test in both web and Companion App.

If upgrading from the old integration, delete `/config/themes/ha_utils_typography.yaml` and reload themes. That old theme used scale `1` and will not increase font size.

---

## What Remains From The Original Plan

Still present:

- A reusable Home Assistant utility repo
- HACS-compatible metadata
- Theme-based default UI font scaling
- Documentation and tests

Removed:

- Custom integration under `custom_components/`
- Config flow
- Developer Tools actions/services
- Runtime frontend JavaScript
- Frontend system storage
- Package deployment
- Repair issues
- Blueprint deployment
- Custom theme patching logic
- Local theme patching CLI

To add later:

- Blueprints
- Automations
- Optional helpers/scripts if we decide a dynamic numeric font-size control is worth the extra complexity
