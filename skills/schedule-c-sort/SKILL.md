---
name: schedule-c-sort
description: Sort a receipts or card-statement CSV into 2026 Schedule C lines (IRS 2026 draft layout) - meals at 50%, mileage at the 2026 rates by trip date, business-use percentages - and list every row it is unsure about as a question instead of guessing. Use for "categorize my business expenses", "which Schedule C line", "sort my receipts CSV".
---

# Schedule C sort (free lite)

`MEBO="<this skill's base directory>/../../scripts"`.

1. The CSV needs `date, vendor, description, amount`; optional `category, business_pct, miles, type`
   (`type` = income for client payments). Header names are matched loosely.
2. `python3 "$MEBO/schedule_c_sort.py" receipts.csv`
3. Report line 31 and the table, then ask the listed questions one by one. Put each answer in the row's `category`
   column (a line like 18, 22, 24a, 24b, 27b, or `personal`) and run again.
4. The line numbers follow the IRS 2026 **draft** Schedule C (line 16b "Vehicle loan" is new); say so if the user is filing.
