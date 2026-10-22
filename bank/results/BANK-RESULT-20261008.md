# One Loop step 7: the banking mirror, scored (2026-10-08)

Pre-registered in publishing `one-loop-two-ledgers/10-banking-mirror-plan.md` (313b376) before any data. Rulings: `09-finish-plan.md` R2-R3.
- **Data:** 48 compliance certificates (4 quarters × 12 borrowers), 396 units.
  - Built by Codex and frozen at 19:03 CT; build report `synth-bank/BUILD-REPORT.md`.
  - The blind re-key agreed with the key on 396 of 396 units; the adjudicator found 0 differences.
- **Calibration** on Q1-Q2. **Scored:** Q3-Q4, 198 units. The key holds 42: 40 planted errors (4 per class) and 2 honestly reported breaches.
- **The freeze:** `bank/frozen/FREEZE-BANK.json`, 22 files. Floors: QC 0.80, QR 0.85, QX 0.95.
- **Summary data:** `BANK-summary.json`, `POSTHOC-capfix.json`, `../frozen/reuse-B.json`.
- **Voids:** one, logged. The first run of arm C had one general-model call return unparseable JSON, and its certificate failed closed. By the void rule the run was repeated (`C-q34-VOID/VOID.txt`). Every other run is reported.

## Results (Q3-Q4)

| Design | Runs | Silent per run | Held per run | False holds | Planted caught | Hidden breaches caught | Owner right | Cost, Q3-Q4 (logged tokens × published price; not a bill) |
|---|---|---|---|---|---|---|---|---|
| **D, the loop** (typed questions on the general model, R3) | 3 | **1, 0, 0** | 42, 43, 42 | 1, 1, 0 | 39, 40, 40 of 40 | 4 of 4, every run | 41/41, 42/42, 42/42 | $0.87-1.07 (general model, about 130 calls) |
| B, one agent (worksheet + calculator) | 3 | **0, 0, 0** | 42, 42, 42 | 0, 0, 0 | 40 of 40, every run | 4 of 4 | 42/42 every run | $0.58-0.63 (2 calls, 105-129 tool calls) |
| C, cascade, as built | 1 (after one void) | 2 | 48 | 8 | 38 of 40 | 4 of 4 | no owner rule | Jev $0.008 + general model $0.77 |
| A, analyst, **assumed** 45% of certificates | seeded run / mean of 2,000 draws | 23 / 24.5 | 83 / 82.5 read | 64 | 18 of 40 | 3 of 4 | 19/19 | staff time |

- **Arm A range:** at an assumed 34%, 28 silent on average; at 56%, 17.5.
- **Arm C's handoffs:** Jev's confidence was low on certificates, so 92-95% of its units went to the general model.
- **Run-to-run:** the three B runs agree on every unit. Pairs of D runs differ on 1-3 units, and one of those is a planted error (below).

## Claims (pre-registered)

| # | Claim | Result |
|---|---|---|
| H12 | The loop lets at most 1 error per quarter through unseen | **PASS**: worst quarter 1 (r1, Q4) |
| H13 | The loop catches every hidden breach | **PASS**: 4 of 4 in every run |
| H14 | The loop catches at least 90% of planted errors | **PASS**: 97.5-100% |
| H15 | The best single agent fails silently in at least 1 of 3 runs | **FAIL**: 0 silent in all 3 runs, and the runs agree on every unit |
| H16 | The loop's run-to-run differences fall only on units the key posts | **FAIL**: 1 differing unit is a planted error (r1's cap line) |
| H17 | The loop sends fewer units to a person than the best agent | **FAIL**: median 42 against 42 (equal) |
| H18 | At least half of the platform's components run unchanged | **FAIL**: 4 of 25 unchanged (16%); 15 of 25 unchanged or configured (60%); 9 rewritten; 1 not used |
| H19 | The cascade lets more errors through than the loop | **PASS**: 2 against at most 1 |
| H20 | The loop routes at least 95% of held units to the right owner | **PASS**: 100% in every run |
| Mark | At most 1 false breach flag per quarter | **PASS**: 0 in every run |

## The loop's one miss, traced (D r1, certificate q4_b07)

- **The model's part was right.** On addback 2 (cost savings), its realized-or-projected answer had 0.82 confidence, below the 0.85 floor. The line went to "needs review" and was held, as designed.
- **The code then left the held line out of the cost-savings cap total.** Without it, addback 4 no longer crossed the cap, so the code posted it. The key counts both lines and puts addback 4 over the cap.
- **The rule failed closed on the doubted line, but not on the line whose test depended on it.** The covenant tests already had that protection; the cap test did not.
  - **Correction (2026-10-09, `CAPFIX-RESULT-20261009.md`):** the covenant guard could never fire, because its stand-in category (`ordinary_operating`) is never permitted. Covenants had the same gap; on this corpus it let no covenant through.
- **Post-hoc, not pre-registered** (`posthoc_capfix.py`; no new model calls):
  - The corrected rule tests each later cost-savings line both ways, with and without the doubted line, and holds it when the two disagree.
  - On the logged answers it gives 0 silent in all three runs, at 43, 43, and 42 held.
  - Replaying the frozen rule reproduces r1's live outcomes exactly, so the replay can be trusted.

## Findings

1. **On this ledger the single agent was perfect and fully repeatable.** Step 6's "judge by the worst run" did not recur in 3 runs. One untested difference stands out: a banking quarter is 12 short certificates (a 59k-character prompt), against an about 195-255k-character billing month in step 6 (logged prompt_chars, months 3-6). Whether agent misses grow with packet size is a hypothesis for the write-up, not a finding.
2. **The loop's only miss came from its own code, not from a model.** An abstention must reach every rule that depends on the abstained value. That is a design rule the loop needs, and the replay shows it closes the miss.
3. **The loop's cost advantage belongs to the small model, not the architecture.** On the general model (R3), the loop cost more than the single agent at list price ($0.87-1.07 against $0.58-0.63 for two quarters), because it asks about 65 narrow questions a quarter. Step 6's loop ran on the small model at $0.007 a month.
4. **The owner rule transferred cleanly.** The loop and the best agent both routed every held unit to the right owner: the Required Lenders, the credit officer, or the analyst.
5. **Reuse:** the loop's shape carried over, but most domain code was rewritten.
   - Unchanged: the word-box reader, the CLI and Jev backends, and the agent runner with its calculator.
   - Configured: the typed-question contract, the decide-and-floor rule, the quote check, the audit sample, the learning step, the floor sweep, the arm A and C runners, the data-build runner, and freeze tooling.
   - Rewritten: the rules, the reader's table logic, the scorer, and replay.
6. **The cascade again leans on the general model** (92-95% of units) and lets 2 errors through. An analyst reading 45% of certificates lets about 25 of 42 holds through.

## Limits

- One synthetic corpus built in one evening; banking publishes no error baseline, so the error mix is an assumption.
- The answer key plays a perfect reviewer and a perfect syndicate.
- The loop's rules match the planted classes by design.
- One certificate template, with no format change: step 7 tests a second ledger, not drift.
- Three runs per design; the cascade ran once.

## Spend

- Jev, arm C (D-300) [measured, input tokens at the docs price]: void run $0.008014, Q1 smoke $0.003897, scored run $0.008014. **Total: $0.019925.**
- General model on the subscription, list-price estimates, not charges:
  - D calibration: $1.21.
  - D runs, all quarters: $1.87-2.24 each.
  - B: $0.58-0.63 a run.
  - C fallback: $0.77.
