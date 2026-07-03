"""Apply global Home Assistant typography variables to theme YAML files.

Ported from ha-helper ``scripts/scale_theme_fonts.py``. Besides
``ha-font-size-scale`` and ``ha-line-height-normal``, the patcher:

- Rewrites fixed ``ha-font-size-*`` / ``title-font-size`` pixel overrides so
  they use ``calc(... * var(--ha-font-size-scale))``.
- Maps Mushroom card font theme keys to scaled token/HA variables.
- Scales ``--text-divider-font-size`` inside card-mod CSS when present.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LINE_HEIGHT = 1.8

FONT_SCALE_KEY = "ha-font-size-scale"
LINE_HEIGHT_KEY = "ha-line-height-normal"

MUSHROOM_FONT_KEYS_TOKEN: list[tuple[str, str]] = [
    ("mush-card-primary-font-size", "token-size-font-l"),
    ("mush-card-secondary-font-size", "token-size-font-m"),
    ("mush-subtitle-font-size", "token-size-font-s"),
    ("mush-chip-font-size", "token-size-font-s"),
    ("mush-title-font-size", "token-size-font-2xl"),
]

MUSHROOM_FONT_KEYS_HA: list[tuple[str, str]] = [
    ("mush-card-primary-font-size", "ha-font-size-l"),
    ("mush-card-secondary-font-size", "ha-font-size-m"),
    ("mush-subtitle-font-size", "ha-font-size-s"),
    ("mush-chip-font-size", "ha-font-size-s"),
    ("mush-title-font-size", "ha-font-size-2xl"),
]

_SCALE_LINE = re.compile(
    rf"^(\s*){re.escape(FONT_SCALE_KEY)}:\s*.*$",
    re.MULTILINE,
)
_LINE_HEIGHT_LINE = re.compile(
    rf"^(\s*){re.escape(LINE_HEIGHT_KEY)}:\s*.*$",
    re.MULTILINE,
)
_CARD_MOD_THEME = re.compile(r"^\s*card-mod-theme:\s*")
_FIXED_HA_FONT = re.compile(
    r"^(\s*)(ha-font-size-(?:2xs|xs|s|m|l|xl|2xl|3xl|4xl|5xl)):\s*"
    r"['\"](\d+(?:\.\d+)?)px['\"]\s*$",
    re.MULTILINE,
)
_FIXED_TITLE_FONT = re.compile(
    r"^(\s*)(title-font-size):\s*['\"](\d+(?:\.\d+)?)px['\"]\s*$",
    re.MULTILINE,
)
_TEXT_DIVIDER_FONT = re.compile(
    r"(--text-divider-font-size:\s*)(\d+(?:\.\d+)?)px(\s*!important)?",
)
_MUSHROOM_FONT_LINE = re.compile(
    r"^(\s*)(mush-(?:card-primary|card-secondary|subtitle|chip|title)-font-size):\s*.*$",
    re.MULTILINE,
)
_MUSH_TITLE_LINE = re.compile(r"^(\s*)mush-title-font-size:\s*.*$", re.MULTILINE)


@dataclass
class PatchResult:
    """Outcome of patching one or more theme files."""

    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    would_change: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _yaml_number(value: float | int) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _font_lines(indent: str, scale: float | int, line_height: float | int) -> str:
    return (
        f"{indent}{FONT_SCALE_KEY}: {_yaml_number(scale)}\n"
        f"{indent}{LINE_HEIGHT_KEY}: {_yaml_number(line_height)}\n"
    )


def _set_or_update_key(text: str, key: str, value: float | int) -> str:
    pattern = _SCALE_LINE if key == FONT_SCALE_KEY else _LINE_HEIGHT_LINE
    replacement = f"\\g<1>{key}: {_yaml_number(value)}"
    return pattern.sub(replacement, text)


def _insert_after_card_mod_theme(
    text: str, scale: float | int, line_height: float | int
) -> str:
    lines = text.splitlines(keepends=True)
    if not lines and not text:
        return text

    out: list[str] = []
    lookahead = 8

    for i, line in enumerate(lines):
        out.append(line)
        if not _CARD_MOD_THEME.match(line):
            continue
        window = "".join(lines[i + 1 : i + 1 + lookahead])
        if FONT_SCALE_KEY in window or LINE_HEIGHT_KEY in window:
            continue
        indent_match = re.match(r"^(\s*)", line)
        indent = indent_match.group(1) if indent_match else "  "
        out.append(_font_lines(indent, scale, line_height))

    return "".join(out)


def _convert_fixed_font_sizes(text: str) -> str:
    def ha_repl(match: re.Match[str]) -> str:
        indent, key, px = match.groups()
        return f"{indent}{key}: 'calc({px}px * var(--ha-font-size-scale))'"

    def title_repl(match: re.Match[str]) -> str:
        indent, key, px = match.groups()
        return f"{indent}{key}: 'calc({px}px * var(--ha-font-size-scale))'"

    text = _FIXED_HA_FONT.sub(ha_repl, text)
    return _FIXED_TITLE_FONT.sub(title_repl, text)


def _convert_text_divider_font_size(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix, px, important = match.groups()
        suffix = important or ""
        if "var(--ha-font-size-scale)" in match.group(0):
            return match.group(0)
        return f"{prefix}calc({px}px * var(--ha-font-size-scale)){suffix}"

    return _TEXT_DIVIDER_FONT.sub(repl, text)


def _uses_token_fonts(text: str) -> bool:
    return "--token-size-font-m" in text


def _mushroom_targets(text: str) -> list[tuple[str, str]]:
    if _uses_token_fonts(text):
        return [
            (key, f"var(--{token})")
            for key, token in MUSHROOM_FONT_KEYS_TOKEN
        ]
    return [
        (key, f"var(--{ha_key})")
        for key, ha_key in MUSHROOM_FONT_KEYS_HA
    ]


def _has_theme_key(text: str, key: str) -> bool:
    return bool(re.search(rf"^\s*{re.escape(key)}:", text, re.MULTILINE))


def _insert_missing_lines_after(
    lines: list[str],
    *,
    match_line: re.Pattern[str],
    targets: dict[str, str],
    present: set[str],
) -> tuple[list[str], set[str]]:
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        match = match_line.match(line)
        if not match:
            continue
        indent = match.group(1)
        window = "".join(lines[i + 1 : i + 1 + 14])
        for key, value in targets.items():
            if key in present or f"{key}:" in window:
                continue
            out.append(f"{indent}{key}: '{value}'\n")
            present.add(key)
    return out, present


def _update_mushroom_font_keys(text: str) -> str:
    targets = {key: value for key, value in _mushroom_targets(text)}

    def line_repl(match: re.Match[str]) -> str:
        indent, key = match.groups()
        if key not in targets:
            return match.group(0)
        return f"{indent}{key}: '{targets[key]}'"

    text = _MUSHROOM_FONT_LINE.sub(line_repl, text)
    present = {key for key in targets if _has_theme_key(text, key)}
    if present == set(targets):
        return text

    lines = text.splitlines(keepends=True)
    lines, present = _insert_missing_lines_after(
        lines,
        match_line=_MUSH_TITLE_LINE,
        targets=targets,
        present=present,
    )
    lines, present = _insert_missing_lines_after(
        lines,
        match_line=_SCALE_LINE,
        targets=targets,
        present=present,
    )

    still_missing = [key for key in targets if key not in present]
    if still_missing:
        joined = "".join(lines)
        indent = "  "
        for line in reversed(lines):
            if "card-mod-theme:" in line:
                indent_match = re.match(r"^(\s*)", line)
                if indent_match:
                    indent = indent_match.group(1) + "  "
                break
        for key in still_missing:
            joined += f"{indent}{key}: '{targets[key]}'\n"
        return joined

    return "".join(lines)


def apply_typography_patches(
    text: str,
    *,
    scale: float | int,
    line_height: float | int,
) -> str:
    """Return theme YAML with typography patches applied."""
    updated = _set_or_update_key(text, FONT_SCALE_KEY, scale)
    updated = _set_or_update_key(updated, LINE_HEIGHT_KEY, line_height)
    updated = _insert_after_card_mod_theme(updated, scale, line_height)
    updated = _convert_fixed_font_sizes(updated)
    updated = _convert_text_divider_font_size(updated)
    updated = _update_mushroom_font_keys(updated)
    return updated


def patch_theme_file(
    path: Path,
    *,
    scale: float | int,
    line_height: float | int,
    dry_run: bool = False,
) -> bool:
    """Patch a single theme file. Returns True if content would change or did change."""
    original = path.read_text(encoding="utf-8")
    updated = apply_typography_patches(original, scale=scale, line_height=line_height)
    if updated == original:
        return False

    if dry_run:
        return True

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    return True


def discover_theme_files(themes_dir: Path) -> list[Path]:
    """List theme YAML files under ``themes_dir``."""
    if not themes_dir.is_dir():
        raise FileNotFoundError(f"Themes directory not found: {themes_dir}")
    return sorted(themes_dir.rglob("*.yaml"))


def patch_all_themes(
    themes_dir: Path,
    *,
    scale: float | int,
    line_height: float | int = DEFAULT_LINE_HEIGHT,
    dry_run: bool = False,
) -> PatchResult:
    """Patch every theme YAML under ``themes_dir``."""
    result = PatchResult()
    try:
        theme_files = discover_theme_files(themes_dir)
    except FileNotFoundError as err:
        result.errors.append(str(err))
        return result

    if not theme_files:
        result.errors.append(f"No theme YAML files under {themes_dir}")
        return result

    for path in theme_files:
        rel = str(path.relative_to(themes_dir))
        try:
            original = path.read_text(encoding="utf-8")
            updated = apply_typography_patches(
                original, scale=scale, line_height=line_height
            )
            if updated == original:
                result.unchanged.append(rel)
                continue
            if dry_run:
                result.would_change.append(rel)
                continue
            if patch_theme_file(
                path, scale=scale, line_height=line_height, dry_run=False
            ):
                result.changed.append(rel)
        except OSError as err:
            result.errors.append(f"{rel}: {err}")

    return result
