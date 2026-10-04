# Upload and desktop report-sharing fixes — 4 October 2026

## WhatsApp correction

The sharing behavior documented below is superseded by this correction:
- Removed the always-visible fallback instructions, links, ZIP downloads and duplicate copy controls.
- Restored native PNG file sharing on desktop as well as mobile. The operating-system share picker lets the user select WhatsApp and receives every original PNG.
- If native file sharing is unsupported, the button opens the installed WhatsApp app. Individual PNGs are copied when clipboard access is available; a short message appears only after interaction. App links alone cannot attach image files.
- Cancelling native sharing does nothing further. Errors show a concise message and re-enable the button.
- Kept the existing copy and download icons and reduced the legacy iframe height.

Changed files: `clipboard_ui.py` (behavior and UI), `tests/test_report_sharing.py` (regression checks), and this QA record.
Validation: all 10 sharing tests passed (Node executes the generated JavaScript; pytest run with `--noconftest` because these tests do not use database fixtures). Ruff E/F/I/B and diff whitespace checks passed. Desktop and 375px-wide local previews showed only the primary share button and existing three-icon action row, without fallback links, instructions or horizontal overflow. Actual WhatsApp delivery remains unverified because the in-app browser cannot control the Windows share picker or WhatsApp desktop.

![Corrected desktop sharing](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/sharing-clean-desktop.jpg)

![Corrected mobile layout](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/sharing-clean-mobile.jpg)

Context7 was unavailable; native sharing behavior was checked against [Microsoft Edge documentation](https://learn.microsoft.com/en-us/microsoft-edge/progressive-web-apps/how-to/share) and [MDN](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share).

## Original release evidence (before the correction)

The fixes were prepared on `main`, which matched `origin/main` after fetching.
Existing unrelated working-tree edits were preserved. Live deployment was not verified.

## Changed files

| File | Why it changed |
| --- | --- |
| `tabs/upload_tab.py` | Removes the misleading second upload prompt; batches all imported footfall dates into one form with Save and finish or Finish without saving. |
| `styles/_components.py` | Styles the actual uploader through a native Streamlit container key; enlarges its drop target and removes hover movement. |
| `components/footfall_editor.py` | Separates entry from saving, keeps Date/Lunch/Dinner together in the upload form, preserves blank/zero semantics, and invalidates caches after partial saves. The standalone Footfall editor also batches edits. |
| `clipboard_ui.py` | Opens WhatsApp Web directly on desktop, starts individual-image copying before opening the new tab, supplies PNG/ZIP downloads, and prevents fallback controls from being clipped. Mobile retains native sharing. |
| `tests/test_upload_footfall_flow.py` | Checks multi-outlet saving, skipping, retries, blank/zero handling and partial-failure cache invalidation. |
| `tests/test_report_sharing.py` | Checks native sharing, desktop routing even when native APIs exist, copying and denied permissions, PNG/ZIP contents and caption encoding. |

## Verification

- 70 focused tests passed across report sharing, upload footfall flow, upload tab/service, footfall overrides, footfall tab and bulk paste.
- Ruff `E,F,I,B` passed for the changed Python implementation and test files; `git diff --check` passed.
- Local browser checks used the real UI functions with synthetic data and an in-memory repository, with Streamlit 1.65.0 and Python 3.14.3.
- Desktop and 375 × 812 layouts were inspected. The upload prompt points to the actual bordered dropzone. Lunch and Dinner remain visible together on the narrow form. Sharing actions wrap within their iframe.
- Entered Lunch and Dinner values with Tab between cells: the page-render counter stayed unchanged until submission. Save and finish returned to upload with confirmation.
- Copied a synthetic report PNG through the desktop fallback in the browser and observed the success message.
- ZIP contents and download link payloads were verified in tests. The in-app browser's download-event capture timed out, so a browser-saved ZIP was not independently confirmed.

This is scoped UI verification against `visual_qa_checklist.md`, not a complete review of the authenticated application. Login, production import/database writes, other pages, an actual mobile device, older Streamlit versions and delivery of a WhatsApp message were not tested. No live reports were sent.

Desktop image sharing still requires choosing a WhatsApp chat and pasting or attaching the image. For multiple reports, copy/attach each PNG or download the ZIP and extract its images.

The API behavior was checked against [Streamlit forms](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form), [Streamlit iframe sizing](https://docs.streamlit.io/develop/api-reference/text/st.iframe) and [browser sharing requirements](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share). Context7 was unavailable in this session.

## Local screenshots

![Upload desktop](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/upload-desktop.jpg)

![Upload narrow layout](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/upload-mobile.jpg)

![Footfall desktop](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/footfall-desktop.jpg)

![Footfall narrow layout](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/footfall-mobile.jpg)

![Sharing desktop](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/sharing-desktop.jpg)

![Sharing narrow layout](C:/Users/arish/.codex/visualizations/2026/10/04/01a1050d-dadc-7c21-b7f4-ac387c0ea6aa/sharing-mobile.jpg)
