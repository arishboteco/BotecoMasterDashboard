"""
Boteco Dashboard — Data integrity checker.

Run against the production database to audit historical data accuracy.
Usage: python scripts/integrity_check.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def check_integrity() -> int:
    violations = []

    if database.use_supabase():
        client = database.get_supabase_client()
        rows = client.table("daily_summaries").select("*").execute().data or []
    else:
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM daily_summaries")
            rows = [dict(r) for r in cur.fetchall()]

    print(f"Checking {len(rows)} daily summaries...\n")

    for row in rows:
        date = row.get("date", "?")
        loc = row.get("location_id", "?")
        prefix = f"[{date} loc={loc}]"
        gross = float(row.get("gross_total") or 0)
        net = float(row.get("net_total") or 0)

        # Check 1: net <= gross
        if net > gross > 0:
            violations.append(f"{prefix} net (₹{net:,.0f}) > gross (₹{gross:,.0f})")

        # Check 2: no negative payments
        for field in ["cash_sales", "card_sales", "gpay_sales", "zomato_sales", "other_sales"]:
            val = float(row.get(field) or 0)
            if val < 0:
                violations.append(f"{prefix} {field} is negative: ₹{val:,.0f}")

        # Check 3: payment sum within 5% of net (slightly loose for historical data)
        payment_sum = sum(
            float(row.get(f) or 0)
            for f in ["cash_sales", "card_sales", "gpay_sales", "zomato_sales", "other_sales"]
        )
        if payment_sum > 0 and net > 0:
            diff_pct = abs(payment_sum - net) / net * 100
            if diff_pct > 5.0:
                violations.append(
                    f"{prefix} payment sum (₹{payment_sum:,.0f}) differs from net "
                    f"(₹{net:,.0f}) by {diff_pct:.1f}%"
                )

        # Check 4: covers should be positive when net > 0
        covers = int(row.get("covers") or 0)
        if net > 0 and covers <= 0:
            violations.append(f"{prefix} net > 0 but covers = {covers}")

    print(f"Found {len(violations)} violation(s):\n")
    for v in violations:
        print(f"  \u274c {v}")

    if not violations:
        print("  \u2705 All records pass integrity checks.")

    return len(violations)


if __name__ == "__main__":
    sys.exit(0 if check_integrity() == 0 else 1)
