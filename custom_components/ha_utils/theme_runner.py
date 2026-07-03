"""Run theme patch with path discovery for Home Assistant."""

from __future__ import annotations

from pathlib import Path

from .theme_paths import discover_theme_sources, read_configuration_text
from .theme_patcher import PatchResult, patch_theme_sources


def run_patch_themes(
    config_dir: Path,
    *,
    scale: float | int,
    line_height: float | int,
    dry_run: bool,
    themes_dir_override: str | None = None,
) -> tuple[PatchResult, list[Path]]:
    """Discover theme locations and patch them."""
    if themes_dir_override:
        override = Path(themes_dir_override)
        if not override.is_absolute():
            override = (config_dir / override).resolve()
        else:
            override = override.resolve()
        sources = [override]
    else:
        configuration_text = read_configuration_text(config_dir)
        sources = discover_theme_sources(config_dir, configuration_text)

    result = patch_theme_sources(
        sources,
        scale=scale,
        line_height=line_height,
        dry_run=dry_run,
    )
    return result, sources
