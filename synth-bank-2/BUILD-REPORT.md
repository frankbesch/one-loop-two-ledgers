# Step 7c fresh banking set: build report (2026-10-09)

**Verdict: BUILT, VALID, AND FROZEN at 09:55 CT, with no rebuilds.** No model answered any question on this set before the freeze.
- 48 quarterly compliance certificates (4 quarters × 12 new borrowers), 96 pages, 396 units.
- Q1-Q2 are learning quarters; Q3-Q4 are scored, with 198 units.
- **Pre-registration:** publishing `one-loop-two-ledgers/14-fresh-set-preregistration.md` (`4e3db47`), committed before the build.
- **Brief:** the data brief (unpublished) (private source `8cbd324`). It is the step 7 brief verbatim from Session 1 on. Every step 7 name is banned.

## Sessions (Codex on the subscription; fresh folder each; stdin closed; containment scanned)

| Stage | Result | Containment |
|---|---|---|
| Designer | 396 units in 392 s. The independent key check (`bank/check_spec_q.py`) finds **0 differences**. Quotas are exact in every quarter. The anti-template and certification-text gates pass. | clean |
| Generator | 48 sources and 396 truth units in 334 s, no deviations. G1-G4 and G7 pass. | clean |
| Render (brain) | 48 PDFs, 96 page images; G1-G7 all **PASS** | n/a |
| Reader check (`bank/check_reader.py`) | The frozen reader reads every printed value on all 48 certificates exactly. **No reader change.** | n/a |
| Blind re-key, one session per quarter | Error class, breach, disposition, and owner agree with the key on **396 of 396** units | clean |
| Adjudicator | 3 differences, all keyer typos in printed fields: q3_b01 cash interest, and the signer names on q3_b12 and q4_b06. The key was right each time. **0 unresolved.** | clean |
| Freeze | `frozen-q.json`: 55 files (truth, reference, PDFs); the synth-bank-2 copy hashes clean | n/a |

## Name check

A scan of the spec against `used_labels.txt` matched 5 entries: Closing, Dismissal, Equity, Glass, and Management. These are common words from the brain's own loose list of capitalized words. No step 7 bank, borrower, lender, or signer name recurs. The new bank is Asterquay Commercial Bank.

## Quotas (every quarter, from the independent check)

- 2 cases in each of the 10 error classes.
- 1 honestly reported breach.
- Scored quarters: 40 planted errors plus 2 honest breaches, so the key holds 42 units.
