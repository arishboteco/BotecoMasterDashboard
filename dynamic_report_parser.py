"""Parse Dynamic Report CSV (per-bill order-level) into daily aggregated records.

Supports two format variants:

  v1 (column-categories): per-bill rows with category-amount columns
    (Food, Liquor, Coffee, etc.) and flat payment columns.

  v2 (line-items): per-item rows with Category Name, Item Name, Item Qty,
    and a summary row per bill carrying financial totals (Pax, Amount,
    Net Amount, Gross Sale, CGST, etc.).  The new format also has
    UPI, Online, Wallet, Credit, Complementary Amount columns.

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

_PAYMENT_TYPE_BUCKET = {
    "cash": "cash_sales",
    "card": "card_sales",
    "other (g  pay)": "gpay_sales",
    "other (g pay)": "gpay_sales",
    "other (zomato)": "zomato_sales",
    "other (boh)": "other_sales",
    "upi": "gpay_sales",
}

_PAYMENT_COL_BUCKET = {
    "cash": "cash_sales",
    "card": "card_sales",
    "credit": "other_sales",
    "other pmt": "other_sales",
    "wallet": "zomato_sales",
    "online": "gpay_sales",
    "upi": "gpay_sales",
}

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


def _meal_from_time(ts_val: Any) -> Optional[str]:
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
    if ts.hour < 18:
        return "Lunch"
    return "Dinner"


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


def _detect_format(col_map: Dict[str, str]) -> str:
    if "category name" in col_map or "item name" in col_map:
        return "v2"
    return "v1"


def _parse_v1(
    df: pd.DataFrame, col_map: Dict[str, str], filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse v1 format: per-bill rows with category-amount columns."""
    notes: List[str] = []

    required = ["bill date", "bill no", "pax", "net amount", "gross sale"]
    missing = [r for r in required if r not in col_map]
    if missing:
        return None, [f"{filename} missing required columns: {', '.join(missing)}"]

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

    days: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        date_raw = _normalize_date(row.get(date_col, ""))
        if not date_raw:
            continue

        if date_raw not in days:
            days[date_raw] = {
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

        day = days[date_raw]
        day["covers"] += _safe_int(row.get(pax_col, 0))
        day["net_total"] += _safe_float(row.get(net_col, 0))
        day["gross_total"] += _safe_float(row.get(gross_col, 0))
        day["discount"] += _safe_float(row.get(disc_col, 0)) if disc_col else 0.0
        day["service_charge"] += _safe_float(row.get(sc_col, 0)) if sc_col else 0.0
        day["cgst"] += _safe_float(row.get(cgst_col, 0)) if cgst_col else 0.0
        day["sgst"] += _safe_float(row.get(sgst_col, 0)) if sgst_col else 0.0

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
            meal = _meal_from_time(row.get(cdt_col))
            if meal:
                net_val = _safe_float(row.get(net_col, 0))
                day["meals"][meal] = day["meals"].get(meal, 0.0) + net_val

    results: List[Dict[str, Any]] = []
    for date_str in sorted(days.keys()):
        day = days[date_str]
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
            "restaurant": restaurant_name,
        }
        results.append(record)

    total_orders = sum(r["order_count"] for r in results)
    total_covers = sum(r["covers"] for r in results)
    notes.append(
        f"Parsed {len(results)} day(s), {total_orders} orders, {total_covers} covers from {filename}"
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

    date_col = col_map.get("bill date")
    bill_col = col_map.get("bill no")
    pax_col = col_map.get("pax")
    net_col = col_map.get("net amount")
    gross_col = col_map.get("gross sale")
    amount_col = (
        col_map.get("amount")
        or col_map.get("total")
        or col_map.get("item total")
        or col_map.get("line total")
        or col_map.get("final amount")
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

    restaurant_name: Optional[str] = None
    if rest_col and not df.empty:
        first_val = str(df[rest_col].iloc[0]).strip()
        if first_val and first_val.lower() not in ("", "nan", "none"):
            restaurant_name = first_val

    # Separate complimentary/cancelled rows from success rows
    is_success = pd.Series(True, index=df.index)
    is_complimentary = pd.Series(False, index=df.index)

    if status_col:
        status_vals = df[status_col].fillna("").astype(str).str.strip()
        is_success = status_vals == "SuccessOrder"
        is_complimentary = status_vals.str.lower().str.contains("compli")

    # Build groups: each bill_no on a date has its own group
    # We'll process success and complimentary separately
    groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)

    for idx, row in df.iterrows():
        if not is_success.iloc[idx] and not is_complimentary.iloc[idx]:
            continue
        date_val = _normalize_date(row.get(date_col, ""))
        if not date_val:
            continue
        bill_no = str(row.get(bill_col, "")).strip() if bill_col else ""
        if not bill_no or bill_no.lower() in ("", "nan", "none"):
            bill_no = f"row_{idx}"
        groups[(date_val, bill_no)].append(idx)

    days: Dict[str, Dict[str, Any]] = {}

    for (date_str, bill_no), idxs in groups.items():
        if date_str not in days:
            days[date_str] = {
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

        day = days[date_str]

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

        # Collect items and categories from ALL rows in the bill
        for idx in idxs:
            row = df.iloc[idx]
            item_qty = max(_safe_int(row.get(qty_col, 1) if qty_col else 1), 1)
            item_amount = _safe_float(row.get(amount_col, 0)) if amount_col else 0.0
            raw_cat = ""
            if cat_col and pd.notna(row.get(cat_col)):
                raw_cat = str(row.get(cat_col)).strip()
            if raw_cat and raw_cat.lower() not in ("", "nan", "none"):
                day["categories"][raw_cat]["qty"] += item_qty
                day["categories"][raw_cat]["amount"] += item_amount
                super_cat = _map_to_super_category(raw_cat)
                if super_cat != raw_cat:
                    day["super_categories"][super_cat]["qty"] += item_qty
                    day["super_categories"][super_cat]["amount"] += item_amount

            item_name = ""
            if item_col and pd.notna(row.get(item_col)):
                item_name = str(row.get(item_col)).strip()
            if item_name and item_name.lower() not in ("", "nan", "none"):
                cat_for_item = (
                    raw_cat
                    if raw_cat and raw_cat.lower() not in ("", "nan", "none")
                    else ""
                )
                day["top_items"][item_name]["qty"] += item_qty
                day["top_items"][item_name]["amount"] += item_amount
                day["top_items"][item_name]["category"] = cat_for_item

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
        day["net_total"] += _safe_float(summary_row.get(net_col, 0)) if net_col else 0.0
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
        day["complimentary"] += (
            _safe_float(summary_row.get(comp_col, 0)) if comp_col else 0.0
        )

        # Payment breakdown — use Payment Type to bucket each bill's Gross Sale
        gross_val = _safe_float(summary_row.get(gross_col, 0)) if gross_col else 0.0
        if gross_val <= 0:
            net_val_pay = _safe_float(summary_row.get(net_col, 0)) if net_col else 0.0
            gross_val = net_val_pay if net_val_pay > 0 else 0.0

        pay_type_raw = ""
        if paytype_col and pd.notna(summary_row.get(paytype_col)):
            pay_type_raw = str(summary_row.get(paytype_col)).strip()

        pay_key = _norm_pay(pay_type_raw)

        if pay_key == "part payment":
            # Part Payment: split across individual payment columns
            for dyn_col, db_field in _PAYMENT_COL_BUCKET.items():
                if dyn_col in col_map:
                    val = _safe_float(summary_row.get(col_map[dyn_col], 0))
                    day[db_field] += val
        elif pay_key in _PAYMENT_TYPE_BUCKET:
            bucket = _PAYMENT_TYPE_BUCKET[pay_key]
            day[bucket] += gross_val
        elif pay_key in ("", "nan", "none"):
            pass  # No payment type — leave unbilled
        else:
            # Unknown payment type: bucket as other_sales
            day["other_sales"] += gross_val

        # Track unique bills
        day["bills"].add(bill_no)

        # Meal period (service breakdown) from summary row's Created Date Time
        if cdt_col:
            meal = _meal_from_time(summary_row.get(cdt_col))
            net_val = _safe_float(summary_row.get(net_col, 0)) if net_col else 0.0
            if meal and net_val > 0:
                day["meals"][meal] += net_val

    # Build output records
    results: List[Dict[str, Any]] = []
    for date_str in sorted(days.keys()):
        day = days[date_str]
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
            "restaurant": restaurant_name,
        }
        results.append(record)

    total_orders = sum(r["order_count"] for r in results)
    total_covers = sum(r["covers"] for r in results)
    fmt_note = "line-item" if "category name" in col_map else "column-category"
    notes.append(
        f"Parsed {len(results)} day(s), {total_orders} orders, {total_covers} covers "
        f"from {filename} ({fmt_note} format)"
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
