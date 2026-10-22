# One Loop step 7d: the stress set under the fixed rule, scored (2026-10-09)

**Verdict: the fix works where the gap is, but the loop still let 1 error through in every run, so H35 fails.**
- **The fix:** the injection test passes with full power. The fixed rule stops all 63 single and all 210 pair cases that the old rule lets through.
- **The miss:** the same one in all three runs. The model confidently mislabeled a valid anchor line. By then the learning step had lowered the floor that would have held it. The fix guards against doubted answers; it cannot guard against a confident wrong one.

- **Pre-registration:** publishing `one-loop-two-ledgers/15-stress-set-preregistration.md` (`76b1ef6`), plus amendment 1 (`72589ef`: builder switched from Codex to Claude Opus), both before any data.
- **Data:** `synth-bank-3/`, 48 certificates, 4 dependent cap cases per quarter. The scored quarters' key holds 46 units.
  - The build has one logged designer rebuild and one reader fix before the freeze (`BUILD-REPORT.md`, private source `b90d5c6`).
- **Run freeze:** `bank/frozen/FREEZE-BANK-4.json`.
- **Summary data:** `INJECTION-stress-20261009.json`, `STRESS-summary.json`, `REPLAY-stress-frozen.json`, `POSTHOC-nolearn-stress.json`.
- **Voids:** one.
  - Run 2's model returned truncated JSON on one Q4 question, and that answer failed closed.
  - The run was repeated as `D4-stress-r2-repeat`; the void note is `D4-stress-r2/VOID.txt`.
  - For the record, the void run scored 0 silent and 51 held. See finding 3.

## Claims

| # | Test | Result |
|---|---|---|
| H33 | Single-abstention injection, 311 cases: invariant rule 0 silent | **PASS**: 0 |
| H33-d | Detector: frozen step 7 rule posts at least 8 | **PASS**: 63, covering all 16 dependent cap lines |
| H34 | Pair-abstention injection, 902 cases: invariant rule 0 silent | **PASS**: 0. The step 7 rule let 210 through. |
| H35 | 3 live runs, Q3-Q4: 0 silent in every run | **FAIL**: 1, 1, 1, the same unit each time (q3_b01 A5) |
| H36 | At most 3 false holds in every run | **FAIL**: 1, 3, 4 |
| H37 | At least 95% owner accuracy in every run | **PASS**: 45/45 in every run |
| H38 | Every hidden breach and at least 90% of planted errors caught in every run | **PASS**: 4/4 and 43/44 (97.7%) |
| Power check | Does the step 7 rule, replayed on the live answers, post a key-held unit? | **Yes**: in run 3 it posts 2, against the fixed rule's 1. The live runs exercised the fix, and it stopped one error. |

The pre-registration also asked for these, reported without a threshold:

| Run | Silent | Held (key 46) | False holds | Q3 floors (QC/QR/QX) | Step 7 rule on the same answers | List-price estimate |
|---|---|---|---|---|---|---|
| r1 | 1 | 46 | 1 | 0.40 / 0.55 / 0.95 | 1 silent | $3.04 |
| r2 repeat | 1 | 48 | 3 | 0.50 / 0.55 / 0.95 | 1 silent | $2.67 |
| r3 | 1 | 49 | 4 | 0.50 / 0.55 / 0.95 | 2 silent | $2.67 |

- **Injection extra holds:** 0 single and 18 pair, the same under both rules. All 18 are covenants that read as breached when two doubted anchor lines leave EBITDA, a fail-closed hold.
- **Step 7 claims re-scored:** H12, H13, H14, H16, and H20 pass on the stress set.
  - Pairs of runs agree on 98.5-99.0% of units, and no differing unit is one the key holds.
  - H12 allows 1 a quarter, which is why it passes here.
- **Replay check:** replaying each run's log under the invariant rule reproduces its live outcomes exactly.

## The miss, traced (q3_b01, all three runs)

- **A3 is a valid anchor.** It is a realized, certified cost saving, dated within the window: "Insurance premiums fell at the March 2025 renewal after the foundry closure ...".
- **The model's answer:** on the category question it answered "ordinary operating" at 0.70 (r1) and 0.62 (r2 repeat, r3).
- **The floors:** they started at QC 0.80. By Q3 the learning step had promoted QC to 0.40-0.50, so the wrong answer passed the floor.
- **What the code did:** it treated A3 as a non-permitted category and held it, which is one of the false holds. It also left A3 out of the cost-savings total.
- **The result:** A5, which crosses the cap only with A3 counted, then fell under the cap and posted.
- **Why the fix did not apply:** nothing was in doubt, because the answer cleared the floor. The fix tests decisions only against doubted answers.

## Findings

1. **The decision-invariance rule closes the dependent-line gap wherever the model abstains.** On a set built to expose it, the step 7 rule lets 63 single and 210 pair abstention cases through, and the fixed rule lets 0 through.
   - Live, it stopped one real error in run 3.
   - Post-hoc, with the floors held at their starting values, the fixed rule gives 0 silent in every run, against 5-7 for the step 7 rule. This is not pre-registered (`posthoc_nolearn.py`).
2. **The learning step traded abstentions for confident errors.**
   - The step 6 promotion rule lowers a floor when the labeled units show no new silent error. But it sees only held units and a 5% audit.
   - On this set it cut QC from 0.80 to 0.40-0.50 and QR from 0.85 to 0.55, and it brought holds down from 58-61 to 46-49.
   - In doing so it let through one confident wrong answer, which the rules then could not catch.
   - Post-hoc, with no learning, false holds would have been 12-15 a run, so H36 would fail under that setting too. The trade is real in both directions.
3. **The void run shows the mechanism directly (reported, not scored).**
   - Run 2's learning step stopped at QC 0.70 for Q3.
   - The model answered A3 at 0.68, below that floor, so the answer became "needs review".
   - The fixed rule then held A5, and the run let 0 errors through.
   - Same answers, a higher floor, no miss.
4. **The model's error was systematic, not random.** All four runs, the void one included, read A3 as ordinary operating cost.
   - Repeating runs did not help: every run that accepted the answer made the same mistake.
   - Step 6's lesson, judge by the worst run, assumes errors vary from run to run. This one did not.
5. **What the loop needs next:** a floor the learning step may not lower for any answer that other rules depend on. That covers category and realized on cost-savings lines, wherever a cap or covenant test reads the line.
   - Alternatively, apply invariance to confident answers on dependency-bearing lines: hold a dependent unit if its outcome turns on that line's answer.
   - Either is a design change, to be pre-registered before it is tested.
6. **Transport faults recur.** Today, 3 runs were voided for one truncated reply each, in about 3,000 live calls.

## Limits

- **The stress set is built to contain the gap.** It measures the rule where the gap exists, not how often the gap occurs.
- **The builder is Claude Opus,** from the same family as the model under test (amendment 1). The anchor that fooled Sonnet was written by Opus.
- **One certificate drove every live miss.** With 16 dependent cases in the scored quarters, 1 systematic model error decided H35.
- **The key plays a perfect person,** and the rules match the planted classes by design.

## Spend

- No Jev calls.
- Opus build sessions on the subscription: 8 (two designer runs, generator, 4 re-keys, adjudicator). List-price estimate from the session envelopes: **$12.47**, not a charge.
- General model live runs, list-price estimates, not charges: r1 $3.04, r2 void $2.66, r2 repeat $2.67, r3 $2.67. **Total $11.04.**
