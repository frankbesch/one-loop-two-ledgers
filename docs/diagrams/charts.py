#!/usr/bin/env python3
"""Draw the README pictures as light and dark SVG.

Usage: python3 -B docs/diagrams/charts.py
Writes one pair of equal height: the typed-question loop beside the silent
errors of each design's worst run on both ledgers. Every figure is copied
from a result file in this repo, and main() checks that each one still
appears on its cited line. The drawing code is quoin_readme.py, a copy of
the Quoin README module.
"""
from pathlib import Path

from quoin_readme import THEMES, GREEN, BLUE, OCHRE, RED, pair, panels, steps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
STEP5 = "month/results/STEP5-RESULT-20261008.md"
REPL = "month/results/REPLICATION-RESULT-20261008.md"
BANK = "bank/results/BANK-RESULT-20261008.md"

# (design, colour, oil and gas silent, bank silent, [(file, line, text that must be on it)])
WORST = [
    ("D, the typed-question loop", GREEN, 0, 1,
     [(REPL, 22, "D: silent 0/0/0"), (BANK, 16, "**1, 0, 0**")]),
    ("B, one agent", BLUE, 2, 0,
     [(REPL, 21, "B: silent 1/1/2"), (BANK, 17, "**0, 0, 0**")]),
    ("C, confidence handoff", OCHRE, 28, 2,
     [(STEP5, 11, "| C, cascade (Jev, Claude below 0.80) | 28 |"), (BANK, 18, "| 1 (after one void) | 2 |")]),
    ("A, sampled audit (45%)", RED, 87, 23,
     [(STEP5, 8, "| A, audit at 45% (seeded run) | 87 |"), (BANK, 19, "| 23 / 24.5 |")]),
]
LINES = [(STEP5, 4, "840 lines"), (BANK, 7, "Q3-Q4, 198 units")]

LOOP_DESC = ("The typed-question loop. The text of a partner bill or a compliance certificate comes in. "
             "Code reads the printed numbers and looks up the reference documents. Where a judgment is "
             "needed, a model answers one narrow question from a closed list that always includes needs "
             "review. Code checks the answer and its quote against the page and holds anything below a "
             "frozen confidence floor. Each line is posted, or held for a named owner.")
WORST_DESC = ("Silent errors, the planted errors posted with no person looking, in each design's worst "
              "run. Oil and gas bills, months 3 to 6, 840 lines: the loop 0 (worst of 3 runs), one agent "
              "2 (worst of 3), confidence handoff 28 (1 run), sampled audit 87 (seeded run). Loan "
              "certificates, two scored quarters, 198 units: the loop 1 (worst of 3), one agent 0 "
              "(worst of 3), confidence handoff 2 (1 run), sampled audit 23 (seeded run).")


def loop(c, spread=0.0, h=0):
    return steps(dict(
        title="The typed-question loop",
        steps=[("Page text in", "a partner bill or a loan compliance certificate", None, "external"),
               ("Code reads the page", "printed numbers, reference lookups, arithmetic", None, "backend"),
               ("Model answers one typed question", "closed list, always with needs review", None, "bus"),
               ("Code checks answer and quote", "below the frozen floor: hold", None, "security"),
               ("Post, or hold for a named owner", "a held line goes to a person", None, "database")],
        note="Floors are frozen with SHA-256 before scoring.",
        desc=LOOP_DESC), c, spread, h)


def worst(c, spread=0.0, h=0):
    return panels(dict(
        title="Silent errors, worst run",
        sub="Lower is better. Oil and gas: 840 lines. Bank: 198 units.",
        panels=[(name, k, [("oil and gas bills", og, str(og)), ("bank certificates", bk, str(bk))])
                for name, k, og, bk, _ in WORST],
        notes=["One linear scale. D and B: worst of 3 runs. C and A: one run each."],
        desc=WORST_DESC), c, spread, h)


def main():
    for name, _, og, bk, cites in WORST:
        for f, n, s in cites:
            assert s in (ROOT / f).read_text().splitlines()[n - 1], (name, f, n, s)
    for f, n, s in LINES:
        assert s in (ROOT / f).read_text().splitlines()[n - 1], (f, n, s)
    for theme, c in THEMES.items():
        for name, s in zip(("loop", "worst-run"), pair(loop, worst, c)):
            (HERE / f"{name}-{theme}.svg").write_text(s)
    print("built loop | worst-run, light and dark; every figure found on its cited line")


if __name__ == "__main__":
    main()
