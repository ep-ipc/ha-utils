"""Test helpers — load integration modules without Home Assistant installed."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HA_UTILS_DIR = REPO / "custom_components" / "ha_utils"


def load_ha_utils_module(name: str):
    """Load ``ha_utils.<name>`` from custom_components without HA deps."""
    if "ha_utils" not in sys.modules:
        pkg = types.ModuleType("ha_utils")
        pkg.__path__ = [str(HA_UTILS_DIR)]  # type: ignore[attr-defined]
        sys.modules["ha_utils"] = pkg

    path = HA_UTILS_DIR / f"{name}.py"
    full_name = f"ha_utils.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module
