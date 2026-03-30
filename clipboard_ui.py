"""Streamlit HTML/JS helpers for clipboard (text + PNG). Requires HTTPS or localhost."""

import base64
import hashlib
import inspect

import streamlit.components.v1 as components


def _html(html: str, height: int, component_key: str) -> None:
    """Call components.html with key only if this Streamlit build supports it."""
    params = inspect.signature(components.html).parameters
    if "key" in params:
        components.html(html, height=height, key=component_key)
    else:
        components.html(html, height=height)


def _safe_id(key: str) -> str:
    return "c" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def render_copy_text_button(text: str, label: str, component_key: str, height: int = 52) -> None:
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    uid = _safe_id(component_key + "t")
    html = f"""
<div>
  <button id="{uid}_btn" type="button" style="padding:0.4rem 1rem;cursor:pointer;border-radius:6px;">{label}</button>
  <span id="{uid}_msg" style="margin-left:10px;font-size:0.9rem;color:#2e7d32;"></span>
</div>
<script>
(function() {{
  const b64 = {repr(b64)};
  document.getElementById("{uid}_btn").onclick = async function() {{
    try {{
      const bin = atob(b64);
      const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const txt = new TextDecoder("utf-8").decode(u8);
      await navigator.clipboard.writeText(txt);
      document.getElementById("{uid}_msg").textContent = "Copied";
    }} catch (e) {{
      alert("Copy failed. Use HTTPS or allow clipboard access. " + e);
    }}
  }};
}})();
</script>
"""
    _html(html, height, component_key)


def render_copy_image_button(png_bytes: bytes, label: str, component_key: str, height: int = 52) -> None:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uid = _safe_id(component_key + "i")
    html = f"""
<div>
  <button id="{uid}_btn" type="button" style="padding:0.4rem 1rem;cursor:pointer;border-radius:6px;">{label}</button>
  <span id="{uid}_msg" style="margin-left:10px;font-size:0.9rem;color:#2e7d32;"></span>
</div>
<script>
(function() {{
  const dataUrl = "data:image/png;base64," + {repr(b64)};
  document.getElementById("{uid}_btn").onclick = async function() {{
    try {{
      const blob = await (await fetch(dataUrl)).blob();
      await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
      document.getElementById("{uid}_msg").textContent = "Copied image";
    }} catch (e) {{
      alert("Image copy failed (try Chrome/Edge over HTTPS). " + e);
    }}
  }};
}})();
</script>
"""
    _html(html, height, component_key)
