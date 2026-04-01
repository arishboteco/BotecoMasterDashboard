"""Streamlit HTML/JS helpers for clipboard (text + PNG). Requires HTTPS or localhost."""

import base64
import hashlib
import inspect
import json

import streamlit.components.v1 as components

import ui_theme
from typing import List, Tuple, Optional


def _html(html: str, height: int, component_key: str) -> None:
    """Call components.html with key only if this Streamlit build supports it."""
    params = inspect.signature(components.html).parameters
    if "key" in params:
        components.html(html, height=height, key=component_key)
    else:
        components.html(html, height=height)


def _safe_id(key: str) -> str:
    return "c" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _btn_style(*, primary: bool = True) -> str:
    c = ui_theme.BRAND_PRIMARY
    if primary:
        return (
            f"padding:0.45rem 1rem;cursor:pointer;border-radius:8px;border:none;"
            f"background:{c};color:#fff;font-weight:600;font-size:0.9rem;"
            f"box-shadow:0 1px 2px rgba(0,0,0,0.08);"
        )
    return (
        "padding:0.45rem 1rem;cursor:pointer;border-radius:8px;border:1px solid #dee2e6;"
        "background:#fff;color:#1a1a1a;font-weight:500;font-size:0.9rem;"
    )


def render_copy_text_button(
    text: str,
    label: str,
    component_key: str,
    height: int = 52,
    *,
    primary: bool = True,
) -> None:
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    uid = _safe_id(component_key + "t")
    stl = _btn_style(primary=primary)
    html = f"""
<div>
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
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


def render_copy_image_button(
    png_bytes: bytes,
    label: str,
    component_key: str,
    height: int = 52,
    *,
    primary: bool = True,
) -> None:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uid = _safe_id(component_key + "i")
    stl = _btn_style(primary=primary)
    html = f"""
<div>
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
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


def render_share_images_button(
    files: List[Tuple[str, bytes]],
    label: str,
    component_key: str,
    height: int = 52,
    *,
    primary: bool = True,
    share_text: str = "Boteco EOD Report",
) -> None:
    """Share multiple PNG images via native share API (mobile) or show fallback (desktop)."""
    if not files:
        return

    # Build base64 for each file
    files_b64 = []
    for name, data in files:
        b64 = base64.b64encode(data).decode("ascii")
        files_b64.append((name, b64))

    uid = _safe_id(component_key + "s")
    stl = _btn_style(primary=primary)

    # JSON-safe representation of files array
    files_json = (
        "["
        + ",".join('{{"name":{!r},"b64":{!r}}}'.format(n, b) for n, b in files_b64)
        + "]"
    )

    # Use str.format to avoid f-string issues with JS braces
    html = """<div>
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
  <span id="{uid}_msg" style="margin-left:10px;font-size:0.9rem;"></span>
</div>
<script>
(function() {{
  const filesData = {files_json};
  const shareText = {share_text_json};
  const msgEl = document.getElementById("{uid}_msg");
  const btnEl = document.getElementById("{uid}_btn");

  // Helper: convert base64 to Blob
  async function b64ToBlob(b64, mime) {{
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Blob([u8], {{type: mime}});
  }}

  // Check if Web Share API supports files
  async function canShareFiles() {{
    if (!navigator.canShare) return false;
    try {{
      const testBlob = await b64ToBlob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "image/png");
      return navigator.canShare({{files: [new File([testBlob], "test.png", {{type: "image/png"}})]]}});
    }} catch(e) {{
      return false;
    }}
  }}

  btnEl.onclick = async function() {{
    try {{
      // Build File objects
      const fileObjs = await Promise.all(
        filesData.map(async (f) => {{
          const blob = await b64ToBlob(f.b64, "image/png");
          return new File([blob], f.name, {{type: "image/png"}});
        }})
      );

      const canShare = await canShareFiles();
      if (canShare) {{
        await navigator.share({{
          files: fileObjs,
          text: shareText
        }});
        msgEl.textContent = "Shared!";
        msgEl.style.color = "#2e7d32";
      }} else {{
        // Fallback for desktop browsers
        msgEl.textContent = "Use download (ZIP/PNG)";
        msgEl.style.color = "#d97706";
      }}
    }} catch (e) {{
      console.error("Share error:", e);
      if (e.name === "AbortError") {{
        // User cancelled - no message needed
        return;
      }}
      // Check if it's the "not supported" error
      if (e.message && e.message.includes("not supported")) {{
        msgEl.textContent = "Use download (ZIP/PNG)";
        msgEl.style.color = "#d97706";
      }} else {{
        msgEl.textContent = "Share failed";
        msgEl.style.color = "#dc2626";
      }}
    }}
  }};
}})();
</script>
""".format(
        uid=uid,
        stl=stl,
        label=label,
        files_json=files_json,
        share_text_json=json.dumps(share_text),
    )
    _html(html, height, component_key)
