# Job B smoke run (2026-10-08)

**Verdict: PASS with five prompt fixes.** The four-session build works end to end on 3 documents. The question set's decision rows reproduce every key outcome. Fix the prompts below before the full build.

Request: Frank, "start the job B smoke run" (2026-10-08, relayed from the parent session).
Spend: four Codex sessions on the subscription (about 11 minutes in total). No parser, Jev, or Claude API call (D-283).
Runner: `jobb/run_jobb.py` (prompts read from the brief). Replay: `jobb/q_replay.py`. Work folders were outside the repo, one fresh folder per session.

## Checks

| Check | Result | Evidence |
|---|---|---|
| S1 designer: spec written, smoke quotas met | PASS | `design/case_spec_b.json`; 24 lines, 8 remarks, 5 register entries; `records/designer.*` (126 s) |
| S2 generator: source build, gates G1-G4, G6, G7, G9 before render | PASS | `SOURCE-REPORT.md`; `records/generator.*` (390 s); its 21 tests pass |
| S2b render (brain side, headless Chrome) | PASS | 3 PDFs, 3 page images |
| Gates G1-G9 after render | FAIL, then PASS | The original check failed G4, G5, and G8: remark text "Line 4: ..." counted as a second table header. After a one-line fix to header detection, all nine pass. The original is kept as `check_b.py.codex-original`. |
| S3 blind re-key: contained, complete | PASS | 24 lines and 8 remarks; 0 UNSURE; no command named a path outside its folder (10 command events checked) |
| Key agreement (generator key vs blind key) | PASS | 0 differences over 7 labels × 24 lines and 8 remarks |
| S4 adjudicator | PASS | 0 differences, 0 unresolved (`adjudication/adjudication_b.json`) |
| Freeze | PASS | `frozen-b.json`: truth, 2 reference files, 3 PDFs |
| Q16 rows with perfect model answers (Q8, Q10, Q11 run on the printed text) | PASS | 24/24 outcomes match the key; 0 defects (`records/replay.json`) |
| Code-only arm (no model questions) | 10/24 right | 14 lines need a model: 12 unsupported (placeholders, no-number, remark-only) and 2 other_authority |

## What broke, and the fix for the full run

1. **The word ban emptied the vocabulary (high).** The designer read "never reuse a word from used_labels.txt" literally. The corpus never prints "AFE" or "approved", so the bait line tests nothing, and the entity names are single invented words. Fix: ban names, label phrases, and number formats only; ordinary words are allowed.
2. **Full-run counts leaked into the smoke (medium).** "At least 10 paraphrased placeholder wordings" made 10 of 24 smoke lines paraphrased placeholders. Fix: state variety as "no two share a wording", not as a count.
3. **The checker failed on rendered pages (medium).** The generator cannot render inside its sandbox, so its checker had never seen a real PDF. Fix: the prompt names the header-row rule, and the brain runs the checker after render (as here).
4. **Output paths (low).** The generator wrote `build_b.py` and `check_b.py` at the folder root, not under `src/`. The runner accepts both, and the brief now names the root.
5. **Text extraction for step 2 (medium, not a data defect).** Plain `pdftotext` interleaves wrapped Description and Reference cells: 4 of 28 claim texts are not verbatim in its output. The step 2 runner must build each unit from column-bounded words (bounding boxes), as `check_b.py` does. Otherwise Q17 rejects true quotes.

Also noted: register scope text does not match line descriptions (for example, "Compressor rebuild" on a pump-alignment line). That is harmless now, because Q12 (scope fit) is deferred, but it matters if Q12 returns.

## Next step toward calibration (step 3)

1. Apply fixes 1 to 4 to the brief's prompts (done in this commit), then run the full build: two splits, about 420 lines, the same four sessions.
2. Build the step 2 line runner with column-bounded units (fix 5), plus a `--smoke` mode on this corpus.
3. Calibrate on the `calibration` split. Jev or the Claude API is metered and needs the D-283 test and Frank's approval first; a Claude arm on the subscription does not.
