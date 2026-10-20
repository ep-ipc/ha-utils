# Agent guide

Rules for changing Home Assistant Utils. User-facing behavior lives under [docs/](docs/README.md). Update those docs when behavior changes.

## What this integration is

One config entry, `ha_utils`. Optional subentries publish entities an automation can trigger on. The entry does not run actions, move covers, or call scenes.

Current subentries:

| Type | Device | Doc | Publishes |
|---|---|---|---|
| `wind_signal` | Wind | [docs/devices/wind.md](docs/devices/wind.md) | Level (`safe`, `advisory`, `warning`), Risk, Calm, Gust factor, Guide |
| `temperature` | Temperature | [docs/devices/temperature.md](docs/devices/temperature.md) | Temperature, Hot, Cold, Guide |
| `bad_weather` | Bad weather | [docs/devices/bad-weather.md](docs/devices/bad-weather.md) | Condition, Bad weather, Reason, Guide |

Wind is a generic wind reading. Do not name it for shades or any other device. Wind rise and fall lines are the user's thresholds, default 30 / 60 / 45 / 20 in the gust sensor's speed unit. Hot and cold default to 90 and 32. Bad weather conditions default to lightning, lightning-rainy, pouring, and rainy.

Weather alerts are signal devices, not blueprints. The only bundled blueprint is the control-all script.

## Documentation standard

- One device → one file under `docs/devices/`.
- Overview stays in `docs/signals.md` and `docs/devices/README.md`.
- Device docs use the same section order: **What it publishes**, **How it decides / Level moves**, **Automations**.
- Every signal device exposes a diagnostic **Guide** entity and a `configuration_url` pointing at its doc (`DOCS_DEVICES` in `const.py`).
- Wind Guide must show both rise and fall ladders with the live threshold numbers, plus a short how-to for watching Level in automations. Keep house-specific shade mapping on the house dashboard, not in the integration Guide.
- When you change thresholds, levels, merge rules, or published entities, update the device doc and Guide text in the same change.

## Signal rules

- A fresh local station (reported in the last 15 minutes) is the live value. The forecast is the fallback and an early warning.
- The forecast may turn Hot, Cold, or Bad weather on. It must not turn them off while the live station is still past the line. For wind, a calm forecast must not pull a live gust down.
- Forecast look-ahead is the next 2 hours. Bad weather can be on while Condition is still `sunny`.
- If the station is missing, use the forecast. Temperature and Bad weather may set the station to `none`.
- Do not list a signal's own entities in its source selectors.
- Wind Level strings are `safe` / `advisory` / `warning`. Map legacy stored `big` → `advisory` and `all` → `warning` on import.
- When Bad weather's decision changes, set the Reason entity to one readable sentence and write that sentence to the activity log with `async_log_entry`. The state-change row will still say that no cause was recorded.

Math that does not need Home Assistant belongs in `logic.py`. Test it from `tests/test_signals.py`. Config/docs/bundled contracts live in `tests/test_contracts.py`. Deploy and voice helpers live in `tests/test_theme_pack.py`. Run `make test` before releasing.

## Home Assistant wiring

- Device-page settings are entities with `EntityCategory.CONFIG`: selects for sources, numbers for wind rise/fall and hot/cold. Diagnostic **Guide** uses `EntityCategory.DIAGNOSTIC`.
- Shared `DeviceInfo` comes from `device_meta.signal_device_info` so every platform attaches the same docs URL.
- Changing a source or a threshold updates the subentry and reloads the entry. Drop the cached runtime on unload so the next setup reads the new data.
- Bus listeners that write state must be `@callback` and stay on the event loop. `async_call_later` callbacks that touch `hass` must be `@callback` too.
- Source lists update after entities appear. Do not snapshot options only at startup.
- Entities use `has_entity_name` and the subentry device. Stable `unique_id` values are `{subentry_id}_{key}`.

## Releases

HACS installs GitHub releases, not raw `main`. The `version` in `custom_components/ha_utils/manifest.json` must match the release tag and must not go backwards.

Ship integration changes as a new patch or minor release: commit, push `main`, then `gh release create`. Docs-only changes go to `main` and do not need a release when no code changed. If docs ship with a Guide or URL change, include them in that release.

## Commits

Do not add a co-author trailer. A commit wrapper injects `Co-authored-by: Cursor` into `git commit` and `git commit --amend`. Use `git commit-tree` and `git update-ref` instead. Do not use `--no-verify`. Do not force-push `main`.

## Live houses

Do not turn on scenes, move covers, or enable an automation that acts on devices unless the user asks. Creating or reloading a signal entry must not be an action.
