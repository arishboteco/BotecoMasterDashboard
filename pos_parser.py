import re
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd


def _f(val: Any) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    s = str(val).replace(",", "").replace("₹", "").replace("Γé╣", "").strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _i(val: Any) -> int:
    return int(round(_f(val)))


def _norm_header(h: Any) -> str:
    if h is None or (isinstance(h, float) and pd.isna(h)):
        return ""
    return re.sub(r"\s+", " ", str(h).strip().lower())


def _parse_date(val: str) -> Optional[str]:
    val = str(val).strip()
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%b-%d-%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _cell_date_to_iso(val: Any) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip().lower()
    if s == "total" or s == "nan":
        return None
    ts = pd.to_datetime(val, errors="coerce")
    if pd.isna(ts):
        return _parse_date(str(val).strip())
    return ts.strftime("%Y-%m-%d")


def _load_tabular(file_content: bytes, filename: str) -> Optional[pd.DataFrame]:
    """Load first sheet into a single DataFrame without header."""
    bio = BytesIO(file_content)
    head = file_content[:2500].lower()
    if b"<html" in head or b"<!doctype html" in head:
        try:
            bio.seek(0)
            dfs = pd.read_html(bio, flavor="lxml")
        except Exception:
            try:
                bio.seek(0)
                dfs = pd.read_html(bio)
            except Exception:
                return None
        if not dfs:
            return None
        return pd.concat(dfs, ignore_index=True)
    try:
        return pd.read_excel(bio, sheet_name=0, header=None, engine=None)
    except Exception:
        try:
            bio.seek(0)
            return pd.read_excel(bio, sheet_name=0, header=None, engine="openpyxl")
        except Exception:
            try:
                bio.seek(0)
                return pd.read_excel(bio, sheet_name=0, header=None, engine="xlrd")
            except Exception:
                return None


def _header_map_row(df: pd.DataFrame, header_idx: int) -> Dict[str, int]:
    row = df.iloc[header_idx]
    out: Dict[str, int] = {}
    for i, v in enumerate(row):
        k = _norm_header(v)
        if k:
            out[k] = i
    return out


def _normalize_group_category(group_name: str) -> str:
    g = group_name.lower()
    if "coffee" in g or g.strip() == "coffee":
        return "Coffee"
    if "beer" in g:
        return "Beer"
    if "liquor" in g or "spirit" in g or "wine" in g:
        return "Liquor"
    if "tobacco" in g:
        return "Tobacco"
    if "soft" in g or "drink" in g or "beverage" in g:
        return "Soft Beverages"
    if "food" in g:
        return "Food"
    return group_name.strip() or "Other"


def _payment_bucket(payment_raw: str) -> str:
    s = _norm_header(payment_raw)
    if not s:
        return "other"
    if s == "cash":
        return "cash"
    if "zomato" in s:
        return "zomato"
    if "g pay" in s or "gpay" in s or ("google" in s and "pay" in s):
        return "gpay"
    if "card" in s or "credit" in s or "debit" in s or "amex" in s:
        return "card"
    return "other"


def _meal_from_timestamp(ts_val: Any) -> Optional[str]:
    if ts_val is None or (isinstance(ts_val, float) and pd.isna(ts_val)):
        return None
    try:
        ts = pd.Timestamp(ts_val)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    h = int(ts.hour)
    if h < 12:
        return "Breakfast"
    if h < 15:
        return "Lunch"
    return "Dinner"


def detect_file_kind(filename: str) -> str:
    n = filename.lower()
    if (
        "customerorder" in n
        or "customer_order" in n
        or "item_report_with_customer" in n
    ):
        return "item_order_details"
    return "unknown"


def parse_item_order_details(
    file_content: bytes, filename: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Item Report With Customer/Order Details: line-item rows, multiple days per file.
    net_total = sum(Sub Total), gross_total = sum(Final Total) for Success rows.
    Complimentary rows contribute to complimentary only.
    """
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    header_idx = None
    for i in range(min(35, len(df))):
        parts = [_norm_header(x) for x in df.iloc[i].values if _norm_header(x)]
        joined = " ".join(parts)
        if "sub total" in joined and "final total" in joined:
            header_idx = i
            break
    if header_idx is None:
        return None

    colmap = _header_map_row(df, header_idx)

    def col(*needles: str) -> Optional[int]:
        for key, idx in colmap.items():
            if all(n in key for n in needles):
                return idx
        for key, idx in colmap.items():
            if any(n in key for n in needles):
                return idx
        return None

    idx_date = colmap.get("date") if "date" in colmap else col("date")
    idx_ts = colmap.get("timestamp") or col("time")
    idx_inv = col("invoice", "no") or col("invoice")
    idx_pay = colmap.get("payment type") or col("payment")
    idx_status = colmap.get("status") or col("status")
    idx_sub = colmap.get("sub total") or col("sub", "total")
    idx_disc = colmap.get("discount") or col("discount")
    idx_tax = colmap.get("tax") or col("tax")
    idx_final = colmap.get("final total") or col("final", "total")
    idx_covers = colmap.get("covers") or col("covers")
    idx_cat = colmap.get("category") or col("category")
    idx_group = colmap.get("group name") or col("group")
    idx_qty = colmap.get("qty.") or colmap.get("qty") or col("qty")
    idx_item = (
        colmap.get("item name")
        or colmap.get("item")
        or col("item", "name")
        or col("item")
    )

    required = [idx_date, idx_sub, idx_final, idx_status]
    if any(x is None for x in required):
        return None

    DayAgg = Dict[str, Any]
    days: Dict[str, DayAgg] = {}

    def day_bucket(d: str) -> DayAgg:
        if d not in days:
            days[d] = {
                "net": 0.0,
                "gross": 0.0,
                "cash": 0.0,
                "card": 0.0,
                "gpay": 0.0,
                "zomato": 0.0,
                "other": 0.0,
                "discount": 0.0,
                "tax": 0.0,
                "complimentary": 0.0,
                "inv_covers": defaultdict(float),
                "invoices": set(),
                "categories": defaultdict(lambda: {"qty": 0, "amount": 0.0}),
                "meal": defaultdict(float),
                "items": defaultdict(lambda: {"qty": 0, "amount": 0.0}),
            }
        return days[d]

    for ri in range(header_idx + 1, len(df)):
        row = df.iloc[ri]
        dcell = row.iloc[idx_date]
        if pd.isna(dcell):
            continue
        if str(dcell).strip().lower() == "total":
            continue
        day = _cell_date_to_iso(dcell)
        if not day:
            continue

        st = _norm_header(row.iloc[idx_status] if idx_status is not None else "")
        is_complimentary = "complimentary" in st
        is_success = st == "success"

        sub = _f(row.iloc[idx_sub])
        final = _f(row.iloc[idx_final])
        disc = _f(row.iloc[idx_disc]) if idx_disc is not None else 0.0
        tax = _f(row.iloc[idx_tax]) if idx_tax is not None else 0.0
        pay_raw = str(row.iloc[idx_pay]).strip() if idx_pay is not None else ""
        inv_key = str(row.iloc[idx_inv]).strip() if idx_inv is not None else f"row_{ri}"
        qty = _i(row.iloc[idx_qty]) if idx_qty is not None else 0
        cov = _f(row.iloc[idx_covers]) if idx_covers is not None else 0.0

        cat_cell = ""
        if idx_cat is not None and pd.notna(row.iloc[idx_cat]):
            cat_cell = str(row.iloc[idx_cat]).strip()
        if not cat_cell and idx_group is not None and pd.notna(row.iloc[idx_group]):
            cat_cell = str(row.iloc[idx_group]).strip()
        cat_name = _normalize_group_category(cat_cell) if cat_cell else "Other"

        b = day_bucket(day)

        if is_complimentary:
            b["complimentary"] += final
            continue

        if not is_success:
            continue

        b["net"] += sub
        b["gross"] += final
        b["discount"] += disc
        b["tax"] += tax

        bucket = _payment_bucket(pay_raw)
        if bucket == "cash":
            b["cash"] += final
        elif bucket == "card":
            b["card"] += final
        elif bucket == "gpay":
            b["gpay"] += final
        elif bucket == "zomato":
            b["zomato"] += final
        else:
            b["other"] += final

        if cov > 0:
            b["inv_covers"][inv_key] = max(b["inv_covers"][inv_key], cov)

        # Count unique orders (invoices)
        b["invoices"].add(inv_key)

        bc = b["categories"][cat_name]
        bc["qty"] += max(qty, 1) if sub > 0 else qty
        bc["amount"] += sub

        # Item-level tracking for top-sellers
        if idx_item is not None and pd.notna(row.iloc[idx_item]):
            item_name = str(row.iloc[idx_item]).strip()
            if item_name and item_name.lower() not in ("nan", ""):
                bi = b["items"][item_name]
                bi["qty"] += max(qty, 1) if sub > 0 else qty
                bi["amount"] += sub

        if idx_ts is not None:
            meal = _meal_from_timestamp(row.iloc[idx_ts])
            if meal:
                b["meal"][meal] += final

    out: List[Dict[str, Any]] = []
    for d in sorted(days.keys()):
        b = days[d]
        if b["net"] <= 0 and b["gross"] <= 0:
            continue
        covers = int(sum(b["inv_covers"].values()))
        order_count = len(b["invoices"])
        tax_sum = b["tax"]
        half = tax_sum / 2.0
        categories = [
            {"category": k, "qty": int(v["qty"]), "amount": v["amount"]}
            for k, v in sorted(b["categories"].items(), key=lambda x: -x[1]["amount"])
        ]
        services = [
            {"type": k, "amount": v}
            for k, v in sorted(b["meal"].items(), key=lambda x: -x[1])
            if v > 0
        ]
        # Top 20 items by revenue (stored for item_sales table)
        top_items = [
            {"item_name": k, "qty": int(v["qty"]), "amount": v["amount"]}
            for k, v in sorted(b["items"].items(), key=lambda x: -x[1]["amount"])[:20]
        ]
        out.append(
            {
                "date": d,
                "filename": filename,
                "file_type": "item_order_details",
                "gross_total": b["gross"],
                "net_total": b["net"],
                "cash_sales": b["cash"],
                "card_sales": b["card"],
                "gpay_sales": b["gpay"],
                "zomato_sales": b["zomato"],
                "other_sales": b["other"],
                "discount": b["discount"],
                "complimentary": b["complimentary"],
                "cgst": half,
                "sgst": half,
                "service_charge": 0.0,
                "covers": covers,
                "order_count": order_count,
                "categories": categories,
                "services": services,
                "top_items": top_items,
            }
        )

    return out if out else None


_MERGE_PRIORITY = {
    "item_order_details": 10,
}

_NUMERIC_SUM_KEYS = (
    "gross_total",
    "net_total",
    "cash_sales",
    "card_sales",
    "gpay_sales",
    "zomato_sales",
    "other_sales",
    "discount",
    "complimentary",
    "cgst",
    "sgst",
    "service_charge",
    "covers",
    "order_count",
)


def _merge_category_lists(
    a: List[Dict[str, Any]], b: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    m: Dict[str, Dict[str, Any]] = {}
    for c in a:
        k = c.get("category") or "Other"
        m[k] = {"qty": int(c.get("qty", 0)), "amount": float(c.get("amount", 0))}
    for c in b:
        k = c.get("category") or "Other"
        if k not in m:
            m[k] = {"qty": 0, "amount": 0.0}
        m[k]["qty"] += int(c.get("qty", 0))
        m[k]["amount"] += float(c.get("amount", 0))
    return [
        {"category": k, "qty": int(v["qty"]), "amount": v["amount"]}
        for k, v in sorted(m.items(), key=lambda x: -x[1]["amount"])
    ]


def _merge_service_lists(
    a: List[Dict[str, Any]], b: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    amt: Dict[str, float] = defaultdict(float)
    for s in a or []:
        amt[str(s.get("type", ""))] += float(s.get("amount", 0) or 0)
    for s in b or []:
        amt[str(s.get("type", ""))] += float(s.get("amount", 0) or 0)
    return [
        {"type": k, "amount": v}
        for k, v in sorted(amt.items(), key=lambda x: -x[1])
        if v > 0
    ]


def _merge_item_lists(
    a: List[Dict[str, Any]], b: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge two top-items lists, keeping top 20 by amount."""
    m: Dict[str, Dict[str, Any]] = {}
    for item in a or []:
        k = item.get("item_name") or ""
        if not k:
            continue
        if k not in m:
            m[k] = {"qty": 0, "amount": 0.0}
        m[k]["qty"] += int(item.get("qty", 0))
        m[k]["amount"] += float(item.get("amount", 0) or 0)
    for item in b or []:
        k = item.get("item_name") or ""
        if not k:
            continue
        if k not in m:
            m[k] = {"qty": 0, "amount": 0.0}
        m[k]["qty"] += int(item.get("qty", 0))
        m[k]["amount"] += float(item.get("amount", 0) or 0)
    return [
        {"item_name": k, "qty": int(v["qty"]), "amount": v["amount"]}
        for k, v in sorted(m.items(), key=lambda x: -x[1]["amount"])[:20]
    ]


def merge_upload_fragments(fragments: List[Dict]) -> Dict[str, Any]:
    """Merge parser outputs for one business day (same date)."""
    fragments = [f for f in fragments if f and f.get("date")]
    if not fragments:
        return {}
    fragments.sort(key=lambda f: _MERGE_PRIORITY.get(f.get("file_type", ""), 100))

    first = fragments[0]
    merged: Dict[str, Any] = {"date": first["date"]}
    for k, v in first.items():
        if k in ("filename", "file_type"):
            continue
        if k == "date":
            continue
        if v is None:
            continue
        merged[k] = v

    for frag in fragments[1:]:
        ft = frag.get("file_type")
        for k in _NUMERIC_SUM_KEYS:
            if k not in merged:
                merged[k] = frag.get(k) or 0
                continue
            merged[k] = float(merged.get(k) or 0) + float(frag.get(k) or 0)
        if ft == "item_order_details":
            merged["categories"] = _merge_category_lists(
                merged.get("categories") or [], frag.get("categories") or []
            )
            merged["services"] = _merge_service_lists(
                merged.get("services") or [], frag.get("services") or []
            )
            merged["top_items"] = _merge_item_lists(
                merged.get("top_items") or [], frag.get("top_items") or []
            )
    return merged


ParseResult = Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]


def parse_upload_file(file_content: bytes, filename: str) -> ParseResult:
    kind = detect_file_kind(filename)
    if kind == "item_order_details":
        return parse_item_order_details(file_content, filename)
    return None


def group_fragments_by_date(fragments: List[Dict]) -> Dict[str, List[Dict]]:
    buckets: Dict[str, List[Dict]] = {}
    for f in fragments:
        d = f.get("date")
        if not d:
            continue
        buckets.setdefault(d, []).append(f)
    return buckets


def process_upload_batch(
    files: List[Tuple[str, bytes]],
) -> Tuple[List[Tuple[str, Dict, List[str]]], List[str]]:
    """
    Parse uploads; merge by date. Returns list of (date, merged_data, errors_per_day)
    and global messages (skipped files).
    """
    from collections import Counter

    fragments: List[Dict] = []
    notes: List[str] = []

    for name, content in files:
        try:
            parsed = parse_upload_file(content, name)
            if parsed is None:
                notes.append(
                    f"Skipped (not Item Report with Customer/Order Details): {name}"
                )
            elif isinstance(parsed, list):
                fragments.extend(parsed)
            else:
                fragments.append(parsed)
        except Exception as ex:
            notes.append(f"Error parsing {name}: {ex}")

    dated = [f for f in fragments if f.get("date")]
    unique_dates = {f["date"] for f in dated}
    majority = None
    if dated:
        majority = Counter(f["date"] for f in dated).most_common(1)[0][0]

    kept: List[Dict] = []
    for f in fragments:
        if f.get("date"):
            kept.append(f)
            continue
        fn = f.get("filename", "unknown")
        if len(unique_dates) <= 1 and majority is not None:
            f["date"] = majority
            kept.append(f)
        elif not dated:
            notes.append(f"Skipped (no date found): {fn}")
        else:
            notes.append(f"Skipped (no date in multi-day batch): {fn}")

    by_date = group_fragments_by_date(kept)
    results: List[Tuple[str, Dict, List[str]]] = []
    for d, frags in sorted(by_date.items()):
        merged = merge_upload_fragments(frags)
        errs: List[str] = []
        if not merged.get("net_total") and merged.get("gross_total"):
            merged["net_total"] = float(merged["gross_total"])
        if not merged.get("gross_total") and merged.get("net_total"):
            merged["gross_total"] = float(merged["net_total"])
        ok, verr = validate_data(merged)
        if not ok:
            errs.extend(verr)
        results.append((d, merged, errs))

    return results, notes


def calculate_mtd_metrics(
    location_id: int,
    target_monthly: float,
    year: Optional[int] = None,
    month: Optional[int] = None,
    as_of_date: Optional[str] = None,
) -> Dict:
    """MTD for calendar month of the report; optional as_of_date caps at that day (inclusive)."""
    from database import get_summaries_for_month

    if year is None or month is None:
        t = datetime.now()
        year, month = t.year, t.month

    summaries = get_summaries_for_month(location_id, year, month)
    if as_of_date:
        cap = str(as_of_date)[:10]
        summaries = [s for s in summaries if str(s.get("date", ""))[:10] <= cap]

    total_covers = sum(s.get("covers", 0) or 0 for s in summaries)
    total_sales = sum(s.get("net_total", 0) or 0 for s in summaries)
    total_discount = sum(s.get("discount", 0) or 0 for s in summaries)
    days_counted = len([s for s in summaries if (s.get("net_total", 0) or 0) > 0])

    avg_daily = total_sales / days_counted if days_counted > 0 else 0
    pct_target = (total_sales / target_monthly) * 100 if target_monthly > 0 else 0

    return {
        "mtd_total_covers": total_covers,
        "mtd_net_sales": total_sales,
        "mtd_discount": total_discount,
        "mtd_avg_daily": avg_daily,
        "mtd_target": target_monthly,
        "mtd_pct_target": pct_target,
        "days_counted": days_counted,
    }


def calculate_mtd_metrics_multi(
    location_ids: List[int],
    target_monthly: float,
    year: Optional[int] = None,
    month: Optional[int] = None,
    as_of_date: Optional[str] = None,
) -> Dict:
    """MTD across multiple locations (sum of each outlet's rows in the month)."""
    from database import get_summaries_for_month

    if year is None or month is None:
        t = datetime.now()
        year, month = t.year, t.month

    summaries: List[Dict] = []
    for lid in location_ids:
        summaries.extend(get_summaries_for_month(lid, year, month))
    if as_of_date:
        cap = str(as_of_date)[:10]
        summaries = [s for s in summaries if str(s.get("date", ""))[:10] <= cap]

    total_covers = sum(s.get("covers", 0) or 0 for s in summaries)
    total_sales = sum(s.get("net_total", 0) or 0 for s in summaries)
    total_discount = sum(s.get("discount", 0) or 0 for s in summaries)
    days_counted = len([s for s in summaries if (s.get("net_total", 0) or 0) > 0])

    avg_daily = total_sales / days_counted if days_counted > 0 else 0
    pct_target = (total_sales / target_monthly) * 100 if target_monthly > 0 else 0

    return {
        "mtd_total_covers": total_covers,
        "mtd_net_sales": total_sales,
        "mtd_discount": total_discount,
        "mtd_avg_daily": avg_daily,
        "mtd_target": target_monthly,
        "mtd_pct_target": pct_target,
        "days_counted": days_counted,
    }


def calculate_derived_metrics(data: Dict) -> Dict:
    out = dict(data)
    covers = int(out.get("covers") or 0)
    net = float(out.get("net_total") or 0)
    if covers > 0 and net > 0:
        out["apc"] = net / covers
    else:
        out["apc"] = 0.0

    seats = float(out.get("seat_count") or 0)
    if seats > 0:
        out["turns"] = round(covers / seats, 2)
    elif "turns" not in out or out.get("turns") is None:
        out["turns"] = round(covers / 100, 1) if covers else 0.0

    tgt = float(out.get("target") or 0)
    if tgt > 0:
        out["pct_target"] = round((net / tgt) * 100, 2)
    else:
        out["pct_target"] = 0.0

    return out


def validate_data(data: Dict) -> Tuple[bool, List[str]]:
    errors = []
    if not data.get("date"):
        errors.append("Date is required")
    gross = float(data.get("gross_total") or 0)
    net = float(data.get("net_total") or 0)
    if gross <= 0:
        errors.append("Gross total should be greater than 0")
    if net <= 0:
        errors.append("Net total should be greater than 0")
    return len(errors) == 0, errors


# Public API aliases for helper functions used by other modules (smart_upload.py).
# These were previously private (_f, _norm_header, etc.) but are part of the parsing contract.
f = _f
i = _i
norm_header = _norm_header
parse_date = _parse_date
cell_date_to_iso = _cell_date_to_iso
payment_bucket = _payment_bucket
normalize_group_category = _normalize_group_category
