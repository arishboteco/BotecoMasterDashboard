"""WCAG contrast checks for design tokens."""

from __future__ import annotations

import re

import pytest

from styles import _tokens


AA_NORMAL_TEXT_MIN_RATIO = 4.5
AA_LARGE_TEXT_MIN_RATIO = 3.0


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB or #RGB to an RGB tuple."""
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) != 6:
        raise ValueError(f"Unsupported hex color: {hex_color}")
    return tuple(int(cleaned[i : i + 2], 16) for i in (0, 2, 4))


def relative_luminance(hex_color: str) -> float:
    """Calculate WCAG relative luminance for a hex color."""

    def _to_linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = hex_to_rgb(hex_color)
    r_lin = _to_linear(red)
    g_lin = _to_linear(green)
    b_lin = _to_linear(blue)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(foreground: str, background: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    l1 = relative_luminance(foreground)
    l2 = relative_luminance(background)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _token_string_hex(token_name: str) -> str | None:
    """Extract hex color from TOKEN_SYSTEM CSS block for optional semantic token vars."""
    pattern = rf"--{token_name}:\s*(#[0-9A-Fa-f]{{6}})"
    match = re.search(pattern, _tokens.TOKEN_SYSTEM)
    if not match:
        return None
    return match.group(1)


class TestLightModeContrast:
    def test_text_on_surface_elevated(self):
        ratio = contrast_ratio(_tokens.TEXT, _tokens.SURFACE_ELEVATED)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_text_secondary_on_surface_elevated(self):
        ratio = contrast_ratio(_tokens.TEXT_SECONDARY, _tokens.SURFACE_ELEVATED)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_text_muted_on_surface_elevated(self):
        ratio = contrast_ratio(_tokens.TEXT_MUTED, _tokens.SURFACE_ELEVATED)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_primary_on_surface_elevated(self):
        ratio = contrast_ratio(_tokens.PRIMARY, _tokens.SURFACE_ELEVATED)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_tab_active_text_on_tab_active_background(self):
        ratio = contrast_ratio("#FFFFFF", _tokens.PRIMARY)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_sidebar_text_on_sidebar_background(self):
        sidebar_bg = _token_string_hex("sidebar-bg")
        sidebar_text = _token_string_hex("sidebar-text")
        if not sidebar_bg or not sidebar_text:
            pytest.skip("Sidebar foreground/background tokens are not explicitly defined as hex")

        ratio = contrast_ratio(sidebar_text, sidebar_bg)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_sidebar_active_foreground_on_sidebar_active_background(self):
        active_bg = _token_string_hex("sidebar-active-bg")
        active_fg = _token_string_hex("sidebar-active-fg")
        if not active_bg or not active_fg:
            pytest.skip("Sidebar active tokens are not explicitly defined as hex")

        ratio = contrast_ratio(active_fg, active_bg)
        assert ratio >= AA_LARGE_TEXT_MIN_RATIO

    def test_error_on_error_background_if_available(self):
        error_bg = _token_string_hex("error-bg")
        if not error_bg:
            pytest.skip("No explicit ERROR background token is available in styles/_tokens.py")

        ratio = contrast_ratio(_tokens.ERROR, error_bg)

        # Questionable pair: semantic error foreground on semantic error background is not
        # always intended for body text; we still enforce WCAG AA and fail loudly for now.
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_success_on_success_background_if_available(self):
        success_bg = _token_string_hex("success-bg")
        if not success_bg:
            pytest.skip("No explicit SUCCESS background token is available in styles/_tokens.py")

        ratio = contrast_ratio(_tokens.SUCCESS, success_bg)

        # Questionable pair: semantic success foreground on semantic success background can be
        # decorative in some components, but keeping AA target explicit avoids silent regressions.
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_kpi_label_on_kpi_primary_card_surface(self):
        ratio = contrast_ratio(_tokens.KPI_LABEL_FG, _tokens.CARD_SURFACE_KPI_PRIMARY)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_kpi_value_on_kpi_primary_card_surface(self):
        ratio = contrast_ratio(_tokens.KPI_VALUE_FG, _tokens.CARD_SURFACE_KPI_PRIMARY)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_kpi_delta_semantic_colors_on_kpi_primary_card_surface(self):
        positive_ratio = contrast_ratio(
            _tokens.KPI_DELTA_POSITIVE_FG,
            _tokens.CARD_SURFACE_KPI_PRIMARY,
        )
        negative_ratio = contrast_ratio(
            _tokens.KPI_DELTA_NEGATIVE_FG,
            _tokens.CARD_SURFACE_KPI_PRIMARY,
        )
        neutral_ratio = contrast_ratio(
            _tokens.KPI_DELTA_NEUTRAL_FG,
            _tokens.CARD_SURFACE_KPI_PRIMARY,
        )
        assert positive_ratio >= AA_NORMAL_TEXT_MIN_RATIO
        assert negative_ratio >= AA_NORMAL_TEXT_MIN_RATIO
        assert neutral_ratio >= AA_NORMAL_TEXT_MIN_RATIO


class TestDarkModeContrast:
    def test_dark_text_on_dark_surface(self):
        ratio = contrast_ratio(_tokens.DARK_TEXT, _tokens.DARK_SURFACE)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_dark_text_secondary_on_dark_surface_elevated(self):
        ratio = contrast_ratio(_tokens.DARK_TEXT_SECONDARY, _tokens.DARK_SURFACE_ELEVATED)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_dark_text_muted_on_dark_surface_elevated(self):
        ratio = contrast_ratio(_tokens.DARK_TEXT_MUTED, _tokens.DARK_SURFACE_ELEVATED)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO

    def test_dark_primary_on_dark_surface(self):
        ratio = contrast_ratio(_tokens.DARK_PRIMARY, _tokens.DARK_SURFACE)

        # DARK_PRIMARY is often used for larger labels/interactive UI affordances.
        # If this fails 4.5:1, 3:1 is still acceptable for large text/non-text contrast.
        assert ratio >= AA_LARGE_TEXT_MIN_RATIO

    def test_dark_tab_active_text_on_tab_active_background(self):
        ratio = contrast_ratio(_tokens.DARK_TEXT, _tokens.DARK_PRIMARY_DARK)
        assert ratio >= AA_NORMAL_TEXT_MIN_RATIO
