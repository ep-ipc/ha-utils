"""Constants for Home Assistant Utils."""

from __future__ import annotations

DOMAIN = "ha_utils"
NAME = "Home Assistant Utils"

BUNDLE_VERSION = "1.0.0"
MARKER_FILE = ".ha_utils_deployed"

# User and developer docs for each signal device.
DOCS_DEVICES = "https://github.com/ep-ipc/ha-utils/blob/main/docs/devices"

# Forecast conditions Bad weather can watch, and the ones it watches by default.
STORM_DEFAULT = ["lightning", "lightning-rainy", "pouring", "rainy"]
STORM_OPTIONS = [*STORM_DEFAULT, "hail", "windy", "windy-variant"]
