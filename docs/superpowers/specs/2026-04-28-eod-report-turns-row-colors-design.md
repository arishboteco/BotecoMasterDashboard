# EOD Report Turns And Row Colors Design

## Goal

Fix the End of Day report so `Turns` reflects covers divided by configured seat count, and improve report scanability with restrained row background colors.

## Calculation

- Use configured location `seat_count` for turns calculations.
- For combined reports, use the sum of selected location seat counts.
- Display turns with one decimal place, so 48 covers over 70 seats shows `0.7`.
- Do not fall back to `covers / 100`; if seat count is unavailable, turns remains unavailable.

## Row Backgrounds

Use subtle semantic bands while preserving the existing report style:

- Operations rows (`Covers`, `Turns`, `APC`) use pale blue.
- Payment rows (`Cash`, `GPay`, `Zomato`, `Card`, `Other / Wallet`) use a neutral light background.
- Totals keep existing strong emphasis for net and MTD totals.
- Deduction rows (`Discount`, `MTD Discount`, `Complimentary`) use pale red or amber, with red value text retained for discounts.
- Target and forecast rows use status-aware pale backgrounds where useful.

## Testing

- Add or update tests covering combined turns with configured seat count.
- Add or update tests for report row background style generation if existing test seams allow it.
- Run focused tests for validation/scope/report formatting after implementation.
