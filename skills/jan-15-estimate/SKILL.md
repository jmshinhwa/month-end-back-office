---
name: jan-15-estimate
description: Work out a US freelancer's January 15, 2027 estimated tax payment (Q4 of tax year 2026) with the 2026 Form 1040-ES worksheet - self-employment tax, 2026 rate schedules and standard deduction, QBI deduction with the $400 minimum, the 90% / 100% / 110% safe harbor and the payments already made - and print the IRS source URLs and the date they were read under the result. Use for "how much is my January 15 payment", "quarterly estimated tax", "1040-ES", "safe harbor", "did I pay enough estimated tax this year".
---

# January 15, 2027 estimate (free lite)

`MEBO="<this skill's base directory>/../../scripts"` - set it in the same shell call.

1. Ask for: filing status (single, mfj, mfs, hoh, qss), expected 2026 Schedule C profit, 2025 tax and 2025 AGI,
   W-2 wages and withholding if any, and each 2026 estimated payment with its date. Do not assume missing numbers;
   without the 2025 tax the worksheet uses 90% of 2026 and says so.
2. Run:
   `python3 "$MEBO/jan15_estimate.py" --status single --profit 80000 --prior-year-tax 12000 --prior-year-agi 70000 --paid 2026-04-15:3000 --paid 2026-06-15:3000 --paid 2026-09-15:3000`
3. Give the headline line and the worksheet table. Use the worksheet's words ("line 14a", "the regular method puts
   $X on January 15, 2027") - not "you owe" or "you should". Keep the sources block; it is the proof.
4. Mention what is not computed when it matters: annualized method (Form 2210 Schedule AI), penalties, AMT,
   capital gains, state tax, QBI limits above the 2026 threshold.
