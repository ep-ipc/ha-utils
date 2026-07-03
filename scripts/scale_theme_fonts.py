"""CLI for scaling theme typography (dev / local maintenance).

Uses the same logic as the ha_utils integration action ``patch_themes``.
Defaults to dry run. Pass ``--apply`` to write theme files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
if str(_REPO_ROOT / "custom_components") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "custom_components"))

from env import get_font_scale  # noqa: E402
from ha_utils.theme_patcher import (  # noqa: E402
    DEFAULT_LINE_HEIGHT,
    patch_all_themes,
)

DEFAULT_THEMES_DIR = _REPO_ROOT / "themes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scale HA + Mushroom typography across theme YAML files",
    )
    parser.add_argument(
        "--themes-dir",
        type=Path,
        default=DEFAULT_THEMES_DIR,
        help=f"Root themes folder (default: {DEFAULT_THEMES_DIR})",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=get_font_scale(),
        help="ha-font-size-scale multiplier",
    )
    parser.add_argument(
        "--line-height",
        type=float,
        default=DEFAULT_LINE_HEIGHT,
        dest="line_height",
        help="ha-line-height-normal value",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: dry run)",
    )
    args = parser.parse_args(argv)

    result = patch_all_themes(
        args.themes_dir,
        scale=args.scale,
        line_height=args.line_height,
        dry_run=not args.apply,
    )

    if result.errors:
        for err in result.errors:
            print(f"Error: {err}", file=sys.stderr)
        return 1

    targets = result.would_change if not args.apply else result.changed
    if not targets:
        print("All theme files already match the target typography settings.")
        return 0

    label = "would patch" if not args.apply else "patched"
    for rel in targets:
        print(f"  {label}: {rel}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write.")
    else:
        print(f"\nUpdated {len(result.changed)} theme file(s).")
        print(
            "Restart Home Assistant or run ha_utils.reload_themes to apply."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
