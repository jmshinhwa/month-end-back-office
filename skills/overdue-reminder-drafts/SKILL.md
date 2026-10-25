---
name: overdue-reminder-drafts
description: Turn an invoice list into an aging table and one reminder email draft per overdue client - friendly (1-14 days late), firm (15-44), final notice (45+) - quoting late-fee terms only from the user's own terms column. Nothing is sent. Use for "who owes me money", "draft payment reminders", "overdue invoices".
---

# Overdue reminder drafts (free lite)

`MEBO="<this skill's base directory>/../../scripts"`.

1. CSV columns: `invoice_no, client, contact, email, issue_date, due_date, amount, paid, status, terms, pay_link, project`.
2. `python3 "$MEBO/overdue_reminders.py" invoices.csv --sender "Their Name"`
3. Show the aging table and the drafts; offer edits. Never send, never add a fee or threat that is not in their terms.
