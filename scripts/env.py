"""Load repo-root ``.env`` for maintenance scripts and Make targets.

Copy ``.env.dist`` to ``.env`` and adjust for your home.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

DEFAULTS: dict[str, str] = {
    "HA_FONT_SCALE": "1",
}

_loaded = False


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_env(*, force: bool = False) -> None:
    """Apply defaults, then override from ``.env`` if present."""
    global _loaded
    if _loaded and not force:
        return

    for key, value in DEFAULTS.items():
        os.environ.setdefault(key, value)

    if ENV_FILE.is_file():
        for key, value in _parse_env_file(ENV_FILE).items():
            os.environ[key] = value

    _loaded = True


def get_font_scale() -> float:
    load_env()
    return float(os.environ["HA_FONT_SCALE"])
