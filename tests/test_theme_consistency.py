"""Catch drift between ui_theme.py Python constants and styles/_tokens.py CSS.

Both files encode the same brand palette in different shapes: Python constants
for Plotly / iframe-embedded HTML, CSS variables for the main stylesheet.
When they drift (e.g. a brand hex updated in one but not the other) Plotly
charts go out of sync with the rest of the UI. This test pins the mapping so
CI catches accidental drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import ui_theme
from styles import _tokens

REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_tokens(css: str, scope_selector: str) -> dict[str, str]:
    """Return {token_name: hex_value} for one :root{...} block in TOKEN_SYSTEM."""
    pattern = re.compile(
        re.escape(scope_selector) + r"\s*\{([^}]*)\}", re.DOTALL
    )
    match = pattern.search(css)
    if not match:
        raise AssertionError(f"scope {scope_selector!r} not found in TOKEN_SYSTEM")
    body = match.group(1)
    decls = re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", body)
    return {name: value.strip() for name, value in decls}


@pytest.fixture(scope="module")
def light_tokens() -> dict[str, str]:
    return _extract_tokens(_tokens.TOKEN_SYSTEM, ":root")


# Pairs: (ui_theme attribute, CSS custom-property name)
PALETTE_PAIRS = [
    ("BRAND_PRIMARY", "--brand"),
    ("BRAND_DARK", "--brand-dark"),
    ("BRAND_LIGHT", "--brand-light"),
    ("BRAND_SOFT", "--brand-soft"),
    ("SURFACE_BASE", "--surface"),
    ("SURFACE_ELEVATED", "--surface-elevated"),
    ("SURFACE_RAISED", "--surface-raised"),
    ("TEXT_PRIMARY", "--text"),
    ("TEXT_SECONDARY", "--text-secondary"),
    ("TEXT_MUTED", "--text-muted"),
    ("BORDER_SUBTLE", "--border-subtle"),
    ("BORDER_MEDIUM", "--border-medium"),
]


@pytest.mark.parametrize("attr,token", PALETTE_PAIRS)
def test_ui_theme_matches_css_token(attr, token, light_tokens):
    py_value = getattr(ui_theme, attr).upper()
    css_value = light_tokens[token].upper()
    assert py_value == css_value, (
        f"{attr} = {py_value} but {token} = {css_value} "
        "(drift between ui_theme.py and styles/_tokens.py)"
    )


def _read_file(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "tab_file,required_classes",
    [
        (
            "tabs/upload_tab.py",
            [
                "tab-upload-mobile-filters",
                "tab-upload-mobile-primary-action",
                "mobile-layout-secondary",
            ],
        ),
        (
            "tabs/report_tab.py",
            [
                "tab-report-mobile-filters",
                "tab-report-mobile-kpis",
                "tab-report-mobile-secondary",
                "tab-report-mobile-primary-action",
            ],
        ),
        (
            "tabs/analytics_tab.py",
            [
                "tab-analytics-mobile-filters",
                "tab-analytics-mobile-sections",
                "tab-analytics-mobile-secondary",
            ],
        ),
        (
            "tabs/settings_tab.py",
            [
                "tab-settings-mobile-filters",
                "tab-settings-mobile-export-filters",
                "tab-settings-mobile-primary-action",
            ],
        ),
    ],
)
def test_mobile_wrapper_classes_present(tab_file: str, required_classes: list[str]) -> None:
    """Prevent responsive wrapper regressions in tab layouts."""
    source = _read_file(tab_file)
    missing = [cls for cls in required_classes if cls not in source]
    assert not missing, f"missing responsive wrapper class hooks in {tab_file}: {missing}"


def test_responsive_css_uses_explicit_mobile_layout_hooks() -> None:
    """Ensure responsive stacking relies on explicit wrappers, not broad selectors."""
    css = _read_file("styles/_responsive.py")
    assert "mobile-layout-stack" in css
    assert "mobile-layout-filters" in css
    assert "mobile-layout-primary-action" in css
    assert "mobile-layout-secondary" in css
    assert ":has([data-testid=" not in css, "remove selector-driven mobile inference rules"
