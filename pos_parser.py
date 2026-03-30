import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import config


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


def _parse_date_range_cell(val: Any) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    m = re.search(
        r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\s+to\s+(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",
        s,
        re.I,
    )
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return _parse_date(s)


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


def _date_from_filename(filename: str) -> Optional[str]:
    m = re.search(r"(20\d{2})_(\d{2})_(\d{2})_", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _load_tabular(file_content: bytes, filename: str) -> Optional[pd.DataFrame]:
    """Load first sheet (or HTML tables) into a single DataFrame without header."""
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


def _get_col(
    colmap: Dict[str, int], row: pd.Series, *substrings: str
) -> Optional[int]:
    for key, idx in colmap.items():
        if all(sub in key for sub in substrings):
            return idx
    for key, idx in colmap.items():
        if any(sub in key for sub in substrings):
            return idx
    return None


def detect_file_kind(filename: str) -> str:
    n = filename.lower()
    if "all_restaurant_sales" in n:
        return "all_restaurant_sales"
    if "flash_report" in n:
        return "flash_report"
    if "restaurant_item_tax" in n or "item_tax_report" in n:
        return "item_tax_report"
    if "restaurant_timing" in n or "timing_report" in n:
        return "timing_report"
    if "group_wise" in n:
        return "group_wise"
    if "customer_report" in n:
        return "customer_report"
    if "sales_summary" in n:
        return "sales_summary"
    if "customerorder" in n or "customer_order" in n:
        return "item_order_details"
    return "unknown"


def parse_all_restaurant_sales(
    file_content: bytes,
    filename: str,
    location_filter: Optional[str] = None,
) -> Optional[Dict]:
    loc_f = (location_filter or config.DEFAULT_RESTAURANT_FILTER or "").strip().lower()
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    header_idx = None
    for i in range(min(15, len(df))):
        c0 = str(df.iat[i, 0]).strip().lower() if df.shape[1] > 0 else ""
        if c0 == "restaurants" or c0.startswith("restaurant"):
            header_idx = i
            break
    if header_idx is None:
        return None

    colmap = _header_map_row(df, header_idx)
    date_str = None
    for i in range(header_idx):
        c0 = str(df.iat[i, 0]).strip().lower() if df.shape[1] > 0 else ""
        if c0.startswith("date"):
            date_str = _parse_date_range_cell(df.iat[i, 1])
            break
    if not date_str:
        date_str = _date_from_filename(filename)

    idx_rest = colmap.get("restaurants", 0)
    idx_net = _get_col(colmap, df.iloc[header_idx], "net", "sales")
    idx_gross = _get_col(colmap, df.iloc[header_idx], "total", "sales")
    idx_my = _get_col(colmap, df.iloc[header_idx], "my", "amount")
    idx_disc = _get_col(colmap, df.iloc[header_idx], "total", "discount")
    idx_sc = _get_col(colmap, df.iloc[header_idx], "service", "charge")
    idx_cash = _get_col(colmap, df.iloc[header_idx], "cash")
    idx_card = _get_col(colmap, df.iloc[header_idx], "card")
    idx_other = _get_col(colmap, df.iloc[header_idx], "other")
    idx_wallet = _get_col(colmap, df.iloc[header_idx], "wallet")
    idx_upi = _get_col(colmap, df.iloc[header_idx], "upi")
    idx_online = _get_col(colmap, df.iloc[header_idx], "online")
    idx_pax = _get_col(colmap, df.iloc[header_idx], "pax")
    idx_bills = _get_col(colmap, df.iloc[header_idx], "bill")

    skip = {"total", "min.", "max.", "avg."}
    picked = None
    for ri in range(header_idx + 1, len(df)):
        loc = str(df.iat[ri, idx_rest]).strip()
        if not loc or loc.lower() in skip:
            continue
        if loc_f and loc_f not in loc.lower():
            continue
        picked = df.iloc[ri]
        break
    if picked is None:
        return None

    net_total = _f(picked.iloc[idx_net]) if idx_net is not None else 0.0
    gross_total = _f(picked.iloc[idx_gross]) if idx_gross is not None else 0.0
    if gross_total <= 0 and idx_my is not None:
        gross_total = _f(picked.iloc[idx_my])

    structural: set = {idx_rest}
    for ix in (idx_net, idx_gross, idx_my, idx_disc, idx_sc, idx_pax, idx_bills):
        if ix is not None:
            structural.add(ix)

    cash = _f(picked.iloc[idx_cash]) if idx_cash is not None else 0.0
    card = _f(picked.iloc[idx_card]) if idx_card is not None else 0.0
    wallet = _f(picked.iloc[idx_wallet]) if idx_wallet is not None else 0.0
    upi = _f(picked.iloc[idx_upi]) if idx_upi is not None else 0.0
    online = _f(picked.iloc[idx_online]) if idx_online is not None else 0.0

    pay_done = {
        x for x in (idx_cash, idx_card, idx_upi, idx_wallet, idx_online) if x is not None
    }
    extra_gpay = 0.0
    extra_zomato = 0.0
    extra_other = 0.0
    for key, j in colmap.items():
        if j in structural or j in pay_done:
            continue
        kk = key
        v = _f(picked.iloc[j])
        if abs(v) < 1e-9:
            continue
        if "zomato" in kk or "swiggy" in kk:
            extra_zomato += v
        elif (
            "g pay" in kk
            or "gpay" in kk
            or ("google" in kk and "pay" in kk)
            or ("other" in kk and ("g pay" in kk or "gpay" in kk))
        ):
            extra_gpay += v
        elif "upi" in kk or ("wallet" in kk and "other" not in kk):
            extra_gpay += v
        elif "online" in kk and "bank" not in kk:
            extra_zomato += v
        elif "other" in kk:
            extra_other += v

    discount = _f(picked.iloc[idx_disc]) if idx_disc is not None else 0.0
    service_charge = _f(picked.iloc[idx_sc]) if idx_sc is not None else 0.0

    covers = _i(picked.iloc[idx_pax]) if idx_pax is not None else 0
    if covers <= 0 and idx_bills is not None:
        covers = _i(picked.iloc[idx_bills])

    out = {
        "date": date_str,
        "filename": filename,
        "file_type": "all_restaurant_sales",
        "gross_total": gross_total,
        "net_total": net_total,
        "cash_sales": cash,
        "card_sales": card,
        "gpay_sales": upi + wallet + extra_gpay,
        "zomato_sales": online + extra_zomato,
        "other_sales": extra_other,
        "discount": discount,
        "service_charge": service_charge,
        "covers": covers,
    }
    return out if date_str else None


def parse_item_tax_report(file_content: bytes, filename: str) -> Optional[Dict]:
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    header_idx = None
    for i in range(min(20, len(df))):
        row = " ".join(_norm_header(x) for x in df.iloc[i].values)
        if "cgst" in row and "sgst" in row:
            header_idx = i
            break
    if header_idx is None:
        return None

    colmap = _header_map_row(df, header_idx)
    ic = next((colmap[k] for k in colmap if "cgst" in k and "2.5" in k), None)
    isgst = next((colmap[k] for k in colmap if "sgst" in k and "2.5" in k), None)
    isc = next(
        (colmap[k] for k in colmap if "service" in k and "charge" in k and "10" in k),
        None,
    )

    cgst = sgst = sc = 0.0
    for ri in range(header_idx + 1, len(df)):
        row = df.iloc[ri]
        if ic is not None:
            cgst += _f(row.iloc[ic])
        if isgst is not None:
            sgst += _f(row.iloc[isgst])
        if isc is not None:
            sc += _f(row.iloc[isc])

    date_str = _date_from_filename(filename)
    if not date_str:
        for i in range(header_idx):
            t = " ".join(str(x) for x in df.iloc[i].values if pd.notna(x))
            if "date" in t.lower():
                date_str = _parse_date_range_cell(
                    next((x for x in df.iloc[i].values if pd.notna(x)), None)
                )
                break

    if not date_str:
        return None

    return {
        "date": date_str,
        "filename": filename,
        "file_type": "item_tax_report",
        "cgst": cgst,
        "sgst": sgst,
        "service_charge": sc,
    }


def parse_flash_report(file_content: bytes, filename: str) -> Optional[Dict]:
    """
    POS "Flash Report" / Collection Report: one summary row with CGST, SGST,
    Service Charge (same merge role as Restaurant_item_tax_report).
    """
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    top_bits = []
    for ri in range(min(8, len(df))):
        for x in df.iloc[ri].values:
            if pd.notna(x):
                top_bits.append(_norm_header(x))
    top = " ".join(top_bits)
    if "pos collection" not in top and "collection report" not in top:
        return None

    header_idx = None
    for i in range(min(30, len(df))):
        c0 = _norm_header(df.iat[i, 0]) if df.shape[1] > 0 else ""
        if c0 != "orders":
            continue
        row_txt = " ".join(_norm_header(x) for x in df.iloc[i].values)
        if "cgst" not in row_txt or "sgst" not in row_txt:
            continue
        colmap = _header_map_row(df, i)
        if "cgst" in colmap and "sgst" in colmap and "service charge" in colmap:
            header_idx = i
            break
    if header_idx is None:
        return None

    if header_idx + 1 >= len(df):
        return None

    colmap = _header_map_row(df, header_idx)
    row = df.iloc[header_idx + 1]
    cgst = _f(row.iloc[colmap["cgst"]])
    sgst = _f(row.iloc[colmap["sgst"]])
    sc = _f(row.iloc[colmap["service charge"]])

    date_str = None
    for i in range(header_idx):
        c0 = _norm_header(df.iat[i, 0]) if df.shape[1] > 0 else ""
        if not c0.startswith("date"):
            continue
        v = df.iat[i, 1] if df.shape[1] > 1 else None
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        try:
            date_str = pd.Timestamp(v).strftime("%Y-%m-%d")
        except Exception:
            date_str = _parse_date_range_cell(v) or _parse_date(str(v).strip())
        if date_str:
            break
    if not date_str:
        date_str = _date_from_filename(filename)

    if not date_str:
        return None

    pay = _parse_flash_payment_summary(df)
    out: Dict[str, Any] = {
        "date": date_str,
        "filename": filename,
        "file_type": "flash_report",
        "cgst": cgst,
        "sgst": sgst,
        "service_charge": sc,
    }
    for pk, pv in pay.items():
        if float(pv or 0) != 0:
            out[pk] = pv
    return out


def _parse_flash_payment_summary(df: pd.DataFrame) -> Dict[str, float]:
    """Payment Wise Summary block: label col 0, amount col 1."""
    cash = gpay = zomato = other = 0.0
    header_i = None
    for i in range(min(40, len(df))):
        c0 = _norm_header(df.iat[i, 0]) if df.shape[1] else ""
        if c0 == "payment type":
            header_i = i
            break
    if header_i is None or df.shape[1] < 2:
        return {
            "cash_sales": cash,
            "gpay_sales": gpay,
            "zomato_sales": zomato,
            "other_sales": other,
        }
    for i in range(header_i + 1, len(df)):
        c0 = _norm_header(df.iat[i, 0]) if df.shape[1] else ""
        if not c0:
            break
        if "category" in c0 and "summary" in c0:
            break
        v = _f(df.iat[i, 1])
        if c0 == "cash":
            cash += v
        elif "zomato" in c0:
            zomato += v
        elif "g pay" in c0 or "gpay" in c0 or ("google" in c0 and "pay" in c0):
            gpay += v
        elif "card" in c0 or "credit" in c0 or "amex" in c0:
            other += v
        elif "other" in c0:
            other += v
    return {
        "cash_sales": cash,
        "gpay_sales": gpay,
        "zomato_sales": zomato,
        "other_sales": other,
    }


def parse_timing_report(file_content: bytes, filename: str) -> Optional[Dict]:
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    header_idx = None
    for i in range(min(20, len(df))):
        c0 = _norm_header(df.iat[i, 0])
        if c0 == "timings":
            header_idx = i
            break
    if header_idx is None:
        return None

    colmap = _header_map_row(df, header_idx)
    idx_amt = next(
        (colmap[k] for k in colmap if "total" in k and "amount" in k), None
    )
    if idx_amt is None:
        idx_amt = colmap.get(list(colmap.keys())[-1], len(df.columns) - 1)

    services: List[Dict] = []
    for ri in range(header_idx + 1, len(df)):
        label = str(df.iat[ri, 0]).strip()
        if not label or label.lower() in ("nan",):
            continue
        low = label.lower()
        if "whole day" in low:
            continue
        amt = _f(df.iat[ri, idx_amt]) if idx_amt < df.shape[1] else 0.0
        svc_type = "Other"
        if "breakfast" in low:
            svc_type = "Breakfast"
        elif "lunch" in low:
            svc_type = "Lunch"
        elif "dinner" in low:
            svc_type = "Dinner"
        services.append({"type": svc_type, "amount": amt})

    date_str = _date_from_filename(filename)
    if not date_str:
        date_str = None

    if not services:
        return None

    return {
        "date": date_str,
        "filename": filename,
        "file_type": "timing_report",
        "services": services,
    }


def parse_group_wise(file_content: bytes, filename: str) -> Optional[Dict]:
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    header_idx = None
    for i in range(min(15, len(df))):
        c0 = _norm_header(df.iat[i, 0])
        if c0 == "group name":
            header_idx = i
            break
    if header_idx is None:
        return None

    colmap = _header_map_row(df, header_idx)
    idx_group = colmap.get("group name", 0)
    idx_item = colmap.get("item", 1)
    idx_qty = next((colmap[k] for k in colmap if "qty" in k), None)
    idx_net = next(
        (colmap[k] for k in colmap if "net" in k and "sales" in k),
        None,
    )
    if idx_net is None:
        idx_net = next((colmap[k] for k in colmap if "net" in k), None)

    date_str = None
    for i in range(header_idx):
        c0 = str(df.iat[i, 0]).strip().lower() if df.shape[1] > 0 else ""
        if c0.startswith("date"):
            date_str = _parse_date_range_cell(df.iat[i, 1])
            break
    if not date_str:
        date_str = _date_from_filename(filename)

    skip_group = {"", "total", "min.", "max.", "avg.", "sub total", "nan"}
    agg: Dict[str, Dict[str, float]] = {}
    last_group = ""

    for ri in range(header_idx + 1, len(df)):
        gcell = df.iat[ri, idx_group]
        icell = df.iat[ri, idx_item] if idx_item < df.shape[1] else None
        if pd.notna(gcell) and str(gcell).strip():
            last_group = str(gcell).strip()
        g = last_group
        gl = g.lower()
        if gl in skip_group or "sub total" in gl:
            continue
        item = str(icell).strip() if pd.notna(icell) else ""
        if not item or item.lower() == "nan":
            continue
        if item.lower() == "sub total":
            continue

        qty = _i(df.iat[ri, idx_qty]) if idx_qty is not None else 0
        amt = _f(df.iat[ri, idx_net]) if idx_net is not None else 0.0
        cat = _normalize_group_category(g)
        if cat not in agg:
            agg[cat] = {"qty": 0, "amount": 0.0}
        agg[cat]["qty"] += qty
        agg[cat]["amount"] += amt

    categories = [
        {"category": k, "qty": int(v["qty"]), "amount": v["amount"]}
        for k, v in sorted(agg.items(), key=lambda x: -x[1]["amount"])
    ]

    if not categories or not date_str:
        return None

    return {
        "date": date_str,
        "filename": filename,
        "file_type": "group_wise",
        "categories": categories,
    }


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
    if "soft" in g or "drink" in g or "beverage" in g or "pfa" in g and "soft" in g:
        return "Soft Beverages"
    if "food" in g:
        return "Food"
    return group_name.strip() or "Other"


def parse_customer_report(
    file_content: bytes,
    filename: str,
    location_filter: Optional[str] = None,
) -> Optional[Dict]:
    loc_f = (location_filter or config.DEFAULT_RESTAURANT_FILTER or "").strip().lower()
    bio = BytesIO(file_content)
    try:
        df = pd.read_excel(bio, sheet_name="Customers", header=0, engine=None)
    except Exception:
        df = _load_tabular(file_content, filename)
        if df is None:
            return None
        for i in range(min(5, len(df))):
            row = [str(x).lower() for x in df.iloc[i].values if pd.notna(x)]
            if "pax" in " ".join(row) and "booked for day" in " ".join(row):
                df = pd.read_excel(
                    BytesIO(file_content),
                    sheet_name=0,
                    header=i,
                    engine=None,
                )
                break

    cols = {c.lower().strip(): c for c in df.columns}
    def col(*names: str) -> Optional[str]:
        for n in names:
            for k, v in cols.items():
                if n in k:
                    return v
        return None

    c_pax = col("pax")
    c_day = col("booked for day")
    c_rest = col("restaurant name")
    c_sess = col("restaurant session", "session name")
    c_status = col("booking status")

    if not c_pax or not c_day:
        return None

    df["_day"] = pd.to_datetime(df[c_day], errors="coerce")
    df = df[df["_day"].notna()]
    if c_rest:
        df = df[df[c_rest].astype(str).str.lower().str.contains(loc_f, na=False)]

    ok_status = {"served", "walkin", "walk-in"}
    if c_status:
        df = df[df[c_status].astype(str).str.lower().isin(ok_status)]

    if df.empty:
        return None

    mode_day = df["_day"].mode()
    date_str = (
        mode_day.iloc[0].strftime("%Y-%m-%d")
        if len(mode_day) > 0
        else _date_from_filename(filename)
    )
    if not date_str:
        return None

    ts = pd.Timestamp(date_str).normalize()
    day_df = df[df["_day"].dt.normalize() == ts]

    lunch = dinner = 0
    if c_sess:
        for _, row in day_df.iterrows():
            s = str(row[c_sess]).lower()
            p = _i(row[c_pax])
            if "lunch" in s:
                lunch += p
            elif "dinner" in s:
                dinner += p

    total = _i(day_df[c_pax].sum())

    return {
        "date": date_str,
        "filename": filename,
        "file_type": "customer_report",
        "lunch_covers": lunch,
        "dinner_covers": dinner,
        "covers": total,
    }


def parse_sales_summary(file_content: bytes, filename: str) -> Optional[Dict]:
    """Parse sales summary: real XLS/XLSX or HTML-as-.xls export."""
    df = _load_tabular(file_content, filename)
    if df is None or df.empty:
        return None

    date = None
    data: Dict[str, Any] = {}
    df_str = df.astype(str)

    for idx, row in df_str.iterrows():
        row_values = " ".join(str(v) for v in row.values).lower()

        if not date:
            for val in row.values:
                if _looks_like_date(val):
                    parsed = _parse_date(str(val))
                    if parsed:
                        date = parsed
                        break
            if not date:
                parsed = _parse_date_range_cell(row.iloc[0]) or _parse_date_range_cell(
                    row.iloc[1] if len(row) > 1 else None
                )
                if parsed:
                    date = parsed

        if "covers" in row_values and "eod" not in row_values:
            data["covers"] = _extract_number(row_values, ["covers"])

        if "turns" in row_values:
            t = _extract_decimal(row_values, ["turns"])
            if t is not None:
                data["turns"] = t

        if "eod" in row_values and "gross" in row_values:
            g = _extract_number(row_values, ["gross", "eod"])
            if g:
                data["gross_total"] = g

        if "eod" in row_values and "net" in row_values:
            n = _extract_number(row_values, ["net"])
            if n:
                data["net_total"] = n

        if "cash" in row_values and "sale" in row_values:
            data["cash_sales"] = _extract_number(row_values, ["cash"])

        if "card" in row_values and "sale" in row_values:
            data["card_sales"] = _extract_number(row_values, ["card"])

        if "gpay" in row_values or "google" in row_values or "upi" in row_values:
            data["gpay_sales"] = _extract_number(
                row_values, ["gpay", "google", "upi", "wallet"]
            )

        if "zomato" in row_values:
            data["zomato_sales"] = _extract_number(row_values, ["zomato"])

        if "service" in row_values and "charge" in row_values:
            data["service_charge"] = _extract_number(
                row_values, ["service charge", "service"]
            )

        if "cgst" in row_values:
            data["cgst"] = _extract_number(row_values, ["cgst"])

        if "sgst" in row_values:
            data["sgst"] = _extract_number(row_values, ["sgst"])

        if "discount" in row_values:
            data["discount"] = _extract_number(row_values, ["discount"])

        if "complimentary" in row_values or "complementry" in row_values:
            data["complimentary"] = _extract_number(
                row_values, ["complimentary", "complementry"]
            )

    if not date:
        date = _date_from_filename(filename)

    if not date:
        return None

    return {
        "date": date,
        "filename": filename,
        "file_type": "sales_summary",
        **{k: v for k, v in data.items() if v is not None},
    }


def _looks_like_date(val: str) -> bool:
    val = str(val).strip().lower()
    return any(
        p in val
        for p in (
            "2026",
            "2025",
            "2024",
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        )
    )


def _extract_number(text: str, keywords: List[str]) -> Optional[float]:
    for keyword in keywords:
        patterns = [
            rf"{keyword}\s*[:\-]?\s*([\d,]+\.?\d*)",
            rf"([\d,]+\.?\d*)\s*{keyword}",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return float(matches[0].replace(",", ""))
                except ValueError:
                    continue
    return None


def _extract_decimal(text: str, keywords: List[str]) -> Optional[float]:
    for keyword in keywords:
        pattern = rf"{keyword}\s*[:\-]?\s*([\d.]+)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                return float(matches[0])
            except ValueError:
                continue
    return None


def parse_category_sales(file_content: bytes, filename: str) -> Optional[List[Dict]]:
    """Legacy helper: try group-wise style via parse_group_wise."""
    g = parse_group_wise(file_content, filename)
    if g and g.get("categories"):
        return g["categories"]
    return None


_MERGE_PRIORITY = {
    "sales_summary": 10,
    "all_restaurant_sales": 20,
    "flash_report": 25,
    "item_tax_report": 35,
    "timing_report": 40,
    "group_wise": 50,
    "customer_report": 60,
}


def merge_upload_fragments(fragments: List[Dict]) -> Dict[str, Any]:
    """Merge parser outputs for one business day (same date)."""
    fragments = [f for f in fragments if f and f.get("date")]
    if not fragments:
        return {}
    fragments.sort(key=lambda f: _MERGE_PRIORITY.get(f.get("file_type", ""), 100))

    merged: Dict[str, Any] = {}
    for frag in fragments:
        ft = frag.get("file_type")
        for k, v in frag.items():
            if k in ("filename", "file_type"):
                continue
            if v is None:
                continue
            if k == "date":
                merged["date"] = v
                continue
            if ft == "item_tax_report" and k in (
                "cgst",
                "sgst",
                "service_charge",
            ):
                merged[k] = v
            elif ft == "flash_report" and k in ("cgst", "sgst", "service_charge"):
                merged[k] = v
            elif ft == "flash_report" and k in (
                "cash_sales",
                "gpay_sales",
                "zomato_sales",
                "other_sales",
            ):
                prev = float(merged.get(k) or 0)
                if abs(prev) < 1e-9 and float(v or 0) != 0:
                    merged[k] = v
            elif ft == "timing_report" and k == "services":
                merged["services"] = v
            elif ft == "group_wise" and k == "categories":
                merged["categories"] = v
            elif ft == "customer_report":
                if k in ("lunch_covers", "dinner_covers"):
                    merged[k] = v
                elif k == "covers":
                    merged["covers"] = max(
                        int(merged.get("covers") or 0), int(v or 0)
                    )
            elif ft in ("all_restaurant_sales", "sales_summary"):
                merged[k] = v
            elif ft not in _MERGE_PRIORITY:
                merged[k] = v

    if merged.get("lunch_covers") is not None and merged.get("dinner_covers") is not None:
        lf = int(merged["lunch_covers"] or 0)
        df = int(merged["dinner_covers"] or 0)
        if lf + df > 0 and merged.get("covers", 0) <= 0:
            merged["covers"] = lf + df

    return merged


def parse_upload_file(file_content: bytes, filename: str) -> Optional[Dict]:
    kind = detect_file_kind(filename)
    if kind == "all_restaurant_sales":
        return parse_all_restaurant_sales(file_content, filename)
    if kind == "item_tax_report":
        return parse_item_tax_report(file_content, filename)
    if kind == "flash_report":
        return parse_flash_report(file_content, filename)
    if kind == "timing_report":
        return parse_timing_report(file_content, filename)
    if kind == "group_wise":
        return parse_group_wise(file_content, filename)
    if kind == "customer_report":
        return parse_customer_report(file_content, filename)
    if kind == "sales_summary":
        return parse_sales_summary(file_content, filename)
    if kind == "item_order_details":
        return None
    if kind == "unknown":
        return parse_sales_summary(file_content, filename) or parse_all_restaurant_sales(
            file_content, filename
        )
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
    Parse multiple uploads; merge by date. Returns list of (date, merged_data, errors_per_day)
    and global messages (skipped files).
    """
    from collections import Counter

    fragments: List[Dict] = []
    notes: List[str] = []

    for name, content in files:
        try:
            parsed = parse_upload_file(content, name)
            if parsed:
                fragments.append(parsed)
            else:
                notes.append(f"Skipped (unrecognized or empty): {name}")
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


def calculate_derived_metrics(data: Dict) -> Dict:
    out = dict(data)
    covers = int(out.get("covers") or 0)
    net = float(out.get("net_total") or 0)
    if covers > 0 and net > 0:
        out["apc"] = net / covers
    else:
        out["apc"] = 0.0

    if "turns" not in out or out.get("turns") is None:
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
