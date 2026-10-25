"""Your January 15, 2027 estimated tax payment - the 2026 Form 1040-ES worksheet, line by line.

    python3 jan15_estimate.py --status single --profit 80000 --prior-year-tax 12000 --prior-year-agi 70000 \
        --paid 2026-04-15:3000 --paid 2026-06-15:3000 --paid 2026-09-15:3000

IRS figures read 2026-10-25; the sources print under the result. Worksheet calculator, not tax advice.
"""
import argparse
import datetime as dt
import sys

import mebo_core as core

PRO = "https://getreadystack.com/apps/freelancer-month-end-back-office-pack/"


def payment(spec):
    if ":" not in spec or not core.parse_date(spec.split(":", 1)[0]):
        raise argparse.ArgumentTypeError("use DATE:AMOUNT, e.g. 2026-09-15:3000")
    d, amt = spec.split(":", 1)
    return {"date": core.parse_date(d).isoformat(), "amount": core.parse_amount(amt)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--status", required=True, choices=["single", "mfj", "mfs", "hoh", "qss"])
    ap.add_argument("--profit", required=True, type=float, help="expected 2026 Schedule C net profit")
    ap.add_argument("--wages", type=float, default=0)
    ap.add_argument("--withholding", type=float, default=0)
    ap.add_argument("--prior-year-tax", type=float)
    ap.add_argument("--prior-year-agi", type=float)
    ap.add_argument("--paid", type=payment, action="append", default=[], metavar="DATE:AMOUNT")
    ap.add_argument("--credits", type=float, default=0)
    ap.add_argument("--itemized", type=float)
    ap.add_argument("--as-of")
    a = ap.parse_args(argv)
    try:
        rules = core.load_rules(a.year)
    except core.RulesNotPublished as e:
        print(e)
        return 4
    est = core.estimate(dict(status=a.status, profit=a.profit, wages=a.wages, withholding=a.withholding,
                             prior_year_tax=a.prior_year_tax, prior_year_agi=a.prior_year_agi, payments=a.paid,
                             credits=a.credits, itemized=a.itemized,
                             as_of=dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()), rules)
    print(core.render_estimate(est, rules))
    print("\nMonth-End Back Office Pro recomputes this every month from your receipts ledger: " + PRO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
