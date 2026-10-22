# Job B label-swap test: pre-registered reading (D-295)

Written 2026-10-08, before any live Jev call. Do not edit after the first live call.

## Question

Do the column-header and remark lead-in words alone move Jev's escalation on the job B questions? Run 2 showed that header vocabulary alone moved Jev on header fields (D-292, `artifacts/typed-questions-2026-09-28/09-label-test.md`).

## Arms (Jev only, calibration split, the same 210 lines, floors 0.60)

| Arm | Command | Unit labels |
|---|---|---|
| A1 standard | `run_b.py --split calibration --backend jev --mode live --vocab standard --yes --d283 <case> --max-spend 0.05` | Description, Reference, "Line N remark" |
| A2 alternate | the same with `--vocab alternate` | Particulars, Authority ref, "Note on item N" |

Only the labels change. Cell text, remark bodies, questions, options, model (`jev-1.13.0`), and floors are identical. Round-2 questions follow each arm's own Q2 answers, so the per-question count may differ. Escalation is read per question as a rate.

A1 is also the Jev-only calibration arm that step 3 needs, and it sizes the Claude call budget (D-293 (4)). Only A2 is extra spend for this test.

## Reading (escalation = a model answer at `needs_review`, per question)

- **VOCAB-SENSITIVE** (revisit trigger): any question's escalation moves 20 points or more from A1 to A2. Then rebuild job B with a balanced vocabulary factor before scoring (D-295).
- **STABLE**: every question moves less than 10 points.
- **MIXED**: anything else. Report it; no rebuild.

Also reported, not part of the verdict: outcome accuracy in each arm, and M1-M3 in each arm.

`score_b.py <A1 dir> --compare <A2 dir>` prints `points_moved` per question and `revisit`.

## Spend (D-283 case needed; Frank runs it from his Terminal)

- Per arm: 516 requests; the hard bound is $0.0265 (UTF-8 bytes counted as tokens, `--max-spend` stops before passing it).
- Expected: about $0.009 per arm at characters/3. Both arms together come to about $0.018. A2 alone, the label-swap test proper, is about $0.009, within D-295's "about $0.01".
- Key loader: `export TYPESAFE_API_KEY=...` in the runner's own shell (see `.env.example`).
