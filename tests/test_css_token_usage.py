"""Guardrail tests that pin CSS token usage to prevent visual regressions.

These tests are intentionally lightweight and file-based so they run in CI
without a browser.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STYLES_DIR = REPO_ROOT / "styles"
HEX_ALLOWLIST_PATH = REPO_ROOT / "tests" / "baselines" / "css_hex_allowlist.json"
IMPORTANT_BASELINE_PATH = REPO_ROOT / "tests" / "baselines" / "css_important_baseline.json"
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\\b")
ROOT_BLOCK_RE = re.compile(r":root\\s*\{(?P<body>.*?)\}", re.DOTALL)
CUSTOM_PROP_DEF_RE = re.compile(r"--[a-z0-9-]+\\s*:", re.IGNORECASE)


def _style_files() -> list[Path]:
    return sorted(path for path in STYLES_DIR.glob("*.py") if path.is_file())


def _repo_relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _extract_hex_colors(path: Path) -> set[str]:
    return {value.upper() for value in HEX_COLOR_RE.findall(path.read_text(encoding="utf-8"))}


def _extract_important_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("!important")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_non_token_styles_only_use_allowlisted_raw_hex_colors() -> None:
    """Raw hex values are banned outside tokens unless explicitly allowlisted."""
    allowlist: dict[str, list[str]] = _load_json(HEX_ALLOWLIST_PATH)
    normalized_allowlist = {
        style_path: {hex_value.upper() for hex_value in hex_values}
        for style_path, hex_values in allowlist.items()
    }

    violations: list[str] = []
    for file_path in _style_files():
        repo_path = _repo_relative(file_path)
        if repo_path == "styles/_tokens.py":
            continue

        discovered = _extract_hex_colors(file_path)
        if not discovered:
            continue

        allowed = normalized_allowlist.get(repo_path, set())
        disallowed = sorted(discovered - allowed)
        if disallowed:
            violations.append(f"{repo_path}: disallowed raw hex values {disallowed}")

    assert not violations, "\n".join(violations)


def test_contrast_fix_has_no_root_token_override_definitions() -> None:
    """styles/_contrast_fix.py should not redefine global :root CSS token values."""
    source = (STYLES_DIR / "_contrast_fix.py").read_text(encoding="utf-8")
    root_blocks = ROOT_BLOCK_RE.finditer(source)

    violations = []
    for match in root_blocks:
        block_body = match.group("body")
        if CUSTOM_PROP_DEF_RE.search(block_body):
            violations.append(block_body.strip())

    assert not violations, "styles/_contrast_fix.py must not define :root custom properties"


def test_important_usage_does_not_exceed_baseline() -> None:
    """Prevent accidental escalation of !important usage across style modules."""
    baseline = _load_json(IMPORTANT_BASELINE_PATH)
    baseline_total: int = baseline["total"]
    baseline_by_file: dict[str, int] = baseline["by_file"]

    current_by_file = {
        _repo_relative(path): _extract_important_count(path)
        for path in _style_files()
    }
    current_total = sum(current_by_file.values())

    assert current_total <= baseline_total, (
        f"!important total increased from {baseline_total} to {current_total}. "
        "If intentional, update tests/baselines/css_important_baseline.json with rationale."
    )

    increases = []
    for repo_path, count in sorted(current_by_file.items()):
        baseline_count = baseline_by_file.get(repo_path, 0)
        if count > baseline_count:
            increases.append(f"{repo_path}: {baseline_count} -> {count}")

    assert not increases, (
        "!important count increased in style files:\n"
        + "\n".join(increases)
        + "\nIf intentional, update tests/baselines/css_important_baseline.json with rationale."
    )
