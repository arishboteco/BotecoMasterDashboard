# CSS Visual Regression Guardrails

This project enforces lightweight, file-based CSS guardrails in `tests/test_css_token_usage.py`.

## What is enforced

1. **Raw hex color guardrail**
   - `styles/_tokens.py` is the canonical token source and may contain raw hex values.
   - Other `styles/*.py` files may only use raw hex values that are explicitly listed in `tests/baselines/css_hex_allowlist.json`.
   - This prevents accidental, one-off color additions that bypass the token system.

2. **`_contrast_fix.py` root override guardrail**
   - `styles/_contrast_fix.py` must not define `:root { --token: ... }` overrides.
   - The file is intended for contrast selectors and semantic usage, not token redefinition.

3. **`!important` budget guardrail**
   - `tests/baselines/css_important_baseline.json` pins both total and per-file `!important` usage.
   - Tests fail when counts increase unexpectedly.

## How to update allowlists responsibly

Only update baseline files when the change is intentional and reviewed.

### Raw hex allowlist (`tests/baselines/css_hex_allowlist.json`)

Update **only** when one of these is true:
- The hex is required for a documented external/embed context (for example, print-only output or third-party/embedded rendering constraints).
- The hex is part of an approved transitional migration and cannot yet be replaced by a token.

Before editing the allowlist:
1. Confirm a tokenized value cannot be used instead.
2. Add or update nearby code comments explaining why token usage is not possible.
3. Keep entries as narrow as possible (specific file + specific hex).

### `!important` baseline (`tests/baselines/css_important_baseline.json`)

Update the baseline only after all alternatives were considered (specificity, scope, component structure).

When updating:
1. Prefer reducing existing `!important` counts where possible.
2. Document the reason in the pull request description.
3. Regenerate/update the exact baseline values and run `pytest`.

## Local validation

```bash
pytest tests/test_css_token_usage.py -v
pytest
```
