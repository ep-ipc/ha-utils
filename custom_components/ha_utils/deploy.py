"""Copy bundled Home Assistant resources into /config."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .const import BUNDLE_VERSION, MARKER_FILE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeployResult:
    """Outcome of deploying bundled resources."""

    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _bundled_root() -> Path:
    return Path(__file__).resolve().parent / "bundled"


def deploy_bundled_assets(hass: HomeAssistant) -> DeployResult:
    """Copy bundled files into the HA config directory.

    Bundled paths intentionally mirror the Home Assistant config tree, e.g.:
    bundled/themes/foo.yaml -> /config/themes/foo.yaml
    bundled/packages/foo.yaml -> /config/packages/foo.yaml
    bundled/blueprints/... -> /config/blueprints/...
    """
    result = DeployResult()
    bundled = _bundled_root()
    config_dir = Path(hass.config.config_dir)

    if not bundled.is_dir():
        result.errors.append(f"Bundled resources not found: {bundled}")
        return result

    for src in sorted(bundled.rglob("*")):
        if not src.is_file():
            continue

        rel = src.relative_to(bundled)
        rel_str = rel.as_posix()
        dest = config_dir / rel

        if dest.exists():
            result.skipped.append(rel_str)
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            result.copied.append(rel_str)
            _LOGGER.info("Deployed bundled resource: %s", rel_str)
        except OSError as err:
            msg = f"{rel_str}: {err}"
            result.errors.append(msg)
            _LOGGER.error("Failed to deploy %s: %s", rel_str, err)

    _write_marker(config_dir, result)
    return result


def _write_marker(config_dir: Path, result: DeployResult) -> None:
    marker_path = config_dir / MARKER_FILE
    payload: dict[str, object] = {
        "version": BUNDLE_VERSION,
        "deployed_at": datetime.now(UTC).isoformat(),
        "copied": result.copied,
        "skipped": result.skipped,
    }

    try:
        marker_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as err:
        _LOGGER.warning("Could not write deploy marker %s: %s", marker_path, err)
