"""Tests for clipboard/share UI helpers."""

import clipboard_ui


def test_share_images_builds_files_sequentially_without_renaming(monkeypatch) -> None:
    """Shared PNG files should keep visible names while preserving input order."""
    captured = {}

    def fake_html(html: str, height: int, component_key: str) -> None:
        captured["html"] = html
        captured["height"] = height
        captured["component_key"] = component_key

    monkeypatch.setattr(clipboard_ui, "_html", fake_html)

    clipboard_ui.render_share_images_button(
        [
            ("boteco_sales_summary_2026-04-27.png", b"sales"),
            ("boteco_category_2026-04-27.png", b"category"),
            ("boteco_service_2026-04-27.png", b"service"),
        ],
        "WhatsApp",
        "share_order_test",
    )

    html = captured["html"]

    assert "for (const f of filesData)" in html
    assert "fileObjs.push(new File([blob], f.name" in html
    assert "Promise.all" not in html
    assert "boteco_sales_summary_2026-04-27.png" in html
    assert "01_boteco_sales_summary_2026-04-27.png" not in html
