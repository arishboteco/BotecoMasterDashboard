"""Streamlit HTML/JS helpers for clipboard (text + PNG). Requires HTTPS or localhost."""

import base64
import hashlib
import inspect
import json

import streamlit.components.v1 as components

import ui_theme
from typing import List, Tuple, Optional

WHATSAPP_ICON_SVG = (
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
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

CLIPBOARD_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<rect x="9" y="2" width="6" height="4" rx="1"/>'
    '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
    "</svg>"
)

DOWNLOAD_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<polyline points="7 10 12 15 17 10"/>'
    '<line x1="12" y1="15" x2="12" y2="3"/>'
    "</svg>"
)

COPY_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
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
    focus_style = f"outline:2px solid {ui_theme.BRAND_SECONDARY};outline-offset:2px;"
    if primary:
        return (
            f"padding:0.5rem 1rem;cursor:pointer;border-radius:6px;border:none;"
            f"background:{c};color:#FFFFFF;font-weight:600;font-size:0.85rem;"
            f"font-family:'Inter',sans-serif;"
            f"box-shadow:0 1px 2px rgba(0,0,0,0.05);"
            f"display:inline-flex;align-items:center;gap:0.4rem;"
            f"min-height:40px;line-height:1.3;transition:all 0.15s ease;"
            f"{focus_style}"
        )
    return (
        "padding:0.5rem 1rem;cursor:pointer;border-radius:6px;border:1px solid #E2E8F0;"
        "background:#FFFFFF;color:#0F172A;font-weight:500;font-size:0.85rem;"
        "font-family:'Inter',sans-serif;"
        "display:inline-flex;align-items:center;gap:0.4rem;"
        "min-height:40px;line-height:1.3;transition:all 0.15s ease;" + focus_style
    )


def _icon_btn_style(*, primary: bool = True) -> str:
    """Generate square icon button styles (40x40px)."""
    c = ui_theme.BRAND_PRIMARY
    focus_style = f"outline:2px solid {ui_theme.BRAND_SECONDARY};outline-offset:2px;"
    if primary:
        return (
            f"display:inline-flex;align-items:center;justify-content:center;"
            f"width:40px;height:40px;padding:0;border-radius:6px;border:none;"
            f"background:{c};color:#FFFFFF;cursor:pointer;"
            f"box-shadow:0 1px 2px rgba(0,0,0,0.05);"
            f"transition:all 0.15s ease;{focus_style}"
        )
    return (
        f"display:inline-flex;align-items:center;justify-content:center;"
        f"width:40px;height:40px;padding:0;border-radius:6px;"
        f"border:1px solid #E2E8F0;background:#FFFFFF;color:#0F172A;cursor:pointer;"
        f"transition:all 0.15s ease;{focus_style}"
    )


def render_image_action_row(
    png_bytes: bytes,
    filename: str,
    component_key: str,
    share_text: str = "Boteco EOD Report",
    fallback_url: Optional[str] = None,
) -> None:
    """Render a unified row of 3 icon buttons: Copy, WhatsApp, Download."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uid = _safe_id(component_key)
    fallback_url_json = json.dumps(fallback_url)
    share_text_json = json.dumps(share_text)

    html = f"""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..24,400,0,0&display=swap" rel="stylesheet">
<style>
.material-symbols-outlined {{
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  font-size: 20px;
  display: inline-block;
  line-height: 1;
}}
.action-btn-row {{
  display: inline-flex;
  align-items: center;
  gap: 0;
  background: #F7FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 4px;
}}
.action-btn-row .action-btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
  background: transparent;
  color: #475569;
  font-family: 'Material Symbols Outlined', sans-serif;
  font-size: 20px;
  line-height: 1;
}}
.action-btn-row .action-btn:hover {{
  background: #E6F4F3;
  color: #1F5FA8;
}}
.action-btn-row .action-btn + .action-btn {{
  border-left: 1px solid #E2E8F0;
}}
</style>
<div class="action-btn-row" id="{uid}_row">
  <button class="action-btn" id="{uid}_copy" title="Copy to clipboard" type="button">&#xe14d;</button>
  <button class="action-btn" id="{uid}_wa" title="Share via WhatsApp" type="button">{WHATSAPP_ICON_SVG}</button>
  <button class="action-btn" id="{uid}_dl" title="Download" type="button">&#xe2c4;</button>
</div>
<span id="{uid}_msg" style="font-size:0.75rem;margin-left:0.5rem;color:#6DBE45;"></span>
<script>
(function() {{
  const b64 = "{b64}";
  const shareText = {share_text_json};
  const fallbackUrl = {fallback_url_json};
  const msgEl = document.getElementById("{uid}_msg");

  // Copy button
  document.getElementById("{uid}_copy").onclick = async function() {{
    try {{
      const dataUrl = "data:image/png;base64," + b64;
      const blob = await (await fetch(dataUrl)).blob();
      await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
      msgEl.textContent = "Copied";
      setTimeout(() => {{ msgEl.textContent = ""; }}, 2000);
    }} catch (e) {{
      alert("Copy failed. Try Chrome/Edge over HTTPS.");
    }}
  }};

  // WhatsApp button
  document.getElementById("{uid}_wa").onclick = async function() {{
    try {{
      const dataUrl = "data:image/png;base64," + b64;
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], "{filename}", {{type: "image/png"}});
      if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
        await navigator.share({{files: [file], text: shareText}});
        msgEl.textContent = "Shared!";
      }} else {{
        await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
        msgEl.textContent = "Copied - paste in WhatsApp";
        if (fallbackUrl) {{ window.open(fallbackUrl, "_blank"); }}
      }}
      setTimeout(() => {{ msgEl.textContent = ""; }}, 3000);
    }} catch (e) {{
      if (e.name !== "AbortError") {{
        msgEl.textContent = "Share failed";
        setTimeout(() => {{ msgEl.textContent = ""; }}, 2000);
      }}
    }}
  }};

  // Download button
  document.getElementById("{uid}_dl").onclick = function() {{
    try {{
      const bin = atob(b64);
      const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const blob = new Blob([u8], {{type: "image/png"}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "{filename}";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      msgEl.textContent = "Saved";
      setTimeout(() => {{ msgEl.textContent = ""; }}, 2000);
    }} catch (e) {{
      alert("Download failed.");
    }}
  }};
}})();
</script>
"""
    _html(html, 48, component_key)


def render_icon_button(
    icon_svg: str,
    tooltip: str,
    on_click_js: str,
    component_key: str,
    *,
    primary: bool = True,
) -> None:
    """Render a square icon-only button with clipboard/image action."""
    uid = _safe_id(component_key)
    stl = _icon_btn_style(primary=primary)
    html = f"""
<div class="action-btn-container">
  <button class="action-btn {"action-btn-primary" if primary else "action-btn-secondary"}"
          id="{uid}_btn" type="button" style="{stl}" title="{tooltip}">
    {icon_svg}
  </button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  document.getElementById("{uid}_btn").onclick = async function() {{
    {on_click_js}
  }};
}})();
</script>
"""
    _html(html, 48, component_key)


def render_copy_icon_button(
    png_bytes: bytes,
    component_key: str,
    *,
    primary: bool = True,
    label: str = "Copy",
) -> None:
    """Render a square icon button that copies PNG to clipboard."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uid = _safe_id(component_key + "ci")
    stl = _icon_btn_style(primary=primary)
    js = f"""
    try {{
      const dataUrl = "data:image/png;base64,{b64}";
      const blob = await (await fetch(dataUrl)).blob();
      await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
      document.getElementById("{uid}_msg").textContent = "Copied";
      setTimeout(() => {{
        if (document.getElementById("{uid}_msg").textContent === "Copied") {{
          document.getElementById("{uid}_msg").textContent = "";
        }}
      }}, 2000);
    }} catch (e) {{
      alert("Copy failed. Try Chrome/Edge over HTTPS.");
    }}
    """
    html = f"""
<div class="action-btn-container">
  <button class="action-btn {"action-btn-primary" if primary else "action-btn-secondary"}"
          id="{uid}_btn" type="button" style="{stl}" title="{label}">
    {COPY_ICON_SVG}
  </button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  document.getElementById("{uid}_btn").onclick = async function() {{
    {js}
  }};
}})();
</script>
"""
    _html(html, 48, component_key)


def render_download_button(
    data: bytes,
    filename: str,
    mime_type: str,
    component_key: str,
    *,
    primary: bool = True,
) -> None:
    """Render a square icon button that downloads a file."""
    b64 = base64.b64encode(data).decode("ascii")
    uid = _safe_id(component_key + "dl")
    stl = _icon_btn_style(primary=primary)
    js = f"""
    try {{
      const bin = atob("{b64}");
      const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const blob = new Blob([u8], {{type: "{mime_type}"}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "{filename}";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      document.getElementById("{uid}_msg").textContent = "Saved";
      setTimeout(() => {{
        if (document.getElementById("{uid}_msg").textContent === "Saved") {{
          document.getElementById("{uid}_msg").textContent = "";
        }}
      }}, 2000);
    }} catch (e) {{
      alert("Download failed.");
    }}
    """
    html = f"""
<div class="action-btn-container">
  <button class="action-btn {"action-btn-primary" if primary else "action-btn-secondary"}"
          id="{uid}_btn" type="button" style="{stl}" title="Download {filename}">
    {DOWNLOAD_ICON_SVG}
  </button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  document.getElementById("{uid}_btn").onclick = async function() {{
    {js}
  }};
}})();
</script>
"""
    _html(html, 48, component_key)


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
        msgEl.style.color = "#6DBE45";
      }} else {{
        if (fallbackUrl) {{
          try {{
            const blob = await b64ToBlob(filesData[0].b64, "image/png");
            await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
            msgEl.textContent = "Image copied — paste in WhatsApp";
            msgEl.style.color = "#6DBE45";
          }} catch (clipErr) {{
            msgEl.textContent = "Open WhatsApp — attach image manually";
            msgEl.style.color = "#F4B400";
          }}
          window.open(fallbackUrl, "_blank");
        }} else {{
          msgEl.textContent = "Use download (ZIP/PNG)";
          msgEl.style.color = "#F4B400";
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
            msgEl.style.color = "#6DBE45";
          }} catch (clipErr) {{
            msgEl.textContent = "Open WhatsApp — attach image manually";
            msgEl.style.color = "#F4B400";
          }}
          window.open(fallbackUrl, "_blank");
        }} else {{
          msgEl.textContent = "Use download (ZIP/PNG)";
          msgEl.style.color = "#F4B400";
        }}
      }} else {{
        msgEl.textContent = "Share failed";
        msgEl.style.color = "#EF4444";
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
