"""Benchmark analytics query performance on synthetic data.

Usage:
  python scripts/profile_analytics_queries.py --days 365 --locations 3
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import database
import database_analytics


def _seed(days: int, locations: int) -> list[int]:
    loc_ids: list[int] = []
    for i in range(locations):
        ok, _ = database.create_location(f"Perf Outlet {i + 1}")
        if not ok:
            continue

    all_locs = [
        l
        for l in database.get_all_locations()
        if str(l.get("name", "")).startswith("Perf Outlet")
    ]
    loc_ids = [int(l["id"]) for l in all_locs]

    end = date.today()
    start = end - timedelta(days=days - 1)
    d = start
    while d <= end:
        d_iso = d.isoformat()
        for idx, loc_id in enumerate(loc_ids):
            base = 45000 + (idx * 2500) + ((d.day % 7) * 1000)
            row = {
                "date": d_iso,
                "covers": 120 + (d.day % 40),
                "gross_total": float(base + 3000),
                "net_total": float(base),
                "cash_sales": float(base * 0.18),
                "card_sales": float(base * 0.22),
                "gpay_sales": float(base * 0.24),
                "zomato_sales": float(base * 0.20),
                "other_sales": float(base * 0.16),
                "cgst": float(base * 0.025),
                "sgst": float(base * 0.025),
                "discount": float(base * 0.05),
                "service_charge": float(base * 0.02),
                "categories": [
                    {"category": "Food", "qty": 40, "amount": float(base * 0.62)},
                    {"category": "Beverage", "qty": 30, "amount": float(base * 0.28)},
                    {"category": "Dessert", "qty": 10, "amount": float(base * 0.10)},
                ],
                "services": [
                    {"type": "Lunch", "amount": float(base * 0.45)},
                    {"type": "Dinner", "amount": float(base * 0.55)},
                ],
                "top_items": [
                    {"item_name": "Fries", "qty": 12, "amount": float(base * 0.08)},
                    {"item_name": "Burger", "qty": 9, "amount": float(base * 0.12)},
                    {
                        "item_name": "Craft Beer",
                        "qty": 15,
                        "amount": float(base * 0.18),
                    },
                ],
            }
            database.save_daily_summary(loc_id, row)
        d += timedelta(days=1)

    return loc_ids


def _bench(name: str, fn, *args) -> None:
    t0 = time.perf_counter()
    out = fn(*args)
    ms = (time.perf_counter() - t0) * 1000
    size = len(out) if isinstance(out, list) else len(out.keys())
    print(f"{name:40s} {ms:8.2f} ms  rows={size}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--locations", type=int, default=3)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "perf.db")
        database.DATABASE_PATH = db_path
        database.init_database()

        loc_ids = _seed(days=args.days, locations=args.locations)
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=args.days - 1)).isoformat()

        print(f"Database: {db_path}")
        print(f"Locations: {len(loc_ids)} | Days: {args.days}")

        _bench(
            "get_summaries_for_date_range_multi",
            database.get_summaries_for_date_range_multi,
            loc_ids,
            start,
            end,
        )
        _bench(
            "get_top_items_for_date_range",
            database_analytics.get_top_items_for_date_range,
            loc_ids,
            start,
            end,
            15,
        )
        _bench(
            "get_category_sales_for_date_range",
            database_analytics.get_category_sales_for_date_range,
            loc_ids,
            start,
            end,
        )
        _bench(
            "get_daily_service_sales_for_date_range",
            database_analytics.get_daily_service_sales_for_date_range,
            loc_ids,
            start,
            end,
        )


if __name__ == "__main__":
    main()
