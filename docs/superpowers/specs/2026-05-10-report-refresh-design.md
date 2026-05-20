# Report Refresh Design

## Goal

Add an in-app way to refresh the currently selected Report tab data after database changes,
backfills, or imports without restarting Streamlit.

## Approved Approach

Use a single `Refresh report` control near the Report date/outlet picker. The button refreshes the
current report scope by clearing Report-tab caches and rerunning the page.

## Behavior

- The button appears beside the existing report date/outlet controls.
- Clicking it clears Report-tab caches for daily report bundles, MTD maps, and footfall rows.
- Clicking it also clears relevant Streamlit cached data so database reads are fetched again.
- The page reruns immediately after refresh.
- A short message confirms that report data was refreshed.

## Scope

This is intentionally limited to Report tab data. It does not clear unrelated analytics/upload caches
and does not change database records.

## Testing

- Add a source-level Report tab test confirming the refresh control is present.
- Add a service-level test confirming the Report cache clear function clears report, MTD, and footfall
  cache stores.
