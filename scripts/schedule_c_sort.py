"""Sort a receipts CSV into 2026 Schedule C lines (IRS 2026 draft layout).

    python3 schedule_c_sort.py receipts.csv

Columns: date, vendor, description, amount (+ optional category, business_pct, miles, type).
Rows it is unsure about are listed as questions; answer by filling the 'category' column (e.g. 18, 24b, personal).
"""
import argparse
import sys

import mebo_core as core

PRO = "https://getreadystack.com/apps/freelancer-month-end-back-office-pack/"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    a = ap.parse_args(argv)
    rules, linemap = core.load_rules(), core.load_line_map()
    sc = core.schedule_c(core.read_rows(a.csv), rules, linemap)
    print(core.render_schedule_c(sc, rules, linemap))
    print("\nPro adds receipt photos and email receipts, remembers your answers per vendor, keeps the YTD ledger "
          "and the home office line: " + PRO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
