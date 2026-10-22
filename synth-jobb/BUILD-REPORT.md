# Job B full data build (2026-10-08)

**Verdict: BUILT, VALID, AND FROZEN. The scored split was rebuilt with fresh wordings, so it is now held out on wording.** There are 48 documents (64 pages) and 426 lines: 210 calibration, 216 scored. Gates G1-G9 pass. The two splits share 0% of claim wordings (it was 89%). The question set's decision rows match 426/426 outcomes. Calibration content is unchanged from the first freeze (PDF hashes identical).

## Scored-split rebuild (Frank's ruling, 2026-10-08: "Rebuild scored")

Runner: `jobb/rebuild_scored.py`. A fresh Codex designer wrote the scored cases only (133 s). It was given the calibration entities, AFE numbers, and 69 masked wordings to avoid (`jobb-inputs/calibration_context.json`, `designer-addendum-scored.md`). The frozen generator code built both splits from the merged spec, so both share one renderer. A fresh blind re-key (220 s) and adjudicator (99 s) covered the scored pages only. Spend: Codex on the subscription only.

| Check | Result |
|---|---|
| Wording overlap, scored claim lines reusing a calibration wording (`check_overlap.py`, cap 10%) | 0 of 156 (0%); was 134 of 150 (89%) |
| Calibration sources rebuilt byte-identical | 24/24; calibration PDFs keep their first-freeze hashes |
| Independent spec check, both splits | PASS |
| Gates G1-G9 | PASS, after four checker fixes (below) |
| Blind key vs original key, scored | 7 lines differ, all property misreads by the keyer (2 carry through to outcome); the adjudicator upheld the original on all 11 fields. 15 remark-numbering-only differences. 0 unresolved. |
| Q16 replay, both splits | 426/426; code alone gets 274 right (75 calibration and 80 scored lines need a model) |
| Freeze | 51 files; hashes re-verified in the repo |

Brain-side fixes in this rebuild, each logged in `records/scored-rebuild/`:
1. **Schema mapping.** The two designers named fields differently (`net` vs `net_amount`; no `pages`, `billing_period`, invoice `vendor`, or remark `page`). Each value was derived from the new spec itself (`rebuild_scored.conform`).
2. **Net rounding.** On 4 lines the designer rounded half-cents down; the generator rule is round-half-up, and net is derived, not a planted case. The values were recomputed: `sco_jib_10:9`, `sco_jib_15:1`, `sco_inv_02:6`, `sco_inv_02:7`, each by 0.01.
3. **Checker rules widened to the brief's own definitions** (the original is kept as `check_b.py.full-build`):
   - AFE numbers may carry dashes inside the letters ("R-W-M/58261/OC").
   - A line wrap after an in-word hyphen is not a space.
   - A literal placeholder is the value after any label.
   - Bait may sit in either column.
4. **Quota record.** The designer's self-reported counts used other key names and another "value over code" definition. They are kept as `quota_check_designer_scored`; the gate compares its own counts.

Code-layer rules the step 2 runner must carry (found here, already in `q_replay.py`):
- **Q10 normalizer.** Adjacent letter groups merge (R-W-M = RWM); digit groups stay bounded.
- **Q9 token lister.** Spaces are allowed around `/` and `-`, never after `:`.

The first full build's scored split (commit 97cacbe) is superseded. Its keys are in `adjudication/adjudication_b.full-build.json` and `records/full-build-2026-10-08/`.

---

# First full build (superseded scored split; calibration unchanged)


Request: Frank, "run the full job B build" (2026-10-08).
Spend: four Codex sessions on the subscription (designer 168 s, generator 393 s, blind re-key 295 s, adjudicator 107 s). No parser, Jev, or Claude API call (D-283).
Runner: `jobb/run_jobb.py --mode full`. Independent checks: `jobb/check_spec.py` and `jobb/q_replay.py`. Each session ran in a fresh folder outside the repo.

## Checks

| Check | Result | Evidence |
|---|---|---|
| Designer spec | PASS | 24 documents and 210 lines per split; designer's own quota check |
| Spec, independent check (quotas per split, splits disjoint, register consistency, word ban) | PASS | `check_spec.py`: every quota met in both splits; 6 authority kinds × 3 lines; 126 lines per split print "AFE" (the smoke run had 0) |
| Generator source gates | PASS | `SOURCE-REPORT.md`; 13 tests pass |
| Render (brain side) | FAIL, then PASS | Chrome wrote each PDF but never exited, so the 90 s timeout fired. The fix polls for the finished PDF and then stops Chrome, as the run 1 generator does. The original is kept as `build_b.py.codex-original`. Result: 48 PDFs, 64 page images. |
| Gates G1-G9 after render | PASS | `gate_results_b.json` |
| Blind re-key, contained | PASS | 420 lines and 96 remarks, 0 UNSURE, no command outside its folder |
| Key agreement, 7 labels × 420 lines | PASS | 0 label differences |
| Adjudicator | PASS | 22 records differ, 0 unresolved. On 4 lines the blind key misread the property, and the original stands. The other 18 are remark numbering (see below). |
| Freeze | PASS | `frozen-b.json`, 51 files; hashes re-verified after the copy into the repo |
| Q16 rows with perfect model answers | PASS | 420/420 outcomes match the key (`records/replay.json`) |
| Code-only arm | 268/420 right | Per split: 76 lines need a model (57 unsupported, 18 other_authority, 1 supported). That clears the 15-target floor for the "value over code" mark. |

## Deviations

1. **Remark numbering.** The generator numbers remarks in spec order and binds that number to the page source (`data-remark`). The blind key numbers them in reading order. The adjudicator picked reading order for 18 remarks. Applying that broke G8, the source binding, while the content of all 96 remarks matches exactly. So the original numbering stands. Scorers must join remarks to lines by `(doc_id, names_line)`, never by `remark_id`.
2. **Q8 coverage.** 12 literal placeholders sit in the description column (for example "Valve packing replacement; Approved AFE: Pending"). Q8 reads only the reference column, so it misses them; Q7 catches them. Outcomes stay right.
3. **Tokens with spaces.** Reformatted numbers include spaced forms ("RWM / 31000 / OC"). The code that lists Q9 candidates must allow spaces around separators. `q_replay.py` now does, and the step 2 runner must too.

## The limit (resolved by the rebuild above): the splits shared claim wordings

Positions differ: only 21 of 210 lines hold the same case at the same document and line number. But wordings repeat. Once numbers are masked, 146 of 162 scored claim lines (90%) use a wording that also appears in the calibration split (39 shared wordings out of 53 and 54). Thresholds tuned on calibration will therefore meet mostly familiar wordings in the scored split. That flatters the scored result.

Options:
1. **Rebuild the scored split only, with fresh wordings (recommended).** Rerun the designer and generator for `scored`, banning every calibration wording, then re-key and adjudicate. It is free and takes about 20 minutes. Calibration stays as built.
2. **Keep it, and state the limit in the write-up.** The scored result then measures familiar wording, not wording generalization.

## Header vocabulary (D-293, superseded by D-295, 2026-10-08)

No rebuild for header vocabulary: Frank ruled "go with A" (D-295), and this build stands. Both splits print the same standard header and column labels: Document, Billing period, Operator, Owner, Vendor; Line, Property, Description, Reference, Vendor, Gross, Decimal, Net. Header and column labels are not part of a job B question's input unit.

Carry-overs for the step 2 runner and the job B runs:
- **Label-swap arm.** Add a Jev-only label-swap arm on the calibration split. It resends the same units with the column-header and remark lead-in words swapped to an alternate vocabulary. Pre-register the reading before any live call, modelled on `artifacts/typed-questions-2026-09-28/label_test.py`. The arm needs its own D-283 case; Frank runs it from his own terminal with the key in the environment, spend bound about $0.01. Revisit trigger: if any question's Jev escalation moves 20 points or more, rebuild with a balanced vocabulary factor.
- **Run discipline.**
  - Log `claude --version` per arm.
  - Compute the Claude call budget from a Jev-only arm first.
  - Set Claude deadlines from about 4.2 s per call.
  - Run Claude-only arms in daytime.

## Next step toward calibration (step 3)

1. Build the step 2 line runner: column-bounded units, spaced-token candidates, remarks joined by line number, the D-295 label-swap arm, and `--smoke` on `synth-jobb-smoke/`.
2. Calibrate on the `calibration` split. A Jev or Claude API arm needs the D-283 test and Frank's approval first; a Claude arm on the subscription does not.
