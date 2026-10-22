# Step 6 data build (2026-10-08): six billing months, format change in month 4

**Verdict: BUILT, VALID, AND FROZEN.** There are 144 documents, 240 pages, and 1,260 lines: 210 per month across months 1-6. Months 1-2 calibrate and months 3-6 are scored; months 4-6 use format B. Gates G1-G8 pass. The blind key differs from the generator key on 6 lines of 1,260. The adjudicator upheld the original key on all 18 differing records, with 0 unresolved in every month. `frozen-m.json` holds 156 files.

Spend: Codex on the subscription only, with no metered call. Designer 465 s, generator 335 s, six blind re-key sessions (one per month) at 140-240 s each, adjudicator. Brief: `artifacts/one-loop-step6-2026-10-08/01-month-data-brief.md`; runner `month/run_build.py`.

## Checks

| Check | Result |
|---|---|
| Designer quotas, per month | Every quota met in all six months: each money class 4 per month; job B claim cases per month; 12 name variants per month |
| Independent spec check (`month/check_spec_m.py`): every money label recomputed from the reference in force on the service date, clean lines clean, arithmetic, register consistency, format headers | ALL PASS |
| Generator gates G1-G8 after render (144 PDFs, first render) | PASS |
| Blind re-key, six sessions, contained | 1,260 lines, 0 missing; no command outside its folder |
| Key agreement on 12 labels (money_error, error_dollars, property_no, property_print, the job B labels, disposition) | 6 lines differ: 2 dollar amounts marked UNSURE, 2 name-variant property resolutions in month 4, 2 disputed decimals |
| Adjudicator | 18 records (it also compared claim_text and property_printed); all upheld the original key; 0 unresolved |
| Freeze | 156 files; hashes re-verified in the repo |

## Corpus facts

- **Per month:** 24 money-error lines (4 in each of 6 classes); 36-38 lines on hold (money errors plus unsupported, contradicted, or other-authority claims).
- **Planted owner overcharge by month:** $1,279.69, $2,025.88, $3,030.07, $4,068.50, $5,281.82, $6,519.89. Dollars rise each month by the designer's choice, so dollar-weighted catch rates lean on months 4-6. The count-based marks do not.
- **Formats:**
  - Format A prints AFE numbers as `BX:7301:K`.
  - Format B prints them as `K[07301]/BX`, with every header renamed and the columns reordered.
  - Job B's code cannot read format B's AFE numbers or headers, which is the drift the loop must recover from.

## Carried into the month runner

1. **Per-operator-format maps** (flow step 5): column headers to fields, and the AFE display pattern to the register number. The drift monitor fingerprints both.
2. **AFE coding.** Lines can be coded to an AFE through a cost-bucket reference without any approval claim. The overrun rule counts every coded line, not only claimed ones.
3. **Property master.** `reference/properties.json` holds number and official name; name variants are resolved by the linking question (step 5).
4. **Remarks** are rare (4 per month), so job B's remark path gets little exercise here.
