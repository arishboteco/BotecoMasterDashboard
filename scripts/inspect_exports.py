"""One-off inspection of POS exports; run locally: python scripts/inspect_exports.py"""
import os
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"c:\Users\arish\OneDrive\Boteco Restaurants\Technology\Data Exports"
FILES = [
    "All_Restaurant_Sales_Report_2026_03_30_15_11_11.xlsx",
    "Restaurant_item_tax_report_2026_03_30_03_27_26.xlsx",
    "Restaurant_timing_report_2026_03_30_03_19_21.xlsx",
    "Item_Report_Group_Wise_2026_03_30_15_16_52.xlsx",
    "customer_report.xlsx",
    "sales_summary_2026_03_30_15_50_04.xls",
]


def main():
    for fn in FILES:
        path = os.path.join(BASE, fn)
        print("\n" + "=" * 60)
        print(fn)
        if not os.path.isfile(path):
            print("  MISSING")
            continue
        try:
            xl = pd.ExcelFile(path)
        except Exception as e:
            print("  ERROR", e)
            continue
        print("  sheets:", xl.sheet_names)
        for sn in xl.sheet_names[:1]:
            df = pd.read_excel(path, sheet_name=sn, header=None, nrows=25)
            print(f"  --- {sn} (first 25 rows, no header) ---")
            pd.set_option("display.max_columns", 20)
            pd.set_option("display.width", 200)
            print(df.to_string())


if __name__ == "__main__":
    main()
