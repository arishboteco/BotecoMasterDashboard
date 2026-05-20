# UPI GPay Razorpay Split Design

## Goal

Split generic UPI payment totals into GPay and Razorpay in reports and stored payment-method rows.
When the Growth Report already contains explicit GPay/Razorpay columns, use Growth Report values. When
Growth only has generic `UPI`, derive the GPay/Razorpay split from the Item Report `Payment Type` column.

## Approved Behavior

- Growth Report explicit split wins when available.
- Item Report split is used only as a fallback for dates where Growth has `upi_sales > 0` but no explicit
  GPay/Razorpay split.
- The generic UPI bucket is replaced by the derived split when the Item Report fully explains the Growth
  UPI amount.
- If the Item Report split is lower than Growth UPI, keep the unmatched remainder in `upi_sales`.
- Do not keep both the original UPI total and the split total, because that would double-count payment
  amounts.

## Data Flow

1. `uploads/parsers/item_report_category_summary.py` continues to emit category/service data, and also
   adds `payment_split_by_date` to parser metadata.
2. `payment_split_by_date` is keyed by date and contains normalized payment rows such as:
   `{"payment_method": "GPay", "payment_key": "gpay", "amount": 1000.0}` and
   `{"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0}`.
3. `smart_upload._process_new_flow_files()` stores Item Report payment split metadata per
   location/date.
4. Before saving Growth daily rows, the upload flow applies the fallback split:
   - if Growth has explicit GPay/Razorpay payment methods, leave it unchanged;
   - otherwise replace generic UPI with Item-derived GPay/Razorpay rows;
   - keep only an unmatched UPI remainder when Item-derived split is smaller than Growth UPI.
5. Existing `payment_method_sales` save/read/report paths then render the normalized split in analytics,
   PNG reports, and WhatsApp text.

## Normalization Rules

- `GPay`, `G PAY`, `Google Pay`, and case/spacing variants normalize to display `GPay`, key `gpay`.
- `Razorpay` and case/spacing variants normalize to display `Razorpay`, key `razorpay`.
- Other Item Report payment types are ignored for this fallback split unless future requirements add them.

## Mismatch Handling

- If Item-derived `GPay + Razorpay` equals Growth `UPI`, set `upi_sales = 0`.
- If Item-derived split is less than Growth `UPI`, set `upi_sales` to the positive remainder.
- If Item-derived split is greater than Growth `UPI`, cap the derived split proportionally to the Growth
  UPI amount and set `upi_sales = 0`. Add a parser/import note so the mismatch is visible.

## Testing

- Item Report parser test: extracts GPay/Razorpay split by date from `Payment Type` and `Final Total`.
- Smart upload merge test: generic Growth UPI is replaced by Item-derived GPay/Razorpay split.
- Smart upload mismatch test: unmatched UPI remainder is preserved when Item split is lower than Growth UPI.
- Report smoke test: resulting daily row stores GPay in `gpay_sales`, Razorpay in `payment_methods`, and
  does not double-count UPI.
