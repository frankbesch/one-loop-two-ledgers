# Step 7 banking corpus: build report (2026-10-08)

**Verdict: BUILT, VALID, AND FROZEN at 19:03 CT.**
- 48 quarterly compliance certificates: 4 quarters × 12 borrowers, 96 pages, 396 units.
- Q1-Q2 calibrate; Q3-Q4 are scored, with 198 units.
- Pre-registration: publishing `one-loop-two-ledgers/10-banking-mirror-plan.md` (313b376), committed before any data. Brief: the data brief (unpublished).

## Sessions (Codex on the subscription; fresh folder each; stdin closed; containment scanned)

| Stage | Result | Containment |
|---|---|---|
| Designer, run 1 | Spec passed the label check but was **rejected**: 190 of 198 descriptions shared a template opening and a "workstream" tag. The prompt was tightened and the designer re-run. | clean |
| Designer, run 2 | 396 units; independent label check (`bank/check_spec_q.py`) **0 differences**; anti-template and certification-text gates pass; quotas exact | clean |
| Generator, run 1 | Asked for the statement wording, which was missing from the brief; statements 1-3 were left empty. The brief was amended and the generator re-run. | clean |
| Generator, run 2 | 48 sources, 396 truth units, no deviations; gates G1-G4 and G7 pass | clean |
| Render (brain) | 48 PDFs, 96 page images; G1-G7 all **PASS** | n/a |
| Blind re-key, one session per quarter | 396 units keyed; labels agree with the key on **396 of 396** | clean |
| Adjudicator | 0 differences, 0 unresolved, every quarter | wrote a scratch file to `/tmp/adjudication_diffs.json`, against its instructions. Nothing was read outside its folder, so blindness is unaffected; logged here. |
| Freeze | `frozen-q.json`: 55 files (truth, reference, PDFs); the synth-bank copy hashes clean | n/a |

**Note:** the first designer session finished seconds after the second started, and both wrote `designer.jsonl` (the session log). The first folder was moved aside and its spec unused. The kept spec is the second run's.

## Gates run by the brain session

- **The independent label check** (`bank/check_spec_q.py`, using `bank/bcode.py`, written from the definitions, not by Codex) recomputes every unit's error class, breach, disposition, and owner from the printed values and the agreement: 0 differences.
- **The reader check** (`bank/check_reader.py`): arm D's certificate reader reads every printed value on all 48 certificates exactly.

## Quotas (every quarter)

- 2 cases in each of the 10 error classes.
- 1 honestly reported breach.
- The benign cases as in `quotas-q.md`.
- Scored quarters: 40 planted errors plus 2 honest breaches; the key holds 42 units.
