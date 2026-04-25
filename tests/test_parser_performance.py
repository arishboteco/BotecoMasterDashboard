"""Performance regression tests for key parser paths."""

from __future__ import annotations

import time

import pandas as pd

import dynamic_report_parser
import pos_parser
import smart_upload


def test_parse_item_order_details_large_synthetic(monkeypatch):
    """Ensure item-order parsing handles large synthetic row counts quickly."""
    n_rows = 30000
    header = [
        "Date",
        "Timestamp",
        "Invoice No",
        "Payment Type",
        "Status",
        "Sub Total",
        "Discount",
        "Tax",
        "Final Total",
        "Covers",
        "Category",
        "Group Name",
        "Qty",
        "Item Name",
    ]
    rows = [header]
    for i in range(n_rows):
        rows.append(
            [
                "2026-04-01" if i % 2 == 0 else "2026-04-02",
                "2026-04-01 13:10:00",
                f"INV{i // 2}",
                "Cash" if i % 3 == 0 else "Card",
                "Success" if i % 25 else "Complimentary",
                "100",
                "5",
                "10",
                "110",
                "2",
                "Food",
                "Food",
                "1",
                "Fries",
            ]
        )
    df = pd.DataFrame(rows)

    monkeypatch.setattr(pos_parser, "_load_tabular", lambda _content, _name: df)

    start = time.perf_counter()
    out = pos_parser.parse_item_order_details(b"unused", "synthetic.xlsx")
    elapsed = time.perf_counter() - start

    assert out is not None
    assert len(out) == 2
    assert elapsed < 20.0


def test_parse_order_summary_csv_large_synthetic():
    """Ensure order-summary parsing scales with vectorized daily aggregation."""
    n_rows = 50000
    df = pd.DataFrame(
        {
            "date": ["2026-04-01 10:30:00" if i % 2 == 0 else "2026-04-02 19:45:00" for i in range(n_rows)],
            "my_amount": [100 + (i % 7) for i in range(n_rows)],
            "status": ["success" if i % 11 else "cancelled" for i in range(n_rows)],
            "payment_type": ["Cash" if i % 3 == 0 else "Card" for i in range(n_rows)],
        }
    )
    content = df.to_csv(index=False).encode("utf-8")

    start = time.perf_counter()
    out, notes = smart_upload._parse_order_summary_csv(content, "orders.csv")
    elapsed = time.perf_counter() - start

    assert notes == []
    assert out is not None
    assert len(out) == 2
    assert elapsed < 4.0


def test_dynamic_report_v1_large_synthetic():
    """Ensure Dynamic Report v1 parser remains fast on larger files."""
    n_rows = 20000
    df = pd.DataFrame(
        {
            "Bill Date": ["2026-04-01" if i % 2 == 0 else "2026-04-02" for i in range(n_rows)],
            "Bill No": [f"B{i}" for i in range(n_rows)],
            "Pax": ["2"] * n_rows,
            "Net Amount": ["100"] * n_rows,
            "Gross Sale": ["110"] * n_rows,
            "Bill Status": ["Success"] * n_rows,
            "Payment Type": ["Cash" if i % 2 == 0 else "Card" for i in range(n_rows)],
            "Created Date Time": ["01/04/2026 01:30 PM"] * n_rows,
            "Food": ["100"] * n_rows,
        }
    )

    start = time.perf_counter()
    out, notes = dynamic_report_parser.parse_dynamic_report(
        df.to_csv(index=False).encode("utf-8"), "dyn_v1.csv"
    )
    elapsed = time.perf_counter() - start

    assert out is not None
    assert len(out) == 2
    assert any("Parsed" in n for n in notes)
    assert elapsed < 20.0


def test_dynamic_report_v2_large_synthetic():
    """Ensure Dynamic Report v2 parser remains fast on line-item style input."""
    n_bills = 8000
    rows = []
    for i in range(n_bills):
        bill_date = "2026-04-01" if i % 2 == 0 else "2026-04-02"
        bill_no = f"V2-{i}"
        rows.append(
            {
                "Bill Date": bill_date,
                "Bill No": bill_no,
                "Pax": "-",
                "Net Amount": "-",
                "Gross Sale": "-",
                "Bill Status": "Success",
                "Payment Type": "Cash",
                "Category Name": "Food",
                "Item Name": "Burger",
                "Item Qty": "1",
                "Amount": "60",
                "Created Date Time": "01/04/2026 01:30 PM",
            }
        )
        rows.append(
            {
                "Bill Date": bill_date,
                "Bill No": bill_no,
                "Pax": "2",
                "Net Amount": "120",
                "Gross Sale": "130",
                "Bill Status": "Success",
                "Payment Type": "Card",
                "Category Name": "Food",
                "Item Name": "Pizza",
                "Item Qty": "1",
                "Amount": "60",
                "Created Date Time": "01/04/2026 01:30 PM",
            }
        )
    df = pd.DataFrame(rows)

    start = time.perf_counter()
    out, notes = dynamic_report_parser.parse_dynamic_report(
        df.to_csv(index=False).encode("utf-8"), "dyn_v2.csv"
    )
    elapsed = time.perf_counter() - start

    assert out is not None
    assert len(out) == 2
    assert any("Parsed" in n for n in notes)
    assert elapsed < 15.0
