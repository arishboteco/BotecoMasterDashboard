# EOD Report Turns And Row Colors Design

## Goal

Fix the End of Day report so `Turns` reflects covers divided by configured seat count, and improve report scanability with restrained row background colors.

## Calculation

- Use configured location `seat_count` for turns calculations.
- For combined reports, use the sum of selected location seat counts.
- Display turns with one decimal place, so 48 covers over 70 seats shows `0.7`.
- Do not fall back to `covers / 100`; if seat count is unavailable, turns remains unavailable.

## Row Backgrounds

Use section-based backgrounds instead of zebra striping. Decorative banding conflicts with semantic color, so body rows should stay white unless their row has a specific purpose.

- Operations rows (`Covers`, `Turns`, `APC`) use pale blue.
- Payment rows (`Cash`, `GPay`, `Zomato`, `Card`, `Other / Wallet`) stay white.
- Taxes stay white; `EOD Gross Total` uses a soft neutral fill.
- `Discount` and `MTD Discount` use pale red, with red value text retained.
- `Complimentary` and `MTD Complimentary` use pale amber to show an exception without equating it to discount leakage.
- `EOD Net Total` keeps the strong navy emphasis.
- `MTD Net Sales` and `MTD Net (Excl. Disc.)` stay bold with no heavy fill.
- The final target/forecast rows use distinct purposeful fills: `Sales Target` soft slate, `% of Target` status fill, `Forecast Month-End` soft blue, `Forecast vs Target` status fill, and `Required Daily Run Rate` pale lavender when behind target or neutral when healthy.

## Testing

- Add or update tests covering combined turns with configured seat count.
- Add or update tests for report row background style generation if existing test seams allow it.
- Run focused tests for validation/scope/report formatting after implementation.
