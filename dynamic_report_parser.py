"""Parse Dynamic Report CSV (per-bill order-level) into daily aggregated records.

Supports two format variants:

  v1 (column-categories): per-bill rows with category-amount columns
    (Food, Liquor, Coffee, etc.) and flat payment columns.

  v2 (line-items): per-item rows with Category Name, Item Name, Item Qty,
    and a summary row per bill carrying financial totals (Pax, Net Amount,
    Gross Sale, CGST, SGST, Service Charge, Gst On Service Charge, etc.).
    **Payment Type** on the summary row drives Cash / Card / GPay / … buckets;
    per-column Cash, Card, UPI, Wallet, etc. are not used (export duplicates).
    Line **Amount** is often '-'; category net is split by qty when no line
    amounts are present.

  One CSV may include multiple **Restaurant** (outlet) values; aggregates are
  split per outlet and each record carries the matching ``restaurant`` string
  for routing in smart upload (see ``config.RESTAURANT_NAME_MAP``).

Usage:
    records, notes = parse_dynamic_report(content, filename)
    # Returns list of per-day dicts ready for save_daily_summary()
"""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


_PAYMENT_MAP_V1 = {
    "cash": "cash_sales",
    "card": "card_sales",
    "online": "gpay_sales",
    "wallet": "zomato_sales",
    "credit": "other_sales",
    "other pmt": "other_sales",
}

_PAYMENT_COLUMN_MAP: Dict[str, str] = {
    "cash": "cash_sales",
    "card": "card_sales",
    "credit": "card_sales",
    "online": "gpay_sales",
    "upi": "gpay_sales",
    "wallet": "gpay_sales",
    "other pmt": "other_sales",
}

def _payment_type_to_sales_field(pay_norm: str) -> Optional[str]:
    """Map normalized Payment Type text to a daily_summaries payment column.

    Per export spec, payment breakdown comes from **Payment Type** only; per-column
    Cash, Card, UPI, etc. must not drive bucketing (those columns may still hold
    redundant totals for Part Payment — we do not read them).
    """
    if not pay_norm or pay_norm in ("nan", "none", "null"):
        return None
    if pay_norm == "part payment":
        return None
    s = pay_norm
    if "zomato" in s or "swiggy" in s:
        return "zomato_sales"
    if (
        "g pay" in s
        or "gpay" in s
        or ("google" in s and "pay" in s)
        or s == "upi"
        or "upi" in s
        or "phonepe" in s
        or "paytm" in s
        or s in ("online", "qr", "bharat qr")
    ):
        return "gpay_sales"
    if (
        "card" in s
        or "credit" in s
        or "debit" in s
        or "amex" in s
        or "visa" in s
        or "master" in s
        or "pos" in s
    ):
        return "card_sales"
    if s == "cash":
        return "cash_sales"
    return "other_sales"


def _buckets_from_payment_columns(
    row: pd.Series, col_map: Dict[str, str]
) -> Dict[str, float]:
    """Read per-column payment amounts on a summary row.

    Returns {bucket: amount} for every mapped column that carries a positive
    numeric value. Used as a backup when the Payment Type cell cannot classify
    the bill, and to proportionally split Part Payment bills across buckets.
    """
    out: Dict[str, float] = defaultdict(float)
    for col_lower, bucket in _PAYMENT_COLUMN_MAP.items():
        orig = col_map.get(col_lower)
        if not orig:
            continue
        amt = _safe_float(row.get(orig))
        if amt > 0:
            out[bucket] += amt
    return dict(out)


_CATEGORY_MAP_V1 = {
    "carft beer": "Craft Beer",
    "coffee": "Coffee",
    "drink": "Drink",
    "food": "Food",
    "liquor": "Liquor",
    "soft drink": "Soft Drink",
    "other": "Other",
}

_SUPER_CATEGORY_MAP = {
    "brazilian bowls": "Food",
    "principais mains": "Food",
    "churrasqueira": "Food",
    "tira gosto": "Food",
    "pao de queijo": "Food",
    "saladas": "Food",
    "side dish": "Food",
    "sobremesas desserts": "Food",
    "acompanhamento & kids menu": "Food",
    "sandwiches": "Food",
    "sake & soju": "Liquor",
    "sake & soju cocktails": "Liquor",
    "house sangria & bellini": "Liquor",
    "signature wine cocktails": "Liquor",
    "red wine": "Liquor",
    "white wine": "Liquor",
    "sparkling wines": "Liquor",
    "meads": "Beer",
    "hot beverages": "Coffee",
    "cold beverages": "Soft Beverages",
    "aerated beverages": "Soft Beverages",
    "mocktails": "Soft Beverages",
    "original brazilian acai mocktails": "Soft Beverages",
}


def _map_to_super_category(category_name: str) -> str:
    key = category_name.strip().lower()
    return _SUPER_CATEGORY_MAP.get(key, category_name.strip() or "Other")


def _safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip()
    if s in ("-", "", "nan", "None"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _safe_int(val: Any) -> int:
    if val is None:
        return 0
    s = str(val).strip()
    if s in ("-", "", "nan", "None"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _is_numeric(val: Any) -> bool:
    s = str(val).strip()
    if s in ("-", "", "nan", "None"):
        return False
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _meal_from_time(ts_val: Any, is_12h: bool = False) -> Optional[str]:
    if ts_val is None:
        return None
    s = str(ts_val).strip()
    if s in ("", "nan", "None"):
        return None
    try:
        ts = pd.Timestamp(s)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    h = ts.hour
    if is_12h:
        # POS uses 12-hour format without AM/PM; pd.Timestamp parses as AM.
        # Restaurant business-hours heuristic:
        #   parsed 12 or 1-5  → noon–5 PM  → Lunch
        #   parsed 6-11       → 6–11 PM    → Dinner
        if 6 <= h <= 11:
            return "Dinner"
        return "Lunch"
    if h < 18:
        return "Lunch"
    return "Dinner"


def _detect_12h_format(df: pd.DataFrame, cdt_col: Optional[str]) -> bool:
    """Return True if all Created Date Time values use 12-hour format (max hour <= 12)."""
    if not cdt_col:
        return False
    max_hour = 0
    for val in df[cdt_col].dropna().head(500):
        s = str(val).strip()
        if s in ("", "nan", "None"):
            continue
        try:
            ts = pd.Timestamp(s)
        except Exception:
            continue
        if pd.isna(ts):
            continue
        if ts.hour > max_hour:
            max_hour = ts.hour
    return max_hour <= 12


def _normalize_date(val: Any) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()[:10]
    if not s or s.lower() in ("nan", "none", ""):
        return None
    try:
        dt = pd.to_datetime(s, dayfirst=False)
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        dt = pd.to_datetime(s, dayfirst=True)
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _norm_pay(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    import re

    return re.sub(r"\s+", " ", str(val).strip().lower())


def _cell_restaurant(row: pd.Series, rest_col: Optional[str]) -> str:
    """Strip CSV Restaurant cell; empty if missing."""
    if not rest_col:
        return ""
    val = row.get(rest_col)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    return s


def _file_default_restaurant(df: pd.DataFrame, rest_col: Optional[str]) -> str:
    """First non-empty Restaurant value in the file (fallback for sparse rows)."""
    if not rest_col or df.empty:
        return ""
    for val in df[rest_col].dropna().head(2000):
        s = str(val).strip()
        if s and s.lower() not in ("nan", "none"):
            return s
    return ""


def _detect_format(col_map: Dict[str, str]) -> str:
    if "category name" in col_map or "item name" in col_map:
        return "v2"
    return "v1"


def _parse_v1(
    df: pd.DataFrame, col_map: Dict[str, str], filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse v1 format: per-bill rows with category-amount columns."""
    notes: List[str] = []
    fallback_count = 0

    required = ["bill date", "bill no", "pax", "net amount", "gross sale"]
    missing = [r for r in required if r not in col_map]
    if missing:
        return None, [f"{filename} missing required columns: {', '.join(missing)}"]

    is_12h = _detect_12h_format(df, col_map.get("created date time"))

    rest_col = col_map.get("restaurant")
    restaurant_name: Optional[str] = None
    if rest_col and not df.empty:
        first_val = str(df[rest_col].iloc[0]).strip()
        if first_val and first_val.lower() not in ("", "nan", "none"):
            restaurant_name = first_val

    if "bill status" in col_map:
        status_col = col_map["bill status"]
        before = len(df)
        df = df[df[status_col].str.strip() == "SuccessOrder"]
        after = len(df)
        notes.append(f"Filtered {before - after} non-SuccessOrder rows from {filename}")
    elif "status" in col_map:
        status_col = col_map["status"]
        before = len(df)
        df = df[df[status_col].str.strip().str.lower() == "success"]
        after = len(df)
        notes.append(f"Filtered {before - after} non-success rows from {filename}")

    if df.empty:
        return None, [f"No SuccessOrder rows found in {filename}"]

    date_col = col_map["bill date"]
    bill_col = col_map["bill no"]
    pax_col = col_map["pax"]
    net_col = col_map["net amount"]
    gross_col = col_map["gross sale"]
    disc_col = col_map.get("discount")
    sc_col = col_map.get("service charge (10)")
    cgst_col = col_map.get("cgst (2.5)")
    sgst_col = col_map.get("sgst (2.5)")
    cdt_col = col_map.get("created date time")

    file_default = _file_default_restaurant(df, rest_col)
    days: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for _, row in df.iterrows():
        date_raw = _normalize_date(row.get(date_col, ""))
        if not date_raw:
            continue

        if rest_col:
            row_rest = _cell_restaurant(row, rest_col) or file_default
            day_key: Tuple[str, str] = (date_raw, row_rest)
        else:
            day_key = (date_raw, "__single__")

        if day_key not in days:
            days[day_key] = {
                "date": date_raw,
                "covers": 0,
                "net_total": 0.0,
                "gross_total": 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "cash_sales": 0.0,
                "card_sales": 0.0,
                "gpay_sales": 0.0,
                "zomato_sales": 0.0,
                "other_sales": 0.0,
                "order_count": 0,
                "bills": set(),
                "categories": {},
                "meals": {},
            }

        day = days[day_key]
        day["covers"] += _safe_int(row.get(pax_col, 0))
        day["net_total"] += _safe_float(row.get(net_col, 0))
        day["gross_total"] += _safe_float(row.get(gross_col, 0))
        day["discount"] += _safe_float(row.get(disc_col, 0)) if disc_col else 0.0
        day["service_charge"] += _safe_float(row.get(sc_col, 0)) if sc_col else 0.0
        day["cgst"] += _safe_float(row.get(cgst_col, 0)) if cgst_col else 0.0
        day["sgst"] += _safe_float(row.get(sgst_col, 0)) if sgst_col else 0.0

        pay_type_col_v1 = col_map.get("payment type")
        if pay_type_col_v1:
            gross_for_pay = _safe_float(row.get(gross_col, 0))
            if gross_for_pay <= 0:
                gross_for_pay = _safe_float(row.get(net_col, 0))
            pk = _norm_pay(row.get(pay_type_col_v1, ""))
            b = None if pk == "part payment" else _payment_type_to_sales_field(pk)
            if b and b != "other_sales":
                day[b] += gross_for_pay
            else:
                col_buckets = _buckets_from_payment_columns(row, col_map)
                col_total = sum(col_buckets.values())
                if col_total > 0:
                    for bk, amt in col_buckets.items():
                        day[bk] += gross_for_pay * (amt / col_total)
                    fallback_count += 1
                elif b:
                    day[b] += gross_for_pay
                else:
                    day["other_sales"] += gross_for_pay
        else:
            for dyn_col, db_field in _PAYMENT_MAP_V1.items():
                if dyn_col in col_map:
                    day[db_field] += _safe_float(row.get(col_map[dyn_col], 0))

        bill_no = str(row.get(bill_col, "")).strip()
        if bill_no and bill_no != "nan":
            day["bills"].add(bill_no)

        for dyn_col, clean_name in _CATEGORY_MAP_V1.items():
            if dyn_col in col_map:
                val = _safe_float(row.get(col_map[dyn_col], 0))
                if val > 0:
                    day["categories"][clean_name] = (
                        day["categories"].get(clean_name, 0.0) + val
                    )

        if cdt_col:
            meal = _meal_from_time(row.get(cdt_col), is_12h=is_12h)
            if meal:
                net_val = _safe_float(row.get(net_col, 0))
                day["meals"][meal] = day["meals"].get(meal, 0.0) + net_val

    results: List[Dict[str, Any]] = []
    for day_key in sorted(days.keys()):
        date_str, outlet_key = day_key
        day = days[day_key]
        bill_count = len(day["bills"])
        categories = [
            {"category": name, "qty": 0, "amount": round(amt, 2)}
            for name, amt in sorted(day["categories"].items(), key=lambda x: -x[1])
        ]
        services = [
            {"type": k, "amount": round(v, 2)}
            for k, v in sorted(day["meals"].items(), key=lambda x: -x[1])
            if v > 0
        ]
        rec_restaurant = (
            restaurant_name if outlet_key == "__single__" else outlet_key
        )
        record = {
            "date": date_str,
            "covers": day["covers"],
            "net_total": round(day["net_total"], 2),
            "gross_total": round(day["gross_total"], 2),
            "discount": round(day["discount"], 2),
            "service_charge": round(day["service_charge"], 2),
            "cgst": round(day["cgst"], 2),
            "sgst": round(day["sgst"], 2),
            "cash_sales": round(day["cash_sales"], 2),
            "card_sales": round(day["card_sales"], 2),
            "gpay_sales": round(day["gpay_sales"], 2),
            "zomato_sales": round(day["zomato_sales"], 2),
            "other_sales": round(day["other_sales"], 2),
            "order_count": bill_count,
            "categories": categories,
            "services": services,
            "top_items": [],
            "file_type": "dynamic_report",
            "restaurant": rec_restaurant,
        }
        results.append(record)

    total_orders = sum(r["order_count"] for r in results)
    total_covers = sum(r["covers"] for r in results)
    n_outlets = len({d[1] for d in days}) if days else 0
    if rest_col and n_outlets > 1:
        notes.append(
            f"Split {filename} across {n_outlets} outlet(s) by Restaurant column."
        )
    notes.append(
        f"Parsed {len(results)} day(s), {total_orders} orders, {total_covers} covers from {filename}"
    )
    if fallback_count:
        notes.append(
            f"Payment column fallback applied to {fallback_count} bill(s) in {filename}"
        )
    return results, notes


def _parse_v2(
    df: pd.DataFrame, col_map: Dict[str, str], filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse v2 format: per-item rows with Category Name, Item Name, and summary row per bill.

    In the v2 format, each bill spans multiple rows (one per item).  Only the
    last row per bill (the "summary row") carries financial totals (Pax, Amount,
    Net Amount, Gross Sale, CGST, SGST, Service Charge, payment columns).
    Intermediate rows have '-' for financial columns.

    Categories and items are extracted from every row.
    """
    notes: List[str] = []
    fallback_count = 0

    date_col = col_map.get("bill date")
    bill_col = col_map.get("bill no")
    pax_col = col_map.get("pax")
    net_col = col_map.get("net amount")
    gross_col = col_map.get("gross sale")
    # Prefer a true per-item amount column ("Item Total", "Line Total", etc.)
    # when present.  Fall back to "Amount" — in Petpooja v2 exports this column
    # is "-" on item rows and holds the bill total on the summary row, so the
    # distribution formula naturally assigns 100 % of bill_net to the summary
    # row's category, matching what a raw CSV pivot would show.
    amount_col = (
        col_map.get("item total")
        or col_map.get("line total")
        or col_map.get("final amount")
        or col_map.get("amount")
    )
    disc_col = col_map.get("discount")
    sc_col = col_map.get("service charge (10)")
    gst_sc_col = col_map.get("gst on service charge (5)")
    cgst_col = col_map.get("cgst (2.5)")
    sgst_col = col_map.get("sgst (2.5)")
    cdt_col = col_map.get("created date time")
    status_col = col_map.get("bill status")
    cat_col = col_map.get("category name")
    item_col = col_map.get("item name")
    qty_col = col_map.get("item qty")
    rest_col = col_map.get("restaurant")
    paytype_col = col_map.get("payment type")
    disc_reason_col = col_map.get("discount reason")
    cancelled_col = col_map.get("cancelled amount")
    comp_col = col_map.get("complementary amount")

    if not date_col:
        return None, [f"{filename} missing Bill Date column"]

    is_12h = _detect_12h_format(df, col_map.get("created date time"))

    file_default = _file_default_restaurant(df, rest_col)
    restaurant_name: Optional[str] = file_default or None

    # Separate complimentary/cancelled rows from success rows
    is_success = pd.Series(True, index=df.index)
    is_complimentary = pd.Series(False, index=df.index)

    if status_col:
        status_vals = df[status_col].fillna("").astype(str).str.strip()
        is_success = status_vals == "SuccessOrder"
        is_complimentary = status_vals.str.lower().str.contains("compli")

    # Build groups: (date, bill_no) then attach outlet from Restaurant so one file
    # can contain multiple outlets without merging their totals.
    groups_raw: Dict[Tuple[str, str], List[int]] = defaultdict(list)

    for idx, row in df.iterrows():
        if not is_success.iloc[idx] and not is_complimentary.iloc[idx]:
            continue
        date_val = _normalize_date(row.get(date_col, ""))
        if not date_val:
            continue
        bill_no = str(row.get(bill_col, "")).strip() if bill_col else ""
        if not bill_no or bill_no.lower() in ("", "nan", "none"):
            bill_no = f"row_{idx}"
        groups_raw[(date_val, bill_no)].append(idx)

    groups: Dict[Tuple[str, str, str], List[int]] = {}
    for (date_val, bill_no), idxs in groups_raw.items():
        bill_rest = ""
        for idx in idxs:
            bill_rest = _cell_restaurant(df.iloc[idx], rest_col)
            if bill_rest:
                break
        if not bill_rest:
            bill_rest = file_default if rest_col else ""
        outlet_key = bill_rest if bill_rest else "__single__"
        groups[(date_val, bill_no, outlet_key)] = idxs

    days: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for (date_str, bill_no, outlet_key), idxs in groups.items():
        day_key = (date_str, outlet_key)
        if day_key not in days:
            days[day_key] = {
                "date": date_str,
                "covers": 0,
                "net_total": 0.0,
                "gross_total": 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "cash_sales": 0.0,
                "card_sales": 0.0,
                "gpay_sales": 0.0,
                "zomato_sales": 0.0,
                "other_sales": 0.0,
                "order_count": 0,
                "complimentary": 0.0,
                "bills": set(),
                "categories": defaultdict(lambda: {"qty": 0, "amount": 0.0}),
                "super_categories": defaultdict(lambda: {"qty": 0, "amount": 0.0}),
                "meals": defaultdict(float),
                "top_items": defaultdict(
                    lambda: {"qty": 0, "amount": 0.0, "category": ""}
                ),
            }

        day = days[day_key]

        is_compli = any(is_complimentary.iloc[idx] for idx in idxs)

        # Find summary row: the row with financial data (Gross Sale or Net Amount is numeric and > 0)
        summary_idx = None
        summary_row = None
        for idx in idxs:
            row = df.iloc[idx]
            gross_val = row.get(gross_col, 0) if gross_col else 0
            net_val = row.get(net_col, 0) if net_col else 0
            if _is_numeric(gross_val) and _safe_float(gross_val) > 0:
                summary_idx = idx
                summary_row = row
                break
            if _is_numeric(net_val) and _safe_float(net_val) > 0:
                summary_idx = idx
                summary_row = row
                break

        # Collect line items for the bill (per-row). We'll distribute bill_net across lines
        # based on per-line Amount when available; otherwise fall back to qty distribution.
        bill_lines: List[Dict[str, Any]] = []  # each line: name, cat, qty, amount
        for idx in idxs:
            row = df.iloc[idx]
            item_qty = max(_safe_int(row.get(qty_col, 1) if qty_col else 1), 1)
            raw_cat = ""
            if cat_col and pd.notna(row.get(cat_col)):
                raw_cat = str(row.get(cat_col)).strip()
            if raw_cat and raw_cat.lower() in ("", "nan", "none"):
                raw_cat = ""

            item_name = ""
            if item_col and pd.notna(row.get(item_col)):
                item_name = str(row.get(item_col)).strip()
            if item_name and item_name.lower() in ("", "nan", "none"):
                item_name = ""

            amount_line = _safe_float(row.get(amount_col, 0)) if amount_col else 0.0
            bill_lines.append(
                {
                    "name": item_name,
                    "cat": raw_cat,
                    "qty": item_qty,
                    "amount": amount_line,
                }
            )

        # Complimentary bills: add gross to complimentary, no revenue
        if is_compli:
            if summary_row is not None:
                compli_amt = 0.0
                if comp_col and pd.notna(summary_row.get(comp_col)):
                    compli_amt = _safe_float(summary_row.get(comp_col))
                if compli_amt <= 0 and gross_col:
                    compli_amt = _safe_float(summary_row.get(gross_col))
                day["complimentary"] += compli_amt
            continue

        # Skip bills with no summary row (no financial data)
        if summary_row is None:
            notes.append(
                f"Skipping bill {bill_no} on {date_str}: no financial summary row"
            )
            continue

        # Extract bill-level financials from summary row
        pax = _safe_int(summary_row.get(pax_col, 0)) if pax_col else 0
        day["covers"] += pax
        bill_net = _safe_float(summary_row.get(net_col, 0)) if net_col else 0.0
        day["net_total"] += bill_net
        day["gross_total"] += (
            _safe_float(summary_row.get(gross_col, 0)) if gross_col else 0.0
        )
        day["discount"] += (
            _safe_float(summary_row.get(disc_col, 0)) if disc_col else 0.0
        )
        day["service_charge"] += (
            _safe_float(summary_row.get(sc_col, 0)) if sc_col else 0.0
        )
        day["cgst"] += _safe_float(summary_row.get(cgst_col, 0)) if cgst_col else 0.0
        day["sgst"] += _safe_float(summary_row.get(sgst_col, 0)) if sgst_col else 0.0
        gst_sc_amt = (
            _safe_float(summary_row.get(gst_sc_col, 0)) if gst_sc_col else 0.0
        )
        if gst_sc_amt > 0:
            day["cgst"] += gst_sc_amt / 2.0
            day["sgst"] += gst_sc_amt / 2.0
        day["complimentary"] += (
            _safe_float(summary_row.get(comp_col, 0)) if comp_col else 0.0
        )

        # Distribute bill net across lines: by Amount when present; else by Item Qty
        # (line Amount is often '-' per export spec).
        total_amount = sum(lv["amount"] for lv in bill_lines if lv["amount"] > 0)
        alloc_lines = [lv for lv in bill_lines if lv["cat"] or lv["name"]]
        total_qty = sum(max(int(lv["qty"]), 1) for lv in alloc_lines)

        for line in bill_lines:
            qty = line["qty"]
            cat = line["cat"]
            name = line["name"]
            amount_line = line["amount"]
            if total_amount > 0 and amount_line > 0:
                share = bill_net * amount_line / total_amount
            elif total_amount <= 0 and total_qty > 0 and (cat or name):
                w = max(int(qty), 1)
                share = bill_net * (w / total_qty)
            else:
                share = 0.0
            if cat:
                day["categories"][cat]["qty"] += qty
                day["categories"][cat]["amount"] += share
                super_cat = _map_to_super_category(cat)
                if super_cat != cat:
                    day["super_categories"][super_cat]["qty"] += qty
                    day["super_categories"][super_cat]["amount"] += share
            if name:
                cat_for_item = cat or ""
                day["top_items"][name]["qty"] += qty
                day["top_items"][name]["amount"] += share
                day["top_items"][name]["category"] = cat_for_item

        # Payment breakdown — Payment Type is the source of truth; per-column
        # payment headers (Cash, Card, Credit, Wallet, Online, UPI, Other Pmt)
        # are a strict backup when Payment Type cannot classify, and drive the
        # proportional split for Part Payment bills.
        gross_val = _safe_float(summary_row.get(gross_col, 0)) if gross_col else 0.0
        if gross_val <= 0:
            net_val_pay = _safe_float(summary_row.get(net_col, 0)) if net_col else 0.0
            gross_val = net_val_pay if net_val_pay > 0 else 0.0

        pay_type_raw = ""
        if paytype_col and pd.notna(summary_row.get(paytype_col)):
            pay_type_raw = str(summary_row.get(paytype_col)).strip()
        pay_key = _norm_pay(pay_type_raw)

        bucket = (
            None if pay_key == "part payment" else _payment_type_to_sales_field(pay_key)
        )

        if bucket and bucket != "other_sales":
            day[bucket] += gross_val
        else:
            col_buckets = _buckets_from_payment_columns(summary_row, col_map)
            col_total = sum(col_buckets.values())
            if col_total > 0:
                for b, amt in col_buckets.items():
                    day[b] += gross_val * (amt / col_total)
                fallback_count += 1
            elif bucket:
                day[bucket] += gross_val
            else:
                day["other_sales"] += gross_val

        # Track unique bills
        day["bills"].add(bill_no)

        # Meal period (service breakdown) from summary row's Created Date Time
        if cdt_col:
            meal = _meal_from_time(summary_row.get(cdt_col), is_12h=is_12h)
            net_val = _safe_float(summary_row.get(net_col, 0)) if net_col else 0.0
            if meal and net_val > 0:
                day["meals"][meal] += net_val

    # Build output records
    results: List[Dict[str, Any]] = []
    for day_key in sorted(days.keys()):
        date_str, outlet_key = day_key
        day = days[day_key]
        bill_count = len(day["bills"])

        categories = [
            {"category": name, "qty": int(v["qty"]), "amount": round(v["amount"], 2)}
            for name, v in sorted(day["categories"].items(), key=lambda x: -x[1]["qty"])
        ]

        super_cats = [
            {"category": name, "qty": int(v["qty"]), "amount": round(v["amount"], 2)}
            for name, v in sorted(
                day["super_categories"].items(), key=lambda x: -x[1]["qty"]
            )
        ]

        top_items = [
            {
                "item_name": name,
                "qty": int(v["qty"]),
                "amount": round(v["amount"], 2),
                "category": v.get("category", ""),
            }
            for name, v in sorted(day["top_items"].items(), key=lambda x: -x[1]["qty"])[
                :30
            ]
        ]

        services = [
            {"type": k, "amount": round(v, 2)}
            for k, v in sorted(day["meals"].items(), key=lambda x: -x[1])
            if v > 0
        ]

        rec_restaurant = (
            restaurant_name if outlet_key == "__single__" else outlet_key
        )

        record = {
            "date": date_str,
            "covers": day["covers"],
            "net_total": round(day["net_total"], 2),
            "gross_total": round(day["gross_total"], 2),
            "discount": round(day["discount"], 2),
            "service_charge": round(day["service_charge"], 2),
            "cgst": round(day["cgst"], 2),
            "sgst": round(day["sgst"], 2),
            "cash_sales": round(day["cash_sales"], 2),
            "card_sales": round(day["card_sales"], 2),
            "gpay_sales": round(day["gpay_sales"], 2),
            "zomato_sales": round(day["zomato_sales"], 2),
            "other_sales": round(day["other_sales"], 2),
            "complimentary": round(day["complimentary"], 2),
            "order_count": bill_count,
            "categories": categories,
            "super_categories": super_cats,
            "services": services,
            "top_items": top_items,
            "file_type": "dynamic_report",
            "restaurant": rec_restaurant,
        }
        results.append(record)

    total_orders = sum(r["order_count"] for r in results)
    total_covers = sum(r["covers"] for r in results)
    n_outlets = len({d[1] for d in days}) if days else 0
    fmt_note = "line-item" if "category name" in col_map else "column-category"
    if rest_col and n_outlets > 1:
        notes.append(
            f"Split {filename} across {n_outlets} outlet(s) by Restaurant column."
        )
    notes.append(
        f"Parsed {len(results)} day(s), {total_orders} orders, {total_covers} covers "
        f"from {filename} ({fmt_note} format)"
    )
    if fallback_count:
        notes.append(
            f"Payment column fallback applied to {fallback_count} bill(s) in {filename}"
        )
    return results, notes


def parse_dynamic_report(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse Dynamic Report CSV into per-day aggregated records.

    Supports both v1 (column-based categories) and v2 (line-item categories/items).

    Args:
        content: Raw CSV bytes
        filename: Original filename (for error messages)

    Returns:
        Tuple of (list of per-day dicts, list of notes/warnings)
        Returns (None, notes) on fatal error.
    """
    notes: List[str] = []

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return None, [f"Cannot decode {filename}: not valid UTF-8"]

    try:
        df = pd.read_csv(StringIO(text), dtype=str)
    except Exception as ex:
        return None, [f"Cannot parse {filename} as CSV: {ex}"]

    if df.empty:
        return None, [f"{filename} is empty"]

    df.columns = [c.strip() for c in df.columns]
    col_map = {c.lower(): c for c in df.columns}

    fmt = _detect_format(col_map)

    if fmt == "v2":
        notes.append(f"Detected Dynamic Report v2 format (line-item) in {filename}")
        return _parse_v2(df, col_map, filename)
    else:
        notes.append(
            f"Detected Dynamic Report v1 format (column-category) in {filename}"
        )
        return _parse_v1(df, col_map, filename)


def parse_dynamic_report_raw(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse Dynamic Report CSV and return raw bill items for the new schema.

    Returns list of bill_items records ready to insert into the database.

    Args:
        content: Raw CSV bytes
        filename: Original filename (for error messages)

    Returns:
        Tuple of (list of bill_items records, list of notes/warnings)
    """
    notes: List[str] = []

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return None, [f"Cannot decode {filename}: not valid UTF-8"]

    try:
        df = pd.read_csv(StringIO(text), dtype=str)
    except Exception as ex:
        return None, [f"Cannot parse {filename} as CSV: {ex}"]

    if df.empty:
        return None, [f"{filename} is empty"]

    df.columns = [c.strip() for c in df.columns]

    bill_items_records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        restaurant = str(row.get("Restaurant", "")).strip()
        bill_date = str(row.get("Bill Date", "")).strip()
        bill_no = str(row.get("Bill No", "")).strip()
        server_name = (
            str(row.get("Server Name", "")).strip()
            if pd.notna(row.get("Server Name"))
            else ""
        )
        table_no = (
            str(row.get("Table No", "")).strip()
            if pd.notna(row.get("Table No"))
            else ""
        )
        bill_status = (
            str(row.get("Bill Status", "")).strip()
            if pd.notna(row.get("Bill Status"))
            else ""
        )
        payment_type = (
            str(row.get("Payment Type", "")).strip()
            if pd.notna(row.get("Payment Type"))
            else ""
        )
        category_name = (
            str(row.get("Category Name", "")).strip()
            if pd.notna(row.get("Category Name"))
            else ""
        )
        item_name = (
            str(row.get("Item Name", "")).strip()
            if pd.notna(row.get("Item Name"))
            else ""
        )

        item_qty = _safe_int(row.get("Item Qty", "0"))
        pax = _safe_int(row.get("Pax", "0"))
        discount_reason = (
            str(row.get("Discount Reason", "")).strip()
            if pd.notna(row.get("Discount Reason"))
            else ""
        )
        created_date_time = (
            str(row.get("Created Date Time", "")).strip()
            if pd.notna(row.get("Created Date Time"))
            else ""
        )

        net_amount = _safe_float(row.get("Net Amount", "0"))
        gross_amount = _safe_float(row.get("Gross Sale", "0"))
        discount = _safe_float(row.get("Discount", "0"))
        cgst = _safe_float(row.get("CGST (2.5)", "0"))
        sgst = _safe_float(row.get("SGST (2.5)", "0"))
        service_charge = _safe_float(row.get("Service Charge (10)", "0"))
        gst_on_sc = _safe_float(row.get("Gst On Service Charge (5)", "0"))
        cancelled_amount = _safe_float(row.get("Cancelled Amount", "0"))
        complementary_amount = _safe_float(row.get("Complementary Amount", "0"))

        bill_items_records.append(
            {
                "restaurant": restaurant,
                "bill_date": bill_date,
                "bill_no": bill_no,
                "server_name": server_name or None,
                "table_no": table_no or None,
                "bill_status": bill_status,
                "payment_type": payment_type or None,
                "category_name": category_name or None,
                "item_name": item_name or None,
                "item_qty": item_qty,
                "pax": pax,
                "discount_reason": discount_reason or None,
                "created_date_time": created_date_time or None,
                "net_amount": net_amount,
                "gross_amount": gross_amount,
                "discount": discount,
                "cgst": cgst,
                "sgst": sgst,
                "service_charge": service_charge,
                "gst_on_service_charge": gst_on_sc,
                "cancelled_amount": cancelled_amount,
                "complementary_amount": complementary_amount,
            }
        )

    notes.append(f"Parsed {len(bill_items_records)} raw records from {filename}")
    return bill_items_records, notes
