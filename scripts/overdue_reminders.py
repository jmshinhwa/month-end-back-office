"""Overdue invoices -> aging + one reminder draft per client. Nothing is sent.

    python3 overdue_reminders.py invoices.csv [--as-of 2026-10-25] [--sender "Your Name"]

Columns: invoice_no, client, contact, email, issue_date, due_date, amount, paid, status, terms, pay_link, project.
Tone by days late: 1-14 friendly, 15-44 firm, 45+ final notice. Late fees are only quoted from your 'terms'.
"""
import argparse
import datetime as dt
import sys

import mebo_core as core

PRO = "https://getreadystack.com/apps/freelancer-month-end-back-office-pack/"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--as-of")
    ap.add_argument("--sender", default="[Your name]")
    a = ap.parse_args(argv)
    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    print(core.render_reminders(core.reminders(core.read_invoices(a.csv), as_of, a.sender)))
    print("\nPro keeps a reminder log and climbs friendly -> firm -> final one step at a time: " + PRO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
