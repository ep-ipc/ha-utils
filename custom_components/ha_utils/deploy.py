"""Deploy bundled packages and blueprints into the HA config directory."""

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
    """Outcome of deploying bundled assets."""

    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    package_copied: bool = False


def _bundled_root() -> Path:
    return Path(__file__).resolve().parent / "bundled"


def deploy_bundled_assets(hass: HomeAssistant) -> DeployResult:
    """Copy bundled files into the config directory (copy-if-missing only)."""
    result = DeployResult()
    bundled = _bundled_root()
    config_dir = Path(hass.config.config_dir)

    if not bundled.is_dir():
        result.errors.append(f"Bundled assets not found: {bundled}")
        return result

    for src in sorted(bundled.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(bundled)
        dest = config_dir / rel
        rel_str = str(rel).replace("\\", "/")

        if dest.exists():
            result.skipped.append(rel_str)
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            result.copied.append(rel_str)
            if rel_str == "packages/ha_utils.yaml":
                result.package_copied = True
            _LOGGER.info("Deployed bundled file: %s", rel_str)
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
    if marker_path.is_file():
        try:
            existing = json.loads(marker_path.read_text(encoding="utf-8"))
            prior_copied = existing.get("copied", [])
            if isinstance(prior_copied, list):
                merged = list(dict.fromkeys([*prior_copied, *result.copied]))
                payload["copied"] = merged
        except (json.JSONDecodeError, OSError):
            pass

    try:
        marker_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as err:
        _LOGGER.warning("Could not write deploy marker %s: %s", marker_path, err)
