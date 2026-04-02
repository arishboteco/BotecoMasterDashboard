"""Streamlit HTML/JS helpers for clipboard (text + PNG). Requires HTTPS or localhost."""

import base64
import hashlib
import inspect
import json

import streamlit.components.v1 as components

import ui_theme
from typing import List, Tuple, Optional

# WhatsApp SVG icon (24x24, brand-colored)
WHATSAPP_ICON_SVG = (
    '<svg class="whatsapp-icon" viewBox="0 0 24 24" fill="currentColor" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.151'
    "-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475"
    "-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52"
    ".149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207"
    "-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297"
    "-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487"
    ".709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413"
    ".248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 "
    "9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51"
    "-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 "
    "0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 "
    "0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305"
    "-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 "
    '11.821 0 00-3.48-8.413z"/>'
    "</svg>"
)


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
    """Generate inline button styles with proper overflow handling."""
    c = ui_theme.BRAND_PRIMARY
    focus_style = "outline:2px solid #2563EB;outline-offset:2px;"
    if primary:
        return (
            f"padding:0.5rem 1rem;cursor:pointer;border-radius:6px;border:none;"
            f"background:{c};color:#FFFFFF;font-weight:600;font-size:0.85rem;"
            f"font-family:'DM Sans',sans-serif;"
            f"box-shadow:0 1px 2px rgba(0,0,0,0.05);"
            f"display:inline-flex;align-items:center;gap:0.4rem;"
            f"min-height:40px;line-height:1.3;transition:all 0.15s ease;"
            f"{focus_style}"
        )
    return (
        "padding:0.5rem 1rem;cursor:pointer;border-radius:6px;border:1px solid #E2E8F0;"
        "background:#FFFFFF;color:#0F172A;font-weight:500;font-size:0.85rem;"
        "font-family:'DM Sans',sans-serif;"
        "display:inline-flex;align-items:center;gap:0.4rem;"
        "min-height:40px;line-height:1.3;transition:all 0.15s ease;" + focus_style
    )


def render_copy_text_button(
    text: str,
    label: str,
    component_key: str,
    height: int = 56,
    *,
    primary: bool = True,
) -> None:
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    uid = _safe_id(component_key + "t")
    stl = _btn_style(primary=primary)
    html = f"""
<div class="whatsapp-btn-container">
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
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
    height: int = 56,
    *,
    primary: bool = True,
) -> None:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uid = _safe_id(component_key + "i")
    stl = _btn_style(primary=primary)
    html = f"""
<div class="whatsapp-btn-container">
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
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
    height: int = 56,
    *,
    primary: bool = True,
    share_text: str = "Boteco EOD Report",
    fallback_url: Optional[str] = None,
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
    fallback_url_json = json.dumps(fallback_url)

    html = """<div class="whatsapp-btn-container">
  <button id="{uid}_btn" type="button" style="{stl}">{whatsapp_icon}<span>{label}</span></button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  const filesData = {files_json};
  const shareText = {share_text_json};
  const fallbackUrl = {fallback_url_json};
  const msgEl = document.getElementById("{uid}_msg");
  const btnEl = document.getElementById("{uid}_btn");

  async function b64ToBlob(b64, mime) {{
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Blob([u8], {{type: mime}});
  }}

  async function canShareFiles() {{
    if (!navigator.canShare) return false;
    try {{
      const testBlob = await b64ToBlob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "image/png");
      return navigator.canShare({{files: [new File([testBlob], "test.png", {{type: "image/png"}})]}});
    }} catch(e) {{
      return false;
    }}
  }}

  btnEl.onclick = async function() {{
    try {{
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
        msgEl.style.color = "#5B7F4A";
      }} else {{
        if (fallbackUrl) {{
          try {{
            const blob = await b64ToBlob(filesData[0].b64, "image/png");
            await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
            msgEl.textContent = "Image copied — paste in WhatsApp";
            msgEl.style.color = "#5B7F4A";
          }} catch (clipErr) {{
            msgEl.textContent = "Open WhatsApp — attach image manually";
            msgEl.style.color = "#C28B2D";
          }}
          window.open(fallbackUrl, "_blank");
        }} else {{
          msgEl.textContent = "Use download (ZIP/PNG)";
          msgEl.style.color = "#C28B2D";
        }}
      }}
    }} catch (e) {{
      console.error("Share error:", e);
      if (e.name === "AbortError") {{
        return;
      }}
      if (e.message && e.message.includes("not supported")) {{
        if (fallbackUrl) {{
          try {{
            const blob = await b64ToBlob(filesData[0].b64, "image/png");
            await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
            msgEl.textContent = "Image copied — paste in WhatsApp";
            msgEl.style.color = "#5B7F4A";
          }} catch (clipErr) {{
            msgEl.textContent = "Open WhatsApp — attach image manually";
            msgEl.style.color = "#C28B2D";
          }}
          window.open(fallbackUrl, "_blank");
        }} else {{
          msgEl.textContent = "Use download (ZIP/PNG)";
          msgEl.style.color = "#C28B2D";
        }}
      }} else {{
        msgEl.textContent = "Share failed";
        msgEl.style.color = "#B84233";
      }}
    }}
  }};
}})();
</script>
""".format(
        uid=uid,
        stl=stl,
        label=label,
        whatsapp_icon=WHATSAPP_ICON_SVG,
        files_json=files_json,
        share_text_json=json.dumps(share_text),
        fallback_url_json=fallback_url_json,
    )
    _html(html, height, component_key)
