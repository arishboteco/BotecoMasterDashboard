"""Flash Report XLSX parser extracted from smart_upload."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import pos_parser


def parse_flash_report(
    content: bytes,
    filename: str,
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse Flash Report / POS Collection report rows into a single-day record."""
    notes: List[str] = []
    bio = BytesIO(content)
    df: Optional[pd.DataFrame] = None
    for engine in (None, "openpyxl", "xlrd"):
        try:
            bio.seek(0)
            kw = {"engine": engine} if engine else {}
            df = pd.read_excel(bio, sheet_name=0, header=None, **kw)
            break
        except (ValueError, ImportError, OSError, pd.errors.ParserError):
            continue

    if df is None or df.empty:
        return None, ["Could not read Flash Report."]

    date_str: Optional[str] = None
    for i in range(min(10, len(df))):
        label = pos_parser.norm_header(df.iloc[i, 0]) if len(df.columns) > 0 else ""
        if "date" in label:
            val = (
                str(df.iloc[i, 1]).strip()
                if len(df.columns) > 1 and pd.notna(df.iloc[i, 1])
                else ""
            )
            if val and val.lower() != "nan":
                date_str = pos_parser.cell_date_to_iso(val) or pos_parser.parse_date(val)
        if date_str:
            break

    if not date_str:
        return None, ["Flash Report: could not extract date."]

    summary_row: Optional[int] = None
    for i in range(len(df)):
        label = pos_parser.norm_header(df.iloc[i, 0])
        if label == "orders" or (
            "my amount" in " ".join(pos_parser.norm_header(v) for v in df.iloc[i].values)
        ):
            summary_row = i
            break

    net = 0.0
    gross = 0.0
    cash = 0.0
    cgst = 0.0
    sgst = 0.0
    service_charge = 0.0
    discount = 0.0
    covers = 0
    gpay = 0.0
    card = 0.0
    zomato = 0.0
    other = 0.0
    categories: List[Dict[str, Any]] = []

    if summary_row is not None:
        hdr = {
            pos_parser.norm_header(df.iloc[summary_row, j]): j
            for j in range(len(df.columns))
            if pos_parser.norm_header(df.iloc[summary_row, j])
        }
        if summary_row + 1 < len(df):
            data_row = df.iloc[summary_row + 1]
            for k, idx in hdr.items():
                v = pos_parser.f(data_row.iloc[idx])
                if "net sales" in k or "my amount" in k:
                    net = max(net, v)
                elif "total" == k:
                    gross = max(gross, v)
                elif "cash" in k:
                    cash = max(cash, v)
                elif "cgst" in k:
                    cgst = v
                elif "sgst" in k:
                    sgst = v
                elif "service charge" in k:
                    service_charge = v
                elif "discount" in k:
                    discount = v
                elif "pax" in k:
                    covers = int(v)
        if gross == 0:
            gross = net

    pay_start: Optional[int] = None
    for i in range(len(df)):
        label = pos_parser.norm_header(df.iloc[i, 0])
        if "payment wise" in label or label == "payment type":
            pay_start = i + 1
            break
    if pay_start:
        for i in range(pay_start, min(pay_start + 25, len(df))):
            label = pos_parser.norm_header(df.iloc[i, 0])
            if not label or "category" in label or label == "total":
                break
            amt = pos_parser.f(df.iloc[i, 1]) if len(df.columns) > 1 else 0.0
            bucket = pos_parser.payment_bucket(label)
            if bucket == "gpay":
                gpay += amt
            elif bucket == "zomato":
                zomato += amt
            elif bucket == "card":
                card += amt
            elif bucket == "cash":
                cash = max(cash, amt)
            else:
                other += amt

    cat_start: Optional[int] = None
    for i in range(len(df)):
        if "category wise" in pos_parser.norm_header(df.iloc[i, 0]):
            cat_start = i + 1
            break
    if cat_start is not None and cat_start < len(df):
        amt_col = 1
        for j in range(len(df.columns)):
            k = pos_parser.norm_header(df.iloc[cat_start, j])
            if "net sales" in k or "my amount" in k:
                amt_col = j
                break
        for i in range(cat_start + 1, min(cat_start + 30, len(df))):
            cat_name = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
            if not cat_name or cat_name.lower() in ("total", "round off", "nan", ""):
                if cat_name.lower() == "total":
                    break
                continue
            cat_amount = pos_parser.f(df.iloc[i, amt_col]) if amt_col < len(df.columns) else 0.0
            if cat_amount > 0:
                categories.append(
                    {
                        "category": pos_parser.normalize_group_category(cat_name),
                        "qty": 0,
                        "amount": cat_amount,
                    }
                )

    if net <= 0 and gross <= 0:
        return None, [f"Flash Report {filename}: no usable net/gross sales found."]

    return [
        {
            "date": date_str,
            "filename": filename,
            "file_type": "flash_report",
            "gross_total": gross,
            "net_total": net,
            "cash_sales": cash,
            "card_sales": card,
            "gpay_sales": gpay,
            "zomato_sales": zomato,
            "other_sales": other,
            "discount": discount,
            "complimentary": 0.0,
            "cgst": cgst,
            "sgst": sgst,
            "service_charge": service_charge,
            "covers": covers,
            "categories": categories,
            "services": [],
        }
    ], notes
