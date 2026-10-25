"""Month-End Back Office - shared calculation code (Python 3.8+, standard library only).

Every IRS number used here is read from ../data/irs_2026.json, which records the IRS URL,
the revision and the day it was read. Output always ends with those sources.
This is a worksheet calculator that uses published IRS figures. It is not tax advice.
"""
import csv
import datetime as dt
import io
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
DISCLAIMER = ("Worksheet calculator using published IRS figures - not tax advice. "
              "Check the result against the IRS source below or with your tax preparer.")


class RulesNotPublished(Exception):
    pass


# ---------------------------------------------------------------- numbers

def r2(x):
    """Round to cents, half up (the way a worksheet is filled in)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def money(x):
    if x is None:
        return "-"
    x = r2(x)
    s = "${:,.2f}".format(abs(x))
    return "-" + s if x < 0 else s


def parse_amount(s):
    """'$1,234.56' -> 1234.56 · '(12.00)' -> -12.0 · '' -> None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    neg = (s.startswith("(") and s.endswith(")")) or bool(re.match(r"^\$?\s*-", s)) or s.endswith("-")
    s = re.sub(r"[^0-9.]", "", s)
    if not s or s == ".":
        return None
    v = float(s)
    return -v if neg else v


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(s):
    """Accepts 2026-10-03, 10/03/2026, 10/3/26, Oct 3, 2026, October 3 2026, 3 Oct 2026."""
    if s is None:
        return None
    s = str(s).strip()
    m = re.search(r"\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b", s)
    if m:
        return _mkdate(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", s)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        return _mkdate(y, int(m.group(1)), int(m.group(2)))
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b", s)
    if m and m.group(1)[:3].lower() in MONTHS:
        return _mkdate(int(m.group(3)), MONTHS[m.group(1)[:3].lower()], int(m.group(2)))
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(20\d\d)\b", s)
    if m and m.group(2)[:3].lower() in MONTHS:
        return _mkdate(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
    return None


def long_date(d, weekday=False):
    """'October 3, 2026' without the platform-specific %-d."""
    s = "%s %d, %d" % (d.strftime("%B"), d.day, d.year)
    return (d.strftime("%A") + ", " + s) if weekday else s


def _mkdate(y, mo, d):
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


# ---------------------------------------------------------------- rules

def load_rules(year=2026):
    year = int(year)
    path = os.path.join(DATA_DIR, "irs_%d.json" % year)
    if not os.path.exists(path):
        raise RulesNotPublished(
            "Tax year %d figures are not in this pack. On 2026-10-25 the IRS had not published the "
            "tax year %d rate schedules or Form 1040-ES (latest IRS newsroom release checked: IR-2026-128, "
            "Oct 23, 2026). Run check_sources.py (Pro) or see https://www.irs.gov/Form1040ES." % (year, year))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_line_map():
    with open(os.path.join(DATA_DIR, "schedule_c_lines_2026.json"), encoding="utf-8") as f:
        return json.load(f)


def source(rules, sid):
    for s in rules["sources"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def sources_block(rules, ids):
    out = ["", "Sources (IRS, read %s):" % rules["read_on"]]
    seen = []
    for sid in ids:
        if sid in seen:
            continue
        seen.append(sid)
        s = source(rules, sid)
        out.append("- %s - %s (%s)" % (s["title"], s["url"], s["revision"]))
    out.append("")
    out.append(DISCLAIMER)
    return "\n".join(out)


# ---------------------------------------------------------------- 1040-ES worksheet

def tax_from_schedule(amount, status, rules):
    """2026 Tax Rate Schedules (Form 1040-ES p. 9): base + rate x (amount - over)."""
    amount = max(0.0, amount)
    rows = rules["rate_schedules"][status]
    over, base, rate = rows[0]
    for row in rows:
        if amount > row[0]:
            over, base, rate = row
    return r2(base + rate * (amount - over))


def se_worksheet(profit, wages, rules):
    """2026 Self-Employment Tax and Deduction Worksheet for lines 1 and 9 (Form 1040-ES p. 8)."""
    se = rules["self_employment"]
    l1a = r2(profit)
    l2 = l1a
    l3 = r2(max(0.0, l2) * se["net_earnings_factor"])
    out = {"1a": l1a, "2": l2, "3": l3, "5": se["ss_wage_base"], "6": r2(wages)}
    if l3 < se["min_net_earnings"]:
        out.update({"4": 0.0, "7": 0.0, "8": 0.0, "9": 0.0, "10": 0.0, "11": 0.0,
                    "note": "Net earnings from self-employment under $%d: no SE tax (Schedule SE instructions)." % se["min_net_earnings"]})
        return out
    l4 = r2(l3 * se["medicare_rate"])
    l7 = r2(max(0.0, se["ss_wage_base"] - wages))
    l8 = r2(min(l3, l7))
    l9 = r2(l8 * se["ss_rate"])
    l10 = r2(l4 + l9)
    l11 = r2(l10 * se["deductible_part"])
    out.update({"4": l4, "7": l7, "8": l8, "9": l9, "10": l10, "11": l11})
    return out


def additional_medicare(status, wages, se_net_earnings, rules):
    """Topic 560: 0.9% over the threshold; the threshold for SE income is reduced by Medicare wages."""
    am = rules["additional_medicare"]
    thr = am["threshold"][status]
    on_wages = max(0.0, wages - thr)
    reduced = max(0.0, thr - wages)
    on_se = max(0.0, se_net_earnings - reduced)
    return r2((on_wages + on_se) * am["rate"])


def estimate(inp, rules):
    """2026 Estimated Tax Worksheet (Form 1040-ES p. 11), line by line.

    inp keys: status, profit (expected 2026 Schedule C line 31), wages, other_income, withholding,
    itemized, schedule_1a, credits, refundable_credits, other_taxes, prior_year_tax, prior_year_agi,
    payments [{date, amount}], qbid (override), as_of (date).
    """
    status = inp.get("status", "single")
    if status not in rules["standard_deduction"]:
        raise ValueError("filing status must be one of: " + ", ".join(rules["standard_deduction"]))
    profit = float(inp.get("profit") or 0)
    wages = float(inp.get("wages") or 0)
    other_income = float(inp.get("other_income") or 0)
    notes = []
    se = se_worksheet(profit, wages, rules)
    if se.get("note"):
        notes.append(se["note"])

    L = {}
    L["1"] = r2(profit + wages + other_income - se["11"])
    if inp.get("itemized") is not None:
        L["2a"] = r2(inp["itemized"])
        notes.append("Line 2a uses the itemized deductions you entered.")
    else:
        L["2a"] = float(rules["standard_deduction"][status])
    # line 2b - qualified business income deduction
    q = rules["qbi"]
    qbi = max(0.0, r2(profit - se["11"]))
    ti_before = max(0.0, L["1"] - L["2a"])
    qbi_note = None
    if inp.get("qbid") is not None:
        L["2b"] = r2(inp["qbid"])
        qbi_note = "Line 2b uses the QBI deduction you entered."
    elif qbi <= 0:
        L["2b"] = 0.0
    elif ti_before <= q["threshold"][status]:
        L["2b"] = r2(min(q["rate"] * qbi, q["rate"] * ti_before))
        if qbi >= q["minimum_qbi_for_minimum"] and L["2b"] < q["minimum_deduction"]:
            L["2b"] = float(q["minimum_deduction"])
            qbi_note = "Line 2b: the 2026 minimum QBI deduction of $%d applies (QBI of $%d or more)." % (
                q["minimum_deduction"], q["minimum_qbi_for_minimum"])
    else:
        L["2b"] = 0.0
        qbi_note = ("Line 2b set to $0: taxable income before the QBI deduction (%s) is over the 2026 threshold "
                    "of %s, where W-2 wage, property and specified-service limits apply (Form 8995-A). "
                    "This makes the estimate err high. Enter your preparer's figure with --qbid."
                    % (money(ti_before), money(q["threshold"][status])))
    if qbi_note:
        notes.append(qbi_note)
    L["2c"] = r2(inp.get("schedule_1a") or 0)
    L["2d"] = r2(L["2a"] + L["2b"] + L["2c"])
    L["3"] = r2(max(0.0, L["1"] - L["2d"]))
    L["4"] = tax_from_schedule(L["3"], status, rules)
    L["5"] = 0.0
    L["6"] = r2(L["4"] + L["5"])
    L["7"] = r2(inp.get("credits") or 0)
    L["8"] = r2(max(0.0, L["6"] - L["7"]))
    L["9"] = se["10"]
    addl = additional_medicare(status, wages, se["3"], rules)
    L["10"] = r2(addl + float(inp.get("other_taxes") or 0))
    if addl:
        notes.append("Line 10 includes Additional Medicare Tax of %s (0.9%% over the %s threshold)."
                     % (money(addl), money(rules["additional_medicare"]["threshold"][status])))
    L["11a"] = r2(L["8"] + L["9"] + L["10"])
    L["11b"] = r2(inp.get("refundable_credits") or 0)
    L["11c"] = r2(max(0.0, L["11a"] - L["11b"]))
    sh = rules["safe_harbor"]
    L["12a"] = r2(L["11c"] * sh["current_year_pct"])
    prior = inp.get("prior_year_tax")
    prior_pct = None
    if prior is None:
        L["12b"] = None
        L["12c"] = L["12a"]
        notes.append("No 2025 tax entered: line 12c uses 90% of the 2026 estimate (line 12a). "
                     "Enter your 2025 tax (Form 1040 line 24, see the 1040-ES line 12b instructions) to compare.")
    else:
        agi = float(inp.get("prior_year_agi") or 0)
        limit = sh["high_agi_over_mfs"] if status == "mfs" else sh["high_agi_over"]
        prior_pct = sh["prior_year_pct_high_agi"] if agi > limit else sh["prior_year_pct"]
        L["12b"] = r2(float(prior) * prior_pct)
        L["12c"] = r2(min(L["12a"], L["12b"]))
    L["13"] = r2(inp.get("withholding") or 0)
    L["14a"] = r2(L["12c"] - L["13"])
    L["14b"] = r2(L["11c"] - L["13"])
    required = True
    why_not = None
    if L["14a"] <= 0:
        required, why_not = False, "Line 14a is zero or less: withholding already covers the required annual payment."
    elif L["14b"] < sh["min_balance_due"]:
        required, why_not = False, "Line 14b is under $1,000: estimated payments are not required."
    L["15"] = r2(L["14a"] / 4) if required else 0.0

    # installments - regular method: 25% of line 14a by each due date
    dues = [dt.date.fromisoformat(d) for d in rules["due_dates"]["installments"]]
    pays = sorted(((parse_date(p["date"]) if not isinstance(p["date"], dt.date) else p["date"], float(p["amount"]))
                   for p in (inp.get("payments") or [])), key=lambda t: t[0])
    as_of = inp.get("as_of") or dt.date.today()
    if isinstance(as_of, str):
        as_of = dt.date.fromisoformat(as_of)
    rows = []
    for k, due in enumerate(dues, 1):
        cum_req = r2(L["14a"] * k / 4) if required else 0.0
        cum_paid = r2(sum(a for d, a in pays if d <= due))
        rows.append({"n": k, "due": due.isoformat(), "required_cumulative": cum_req,
                     "paid_by_due": cum_paid, "short_by": r2(max(0.0, cum_req - cum_paid)),
                     "status": "past" if due < as_of else "upcoming"})
    total_paid = r2(sum(a for _, a in pays))
    next_row = next((r for r in rows if r["status"] == "upcoming"), None)
    next_payment = None
    if next_row:
        paid_now = r2(sum(a for d, a in pays if d <= as_of))
        next_payment = {"due": next_row["due"], "amount": r2(max(0.0, next_row["required_cumulative"] - paid_now)),
                        "days_left": (dt.date.fromisoformat(next_row["due"]) - as_of).days}
    short_past = [r for r in rows if r["status"] == "past" and r["short_by"] > 0]
    for r in short_past:
        notes.append("Installment %d (%s) was short by %s. A penalty may apply for the days it stayed unpaid "
                     "(Form 2210) - this pack does not compute the penalty." % (r["n"], r["due"], money(r["short_by"])))
    notes.append("Regular installment method (25% of line 14a by each due date). If your income came unevenly, "
                 "the annualized method (Form 2210 Schedule AI) can lower the earlier installments - not computed here.")
    notes.append("Not computed: alternative minimum tax (line 5), capital gains rates, state tax.")
    return {"tax_year": rules["tax_year"], "status": status, "inputs": {
                "profit": r2(profit), "wages": r2(wages), "other_income": r2(other_income),
                "prior_year_tax": prior, "prior_year_agi": inp.get("prior_year_agi"), "payments_total": total_paid},
            "se": se, "lines": L, "prior_pct": prior_pct, "required": required, "why_not": why_not,
            "installments": rows, "next_payment": next_payment, "jan_skip_rule": rules["due_dates"]["jan_skip_rule"],
            "notes": notes, "as_of": as_of.isoformat()}


ES_LABELS = [
    ("1", "Adjusted gross income you expect in 2026"), ("2a", "Deductions (standard deduction unless itemized)"),
    ("2b", "Qualified business income deduction"), ("2c", "Schedule 1-A deductions (entered by you)"),
    ("2d", "Add lines 2a-2c"), ("3", "Line 1 minus line 2d"), ("4", "Tax (2026 Tax Rate Schedules)"),
    ("5", "Alternative minimum tax (not computed)"), ("6", "Lines 4 + 5"), ("7", "Credits (entered by you)"),
    ("8", "Line 6 minus line 7"), ("9", "Self-employment tax"), ("10", "Other taxes"),
    ("11a", "Lines 8 + 9 + 10"), ("11b", "Refundable credits (entered by you)"), ("11c", "Total 2026 estimated tax"),
    ("12a", "90% of line 11c"), ("12b", "Required payment based on 2025 tax"), ("12c", "Required annual payment (smaller of 12a/12b)"),
    ("13", "Income tax withheld in 2026"), ("14a", "Line 12c minus line 13"), ("14b", "Line 11c minus line 13"),
    ("15", "Each quarterly installment (1/4 of line 14a)")]


def align_tables(md):
    """Pad markdown table columns so the tables also read well in a plain terminal (still valid markdown)."""
    lines, out, block = md.split("\n"), [], []

    def flush():
        if not block:
            return
        cells = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in block]
        n = max(len(r) for r in cells)
        cells = [r + [""] * (n - len(r)) for r in cells]
        sep = [i for i, r in enumerate(cells) if all(re.fullmatch(r":?-{3,}:?", c or "---") for c in r)]
        right = [c.endswith(":") for c in cells[sep[0]]] if sep else [False] * n
        w = [max(len(r[i]) for j, r in enumerate(cells) if j not in sep) for i in range(n)]
        w = [max(3, x) for x in w]
        if not right[-1]:
            w[-1] = 3  # a long free-text last column is left unpadded
        for j, r in enumerate(cells):
            if j in sep:
                out.append("|" + "|".join(("-" * (w[i] + 1) + ":") if right[i] else ("-" * (w[i] + 2)) for i in range(n)) + "|")
            else:
                out.append("| " + " | ".join(r[i].rjust(w[i]) if right[i] else r[i].ljust(w[i]) for i in range(n)) + " |")
        del block[:]

    for ln in lines:
        if ln.startswith("|"):
            block.append(ln)
        else:
            flush()
            out.append(ln)
    flush()
    return "\n".join(out)


def render_estimate(est, rules):
    L = est["lines"]
    st = rules["filing_statuses"][est["status"]]
    out = []
    np_ = est["next_payment"]
    if not est["required"]:
        out.append("## Estimated tax 2026: no payment required")
        out.append(est["why_not"])
    elif np_ and np_["due"] == "2027-01-15":
        out.append("## Your January 15, 2027 payment (2026 Form 1040-ES worksheet): %s" % money(np_["amount"]))
        out.append("Q4 of tax year 2026 · due in %d days · required annual payment %s · paid so far %s"
                   % (np_["days_left"], money(L["14a"]), money(est["inputs"]["payments_total"])))
    elif np_:
        out.append("## Next estimated tax payment (%s): %s" % (np_["due"], money(np_["amount"])))
        out.append("Due in %d days · required annual payment %s · paid so far %s"
                   % (np_["days_left"], money(L["14a"]), money(est["inputs"]["payments_total"])))
    else:
        out.append("## Tax year 2026: all four due dates have passed")
    out.append("")
    out.append("Filing status: %s · expected 2026 Schedule C profit %s · wages %s · as of %s"
               % (st, money(est["inputs"]["profit"]), money(est["inputs"]["wages"]), est["as_of"]))
    out.append("")
    se = est["se"]
    out.append("### Self-employment tax worksheet (Form 1040-ES 2026, p. 8)")
    out.append("| Line | | Amount |")
    out.append("|---|---|---:|")
    for k, lab in [("1a", "Expected profit subject to SE tax"), ("3", "x 92.35%"), ("4", "x 2.9% (Medicare part)"),
                   ("5", "Social security maximum 2026"), ("6", "Your wages subject to social security"),
                   ("8", "Smaller of line 3 or line 5 minus line 6"), ("9", "x 12.4% (social security part)"),
                   ("10", "SE tax"), ("11", "Half of SE tax (deducted on line 1)")]:
        out.append("| %s | %s | %s |" % (k, lab, money(se.get(k))))
    out.append("")
    out.append("### 2026 Estimated Tax Worksheet (Form 1040-ES 2026, p. 11)")
    out.append("| Line | | Amount |")
    out.append("|---|---|---:|")
    for k, lab in ES_LABELS:
        v = L.get(k)
        if k == "12b" and v is not None:
            lab = "%d%% of your 2025 tax" % round(est["prior_pct"] * 100)
        out.append("| %s | %s | %s |" % (k, lab, money(v)))
    out.append("")
    out.append("### Due dates (regular method)")
    out.append("| # | Due | Required by then | Paid by then | Short |")
    out.append("|---|---|---:|---:|---:|")
    for r in est["installments"]:
        out.append("| %d | %s | %s | %s | %s |" % (r["n"], r["due"], money(r["required_cumulative"]),
                                                  money(r["paid_by_due"]), money(r["short_by"])))
    out.append("")
    out.append("Rule on the form: " + est["jan_skip_rule"])
    out.append("")
    for n in est["notes"]:
        out.append("- " + n)
    out.append(sources_block(rules, ["f1040es", "ir-2025-103", "rp-25-32", "i1040sse", "tc560"]))
    return align_tables("\n".join(out))


# ---------------------------------------------------------------- receipts -> Schedule C

RECEIPT_COLUMNS = ["date", "vendor", "description", "amount", "category", "business_pct", "miles", "type", "note"]
INCOME_TYPES = {"income", "sale", "sales", "payment received", "deposit", "client payment", "revenue"}
REFUND_OUT_TYPES = {"refund issued", "refund to client", "return", "returns", "allowance"}


def read_rows(path_or_text):
    """Read a receipts CSV. Column names are matched loosely (Date/Merchant/Payee/Amount/...)."""
    if os.path.exists(path_or_text):
        with open(path_or_text, encoding="utf-8-sig", newline="") as f:
            text = f.read()
    else:
        text = path_or_text
    reader = csv.DictReader(io.StringIO(text))
    alias = {"merchant": "vendor", "payee": "vendor", "name": "vendor", "store": "vendor",
             "memo": "description", "details": "description", "item": "description",
             "total": "amount", "debit": "amount", "line": "category", "schedule_c_line": "category",
             "business %": "business_pct", "business_use": "business_pct", "kind": "type", "notes": "note"}
    rows = []
    for raw in reader:
        row = {k: "" for k in RECEIPT_COLUMNS}
        for k, v in raw.items():
            if k is None:
                continue
            key = k.strip().lower()
            key = alias.get(key, key)
            if key in row:
                row[key] = (v or "").strip()
        if not any(row.values()):
            continue
        rows.append(row)
    return rows


def _kw_regex(word):
    return re.compile(r"(?<![a-z0-9])" + re.escape(word.lower()) + r"(?:s|es)?(?![a-z0-9])")


def _best_keyword(text, linemap):
    """Longest keyword found in text across line keywords, personal words and ambiguous words."""
    if not text.strip():
        return None
    best = None
    for grp in linemap["keywords"]:
        for w in grp["words"]:
            if _kw_regex(w).search(text) and (best is None or len(w) > len(best[0])):
                best = (w, "line", grp)
    for w in linemap["personal_words"]:
        if _kw_regex(w).search(text) and (best is None or len(w) > len(best[0])):
            best = (w, "personal", None)
    for amb in linemap["ambiguous_words"]:
        for w in amb["words"]:
            if _kw_regex(w).search(text) and (best is None or len(w) > len(best[0])):
                best = (w, "ask", amb)
    return best


def _normalize_line(cat, linemap):
    c = (cat or "").strip().lower()
    if not c:
        return None
    if c in ("personal", "not business", "exclude", "skip"):
        return "personal"
    c2 = re.sub(r"^(schedule c\s*)?(line\s*)?", "", c).strip()
    if c2 in linemap["lines"]:
        return c2
    for code, info in linemap["lines"].items():
        if c == info["name"].lower():
            return code
    return None


def mileage_rate(d, rules):
    for p in rules["mileage_business_cents"]["periods"]:
        if dt.date.fromisoformat(p["from"]) <= d <= dt.date.fromisoformat(p["to"]):
            return p["cents"], p["release"]
    return None, None


def classify(row, rules, linemap, vendor_rules=None):
    """Return a classified row: line, label, amount, deductible, how, question."""
    text = ("%s %s" % (row.get("vendor", ""), row.get("description", ""))).lower()
    amount = parse_amount(row.get("amount"))
    d = parse_date(row.get("date"))
    typ = (row.get("type") or "").strip().lower()
    pct = parse_amount(row.get("business_pct"))
    pct = 100.0 if pct is None else max(0.0, min(100.0, pct))
    out = {"date": d.isoformat() if d else row.get("date", ""), "vendor": row.get("vendor", ""),
           "description": row.get("description", ""), "amount": amount, "business_pct": pct,
           "line": None, "label": "", "deductible": 0.0, "how": "", "question": None, "flags": []}
    if d is None:
        out["flags"].append("no readable date")
    if d and d.year != rules["tax_year"]:
        out["flags"].append("dated %d, not tax year %d - left out" % (d.year, rules["tax_year"]))
        out["how"] = "other year"
        out["line"] = "other-year"
        return out
    miles = parse_amount(row.get("miles"))
    if miles and miles > 0 and (amount is None or amount == 0):
        cents, rel = mileage_rate(d, rules) if d else (None, None)
        if cents is None:
            out.update(line=None, how="ask", question="Mileage row needs a 2026 trip date.")
            return out
        value = r2(miles * cents / 100)
        out.update(line="9", label="Standard mileage %s mi x %s cents (%s)" % (_num(miles), _num(cents), rel),
                   amount=value, deductible=r2(value * pct / 100), how="mileage", mileage=True)
        return out
    if amount is None:
        out.update(how="ask", question="No amount on this row.")
        return out
    if typ in INCOME_TYPES:
        out.update(line="1", label="Gross receipts", deductible=r2(abs(amount)), how="income")
        return out
    if typ in REFUND_OUT_TYPES:
        out.update(line="2", label="Returns and allowances", deductible=r2(abs(amount)), how="income")
        return out
    # 1 your saved vendor rules (Pro) · 2 the category column · 3 keywords (longest match wins)
    line = label = None
    how = ""
    if row.get("category"):
        code = _normalize_line(row["category"], linemap)
        if code:
            line, label, how = code, "your category", "category"
        else:
            out["flags"].append("category '%s' is not a Schedule C line - ignored" % row["category"])
    if line is None:
        for vend, code in sorted((vendor_rules or {}).items(), key=lambda kv: -len(kv[0])):
            if vend and vend.lower() in text:
                line, label, how = code, "your saved rule '%s'" % vend, "rule"
                break
    actual_car = False
    if line is None:
        # the vendor name decides first ('Delta Air Lines - client workshop' is travel, not training);
        # the description only when the vendor says nothing
        best = _best_keyword((row.get("vendor") or "").lower(), linemap) or \
            _best_keyword((row.get("description") or "").lower(), linemap)
        if best is None:
            out.update(how="ask", question="Which Schedule C line? No keyword matched '%s'." % (row.get("vendor") or row.get("description")))
            return out
        w, kind, grp = best
        if kind == "personal":
            out.update(line="personal", label="looks personal ('%s')" % w, how="personal",
                       question="Looks personal ('%s'). Left out unless you say it was for the business." % w)
            return out
        if kind == "ask":
            out.update(how="ask", candidates=grp["candidates"], question=grp["ask"])
            return out
        line, label, how = grp["line"], grp["label"], "keyword"
        out["keyword"] = w
        actual_car = bool(grp.get("actual_car_cost"))
    if line == "personal":
        out.update(line="personal", label="marked personal", how="marked")
        return out
    out["line"], out["label"], out["how"] = line, label, how
    out["actual_car_cost"] = actual_car
    signed = amount  # a negative expense row is a refund/credit and lowers the line
    ded = signed * pct / 100
    if line == "24b":
        ded = ded * rules["schedule_c"]["meals_deductible_pct"]
        out["flags"].append("meals: 50% counted; keep who/why on the receipt")
    out["deductible"] = r2(ded)
    if line == "25" and not row.get("business_pct"):
        out["flags"].append("phone/internet: enter business_pct (first home landline base rate is not deductible)")
    if abs(amount) > rules["schedule_c"]["de_minimis_per_item_no_afs"] and line not in ("11", "20a", "20b", "15", "17", "26", "16a", "16b", "16c", "1", "2"):
        out["flags"].append("over the $2,500-per-item de minimis amount: if this is equipment it is depreciated (line 13, Form 4562)")
    return out


def _num(x):
    return ("%g" % x)


def schedule_c(rows, rules, linemap, vendor_rules=None, home_office_sqft=None):
    items = [classify(r, rules, linemap, vendor_rules) for r in rows]
    items.sort(key=lambda it: it["date"] or "")
    totals = {}
    part_v = {}
    for it in items:
        ln = it["line"]
        if ln in (None, "personal", "other-year"):
            continue
        totals[ln] = r2(totals.get(ln, 0) + it["deductible"])
        if ln == "27b":
            what = it["label"] if it["how"] == "keyword" else (it["description"] or it["vendor"] or "Other")[:40]
            part_v[what] = r2(part_v.get(what, 0) + it["deductible"])
    has_mileage = any(it.get("mileage") for it in items)
    flags = []
    if has_mileage and any(it.get("actual_car_cost") for it in items):
        for it in items:
            if it.get("actual_car_cost"):
                it["flags"].append("you also log standard mileage: gas/repairs are not added on top (parking and tolls are)")
                totals["9"] = r2(totals["9"] - it["deductible"])
                it["deductible"] = 0.0
        flags.append("Standard mileage rate used: actual car operating costs were left out of line 9 "
                     "(Schedule C instructions, line 9: add parking fees and tolls only).")
    l1 = totals.get("1", 0.0)
    l2 = totals.get("2", 0.0)
    l3 = r2(l1 - l2)
    l7 = r2(l3 + totals.get("6", 0.0))
    exp_lines = [c for c in linemap["lines"] if linemap["lines"][c].get("part") != "income" and c != "30"]
    l28 = r2(sum(totals.get(c, 0.0) for c in exp_lines))
    l29 = r2(l7 - l28)
    l30 = 0.0
    if home_office_sqft:
        sc = rules["schedule_c"]
        sq = min(float(home_office_sqft), sc["home_office_simplified_max_sqft"])
        l30 = r2(sq * sc["home_office_simplified_rate"])
        if l29 <= 0:
            flags.append("Line 30 is limited by the gross income limitation: with no tentative profit the simplified "
                         "deduction is $0 this year (Simplified Method Worksheet).")
            l30 = 0.0
        elif l30 > l29:
            flags.append("Line 30 limited to the tentative profit on line 29 (gross income limitation).")
            l30 = l29
        totals["30"] = l30
    l31 = r2(l29 - l30)
    asks = [it for it in items if it["how"] in ("ask", "personal")]
    return {"items": items, "totals": totals, "part_v": part_v, "flags": flags, "asks": asks,
            "summary": {"1": l1, "2": l2, "3": l3, "7": l7, "28": l28, "29": l29, "30": l30, "31": l31},
            "counted": sum(1 for it in items if it["line"] not in (None, "personal", "other-year"))}


def row_reason(it):
    how = it["how"]
    if how == "keyword":
        return "%s (keyword '%s')" % (it["label"], it.get("keyword", ""))
    if how in ("ask", "personal"):
        return "question"
    if how == "other year":
        return "other tax year"
    return it["label"] or how


def render_schedule_c(sc, rules, linemap, title="Schedule C lines"):
    s = sc["summary"]
    out = ["## %s: net profit (line 31) %s" % (title, money(s["31"])),
           "%d of %d rows sorted · %d questions before they count · layout: %s"
           % (sc["counted"], len(sc["items"]), len(sc["asks"]), linemap["form"] + " DRAFT (Created 5/15/26)"), ""]
    out.append("| Line | Schedule C 2026 | Amount |")
    out.append("|---|---|---:|")
    out.append("| 1 | Gross receipts or sales | %s |" % money(s["1"]))
    if s["2"]:
        out.append("| 2 | Returns and allowances | %s |" % money(s["2"]))
    if sc["totals"].get("6"):
        out.append("| 6 | Other income | %s |" % money(sc["totals"]["6"]))
    out.append("| 7 | Gross income | %s |" % money(s["7"]))
    for code, info in linemap["lines"].items():
        if info.get("part") == "income" or code == "30":
            continue
        if sc["totals"].get(code):
            star = " (new line on the 2026 draft)" if info.get("new_2026") else ""
            out.append("| %s | %s%s | %s |" % (code, info["name"], star, money(sc["totals"][code])))
    out.append("| 28 | Total expenses before home office | %s |" % money(s["28"]))
    out.append("| 29 | Tentative profit | %s |" % money(s["29"]))
    if s["30"]:
        out.append("| 30 | Business use of home (simplified: $5 x sq ft, max 300) | %s |" % money(s["30"]))
    out.append("| **31** | **Net profit or (loss)** | **%s** |" % money(s["31"]))
    if sc["part_v"]:
        out.append("")
        out.append("Part V (line 48 -> 27b): " + " · ".join("%s %s" % (k, money(v)) for k, v in sc["part_v"].items()))
    if sc["asks"]:
        out.append("")
        out.append("### Questions before these rows count")
        for i, it in enumerate(sc["asks"], 1):
            cand = (" Candidates: " + ", ".join(it.get("candidates", []))) if it.get("candidates") else ""
            out.append("%d. %s %s %s - %s%s" % (i, it["date"], it["vendor"] or it["description"], money(it["amount"]),
                                                it["question"] or "", cand))
    out.append("")
    out.append("### Every row")
    out.append("| Date | Vendor | Amount | Line | Counted | Why |")
    out.append("|---|---|---:|---|---:|---|")
    for it in sc["items"]:
        why = row_reason(it)
        if it["flags"]:
            why += " · " + "; ".join(it["flags"])
        out.append("| %s | %s | %s | %s | %s | %s |" % (it["date"], (it["vendor"] or it["description"])[:40],
                                                        money(it["amount"]), it["line"] or "?",
                                                        money(it["deductible"]) if it["line"] not in (None, "personal", "other-year") else "-", why))
    if sc["flags"]:
        out.append("")
        for f in sc["flags"]:
            out.append("- " + f)
    out.append("")
    out.append("- " + linemap["status"])
    out.append("- What changed for 2026: " + linemap["changed_vs_2025"])
    out.append(sources_block(rules, ["f1040sc-2026-draft", "f1040sc-2025", "i1040sc", "mileage"]))
    return align_tables("\n".join(out))


# ---------------------------------------------------------------- receipt text -> row

TOTAL_LABELS = ["amount paid", "total paid", "total charged", "grand total", "payment total", "order total",
                "total", "amount due", "amount charged", "charged"]
SKIP_TOTAL = re.compile(r"sub\s*-?total|total tax|total savings|total items|total discount|total qty|total quantity", re.I)
AMOUNT_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d{2})?|(?<![\d.,])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\d])")


def find_amounts(line):
    out = []
    for m in AMOUNT_RE.finditer(line):
        if m.group(1):
            out.append(float(m.group(1).replace(",", "") + (m.group(2) or "")))
        else:
            out.append(float(m.group(3).replace(",", "")))
    return out


def parse_receipt_text(text):
    """Pull date, vendor and total out of an email receipt or the text Claude read from a receipt photo."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    res = {"date": None, "vendor": None, "amount": None, "currency": "USD", "warnings": []}
    if re.search(r"[€£¥]|\b(eur|gbp|cad|aud|jpy|mxn)\b", text, re.I):
        res["currency"] = "non-USD"
        res["warnings"].append("not in US dollars - convert at the rate on the payment date before using it")
    # vendor
    for ln in lines:
        m = re.match(r"(?i)^(from|merchant|store|seller|sold by|vendor|billed by)\s*:\s*(.+)$", ln)
        if m:
            v = re.sub(r"<[^>]*>", "", m.group(2)).strip().strip('"')
            res["vendor"] = v
            break
    if not res["vendor"]:
        for ln in lines:
            low = ln.lower()
            if re.search(r"[a-z]", low) and not re.search(r"receipt|invoice|thank|order #|order number|subject|date|^to:", low):
                res["vendor"] = ln[:60]
                break
    # date: prefer a line that says date
    for ln in sorted(lines, key=lambda l: 0 if re.search(r"(?i)date|paid on|charged on|issued", l) else 1):
        d = parse_date(ln)
        if d:
            res["date"] = d.isoformat()
            break
    # total
    best = None
    for idx, ln in enumerate(lines):
        low = ln.lower()
        if SKIP_TOTAL.search(low):
            continue
        for rank, lab in enumerate(TOTAL_LABELS):
            if re.search(r"(?<![a-z])" + re.escape(lab) + r"(?![a-z])", low):
                amts = find_amounts(ln)
                if not amts and idx + 1 < len(lines):
                    amts = find_amounts(lines[idx + 1])
                if amts:
                    val = amts[-1]
                    key = (rank, -idx)
                    if best is None or key < best[0]:
                        best = (key, val)
                break
    if best:
        res["amount"] = best[1]
    else:
        amts = find_amounts(text)
        if amts:
            res["amount"] = max(amts)
            res["warnings"].append("no 'total' line found - used the largest amount; check it")
    if not res["date"]:
        res["warnings"].append("no date found")
    if res["amount"] is None:
        res["warnings"].append("no amount found")
    return res


# ---------------------------------------------------------------- invoices -> reminder drafts

INVOICE_COLUMNS = ["invoice_no", "client", "contact", "email", "issue_date", "due_date", "amount", "paid", "status", "terms", "pay_link", "project"]
BUCKETS = [(0, 0, "not due"), (1, 15, "1-15 days"), (16, 30, "16-30 days"), (31, 60, "31-60 days"), (61, 90, "61-90 days"), (91, 10 ** 6, "90+ days")]
STAGES = {1: "friendly", 2: "firm", 3: "final notice"}


def read_invoices(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        alias = {"invoice": "invoice_no", "invoice #": "invoice_no", "number": "invoice_no", "customer": "client",
                 "client_email": "email", "date": "issue_date", "due": "due_date", "total": "amount",
                 "amount_paid": "paid", "payment_link": "pay_link"}
        rows = []
        for raw in reader:
            row = {k: "" for k in INVOICE_COLUMNS}
            for k, v in raw.items():
                if k is None:
                    continue
                key = alias.get(k.strip().lower(), k.strip().lower())
                if key in row:
                    row[key] = (v or "").strip()
            if any(row.values()):
                rows.append(row)
    return rows


def stage_for_days(days):
    if days <= 0:
        return 0
    if days <= 14:
        return 1
    if days <= 44:
        return 2
    return 3


def age_invoices(rows, as_of):
    out = []
    for r in rows:
        status = (r.get("status") or "").lower()
        amt = parse_amount(r.get("amount")) or 0.0
        paid = parse_amount(r.get("paid")) or 0.0
        bal = r2(amt - paid)
        if status in ("paid", "void", "cancelled", "canceled", "draft") or bal <= 0.004:
            continue
        issued = parse_date(r.get("issue_date"))
        if issued and issued > as_of:
            continue  # not issued yet on the as-of date
        due = parse_date(r.get("due_date"))
        if not due:
            m = re.search(r"net\s*(\d+)", (r.get("terms") or "").lower())
            if issued and m:
                due = issued + dt.timedelta(days=int(m.group(1)))
        days = (as_of - due).days if due else None
        bucket = next(lab for lo, hi, lab in BUCKETS if days is not None and lo <= max(days, 0) <= hi) if days is not None else "no due date"
        out.append(dict(r, balance=bal, amount_num=amt, paid_num=paid, due=due.isoformat() if due else None,
                        days_late=days, bucket=bucket, stage=stage_for_days(days) if days is not None else 0))
    return out


def draft_email(client, invs, stage, sender, as_of, earlier=None):
    """One email per client. earlier: True/False when the reminder log knows, None when it doesn't (lite)."""
    total = r2(sum(i["balance"] for i in invs))
    nums = ", ".join("#" + i["invoice_no"] for i in invs)
    lines_ = "\n".join("- Invoice #%s%s: %s, due %s (%d days ago)" % (
        i["invoice_no"], (" (" + i["project"] + ")") if i.get("project") else "", money(i["balance"]),
        long_date(dt.date.fromisoformat(i["due"])), i["days_late"]) for i in invs)
    link = next((i["pay_link"] for i in invs if i.get("pay_link")), "")
    pay = ("You can pay here: %s\n\n" % link) if link else ""
    terms = next((i["terms"] for i in invs if i.get("terms") and re.search(r"late|interest|fee", i["terms"], re.I)), "")
    contact = (invs[0].get("contact") or "").strip()
    role_words = {"accounts", "payable", "billing", "finance", "team", "department", "office", "admin", "ap"}
    if re.fullmatch(r"[A-Z][a-z'\-]+(\s+[A-Z][a-z'\-]+)+", contact) and not role_words & set(contact.lower().split()):
        greet = "Hi %s," % contact.split()[0]
    elif contact:
        greet = "Hello %s," % contact
    else:
        greet = "Hello,"
    oldest = max(i["days_late"] for i in invs)
    if stage == 1:
        subject = "Quick reminder: invoice %s (%s)" % (nums, money(total))
        body = ("%s\n\nHope all is well. A quick reminder that the following is now past due:\n\n%s\n\n%s"
                "If it's already on its way, thank you - please ignore this note. If anything is missing on your side "
                "(a PO number, a W-9, a different address), just reply and I'll send it today.\n\nThanks,\n%s"
                % (greet, lines_, pay, sender))
    elif stage == 2:
        opener = ("I'm following up on my earlier reminder." if earlier else
                  "I'm following up on the invoice%s below, now %d days past due." % ("s" if len(invs) > 1 else "", oldest))
        subject = "Past due: invoice %s - %s outstanding" % (nums, money(total))
        body = ("%s\n\n%s As of %s this is still open:\n\n%s\n\nTotal outstanding: %s\n\n%s"
                "Could you let me know by %s when payment will be sent? If there is a problem with the invoice, "
                "tell me and I'll fix it right away.\n\nThank you,\n%s"
                % (greet, opener, long_date(as_of), lines_, money(total), pay,
                   long_date(as_of + dt.timedelta(days=5), weekday=True), sender))
    else:
        opener = ("This is my final reminder about the invoices below, which remain unpaid after my earlier reminders."
                  if earlier else "The invoice%s below %s now %d days past due." % (
                      "s" if len(invs) > 1 else "", "are" if len(invs) > 1 else "is", oldest))
        quote = ("As agreed in our terms: \"%s\"\n\n" % terms) if terms else ""
        subject = "Final notice: invoice %s - %s past due" % (nums, money(total))
        body = ("%s\n\n%s\n\n%s\n\nTotal outstanding: %s\n\n%s%sPlease send payment by %s, or reply today so we "
                "can agree on a date. If you have already paid, send me the date and reference so I can match it."
                "\n\nRegards,\n%s"
                % (greet, opener, lines_, money(total), quote, pay, long_date(as_of + dt.timedelta(days=7)), sender))
    return {"client": client, "email": invs[0].get("email", ""), "stage": stage, "tone": STAGES[stage],
            "subject": subject, "body": body, "total": total, "invoices": [i["invoice_no"] for i in invs]}


def reminders(rows, as_of, sender="[Your name]", log=None, min_gap_days=7):
    """Aging + one draft per client.

    log (Pro): {invoice_no: [(stage, date_sent), ...]}. With a log the tone climbs one stage at a time,
    never sooner than min_gap_days after the last reminder, and a client never reminded starts at most at 'firm'.
    """
    aged = age_invoices(rows, as_of)
    buckets = {}
    for a in aged:
        buckets[a["bucket"]] = r2(buckets.get(a["bucket"], 0) + a["balance"])
    by_client = {}
    for a in aged:
        if a["stage"] > 0:
            by_client.setdefault(a["client"], []).append(a)
    drafts, waits = [], []
    for client, invs in by_client.items():
        stage = max(i["stage"] for i in invs)
        earlier = None
        if log is not None:
            sent = [(d, st) for i in invs for st, d in log.get(i["invoice_no"], [])]
            if sent:
                last_date, last_stage = max(sent)
                earlier = True
                if (as_of - last_date).days < min_gap_days:
                    waits.append({"client": client, "last_stage": last_stage, "sent": last_date.isoformat(),
                                  "next_on": (last_date + dt.timedelta(days=min_gap_days)).isoformat()})
                    continue
                stage = min(3, max(stage, 1), last_stage + 1)
            else:
                earlier = False
                stage = min(stage, 2)
        drafts.append(draft_email(client, sorted(invs, key=lambda i: i["due"] or ""), stage, sender, as_of, earlier))
    drafts.sort(key=lambda d: -d["total"])
    return {"as_of": as_of.isoformat(), "open": aged, "buckets": buckets, "drafts": drafts, "waits": waits,
            "total_open": r2(sum(a["balance"] for a in aged)),
            "total_overdue": r2(sum(a["balance"] for a in aged if a["stage"] > 0))}


def render_reminders(res):
    out = ["## Overdue invoices: %s across %d drafts (as of %s)" % (money(res["total_overdue"]), len(res["drafts"]), res["as_of"]),
           "Open %s in total · nothing is sent - these are drafts for you to review" % money(res["total_open"]), "",
           "| Age | Open |", "|---|---:|"]
    for _, _, lab in BUCKETS:
        if res["buckets"].get(lab):
            out.append("| %s | %s |" % (lab, money(res["buckets"][lab])))
    out.append("")
    out.append("| Invoice | Client | Due | Days late | Balance |")
    out.append("|---|---|---|---:|---:|")
    for a in sorted(res["open"], key=lambda a: -(a["days_late"] if a["days_late"] is not None else -999)):
        dl = a["days_late"]
        late = "?" if dl is None else (str(dl) if dl > 0 else ("due today" if dl == 0 else "due in %d days" % -dl))
        out.append("| #%s | %s | %s | %s | %s |" % (a["invoice_no"], a["client"], a["due"] or "?", late, money(a["balance"])))
    for w in res.get("waits", []):
        out.append("")
        out.append("- %s: %s reminder sent %s - next one not before %s." % (w["client"], STAGES[w["last_stage"]], w["sent"], w["next_on"]))
    for d in res["drafts"]:
        out.append("")
        out.append("### Draft to %s <%s> - %s" % (d["client"], d["email"] or "no email on file", d["tone"]))
        out.append("Subject: " + d["subject"])
        out.append("")
        out.append("```")
        out.append(d["body"])
        out.append("```")
    return align_tables("\n".join(out))
