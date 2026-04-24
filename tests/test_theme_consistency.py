"""Catch drift between ui_theme.py Python constants and styles/_tokens.py CSS.

Both files encode the same brand palette in different shapes: Python constants
for Plotly / iframe-embedded HTML, CSS variables for the main stylesheet.
When they drift (e.g. a brand hex updated in one but not the other) dark mode
and Plotly charts go out of sync with the rest of the UI. This test pins the
mapping so CI catches accidental drift.
"""

from __future__ import annotations

import re

import pytest

import ui_theme
from styles import _tokens


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


@pytest.fixture(scope="module")
def dark_tokens() -> dict[str, str]:
    return _extract_tokens(_tokens.TOKEN_SYSTEM, ':root[data-theme="dark"]')


# Pairs: (ui_theme attribute, CSS custom-property name)
LIGHT_PAIRS = [
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

DARK_PAIRS = [
    # Note: dark-mode --surface / --surface-elevated swap roles vs. light
    # (--surface in dark is the "card" color, not the page bg), so those pairs
    # are intentionally omitted here. Text and border tokens map 1:1.
    ("SURFACE_RAISED_DARK", "--surface-raised"),
    ("TEXT_PRIMARY_DARK", "--text"),
    ("TEXT_SECONDARY_DARK", "--text-secondary"),
    ("TEXT_MUTED_DARK", "--text-muted"),
    ("BORDER_SUBTLE_DARK", "--border-subtle"),
    ("BORDER_MEDIUM_DARK", "--border-medium"),
]


class TestLightPalette:
    @pytest.mark.parametrize("attr,token", LIGHT_PAIRS)
    def test_ui_theme_matches_css_token(self, attr, token, light_tokens):
        py_value = getattr(ui_theme, attr).upper()
        css_value = light_tokens[token].upper()
        assert py_value == css_value, (
            f"{attr} = {py_value} but {token} = {css_value} "
            "(drift between ui_theme.py and styles/_tokens.py)"
        )


class TestDarkPalette:
    @pytest.mark.parametrize("attr,token", DARK_PAIRS)
    def test_ui_theme_matches_css_token(self, attr, token, dark_tokens):
        py_value = getattr(ui_theme, attr).upper()
        css_value = dark_tokens[token].upper()
        assert py_value == css_value, (
            f"{attr} = {py_value} but {token} (dark) = {css_value} "
            "(drift between ui_theme.py and styles/_tokens.py)"
        )
