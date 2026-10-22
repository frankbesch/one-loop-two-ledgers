# One Loop step 7b: the cap fix, scored (2026-10-09)

**Verdict: the fix holds on every test, and every pre-registered claim passes.** The live runs did not exercise it, though. On their answers, the old rule gives the same outcomes. The evidence for the fix is the injection test.

- **Pre-registration:** publishing `one-loop-two-ledgers/13-capfix-preregistration.md`, commit `d7aec0c`, pushed before any scored run.
  - Code: private source `66bb007`. Freeze: `bank/frozen/FREEZE-BANK-2.json`, 25 files, commit `25d10fd`.
- **The rule (decision invariance):** code posts a unit only when the unit posts under every way the doubted answers could resolve.
- **Data:** the step 7 corpus, key, floors, questions, and model (`claude-sonnet-5-5` on the subscription). Only the rule changed.
- **Summary data:** `INJECTION-20261009.json`, `REPLAY-step7-frozen.json`, `REPLAY-step7-invariant.json`, `CAPFIX-summary.json`, `REPLAY-step7b-frozen.json`.
- **Voids:** one, logged.
  - Run 2's model returned truncated JSON on one Q2 question, and that answer failed closed.
  - By the void rule the run was repeated as `D2-q1234-r2-repeat`; the void note is `D2-q1234-r2/VOID.txt`.
  - For the record, the void run scored 0 silent and 43 held.

## Claims (pre-registered thresholds)

| # | Test | Result |
|---|---|---|
| H21 | Single-abstention injection: 272 cases, 48 certificates | **PASS**: invariant rule 0 silent. The step 7 rule let 12 through. |
| H21-d | Detector: does the step 7 rule fail this test? | **PASS**: yes, 12 silent, so the test has power |
| H22 | Pair-abstention injection: 600 cases | **PASS**: invariant 0 silent. The step 7 rule let 28 through. |
| F | Step 7 rule replayed on step 7 D r1-r3 logs | **PASS**: 0 differences from the live outcomes |
| H26 | Invariant rule on step 7 D r1-r3 logs | **PASS**: 0 silent in every run; 43, 43, 42 held |
| H23 | 3 fresh live runs, Q3-Q4: 0 silent in every run | **PASS**: 0, 0, 0 |
| H24 | At most 3 false holds in every run | **PASS**: 1, 2, 0 |
| H25 | At least 95% owner accuracy in every run | **PASS**: 42/42 in every run |

The pre-registration also asked for these, reported without a threshold:

| Run | Silent | Held (key 42) | False holds | Planted caught | Hidden breaches | Units the fix changed | List-price estimate, Q1-Q4 |
|---|---|---|---|---|---|---|---|
| r1 | 0 | 43 | 1 | 40/40 | 4/4 | 0 | $2.80 |
| r2 repeat | 0 | 44 | 2 | 40/40 | 4/4 | 0 | $2.13 |
| r3 | 0 | 42 | 0 | 40/40 | 4/4 | 0 | $2.35 |

- **Step 7 claims re-scored on the new runs:** H12, H13, H14, H16, and H20 pass.
  - Pairs of runs agree on 99.0-99.5% of units, and no differing unit is one the key holds.
- **Injection extra holds:** 0 under both rules. The fix held no unit the key posts.
- **Injection misses by unit type:** under the step 7 rule, all 12 single and all 28 pair misses are cap-exceeded addbacks.
  - They sit in 4 certificates: q1_b04, q2_b09, q3_b01, q4_b07. Each holds one of the corpus's 8 cap errors.
  - No covenant was missed, even though the covenant guard could not fire.
- **Counterfactual:** each new run, replayed under the step 7 rule, gives the same outcome unit for unit.
  - None of the 6-8 abstentions per run fell on a line that a cap test depended on.

## Findings

1. **The gap was structural, not a one-off.** With any one answer on the earlier cost-savings line doubted, the step 7 rule posts the later over-cap line. That holds in 4 of the 8 certificates that carry a cap error. Step 7's miss was the one time a live run drew that abstention.
2. **The decision-invariance rule closes it at no cost here.** It gives 0 silent in 872 injected cases, and it held no extra unit.
3. **Step 7's post-hoc fix was incomplete.** This check was run after the pre-registration and is not part of it. The post-hoc fix still lets 4 of the 12 single cases through: those where the model doubts the category itself. A rule that enumerates the closed option list covers them; a hand-patched bucket rule does not.
4. **A guard can pass review and still never fire.** The step 7 covenant guard compared a result with itself, because its stand-in category is never permitted. The live logs show it never fired. The step 7 sentence "the covenant tests already had that protection" is wrong. On this corpus the gap let no covenant through.
5. **Fresh runs alone would not have shown any of this.** All three runs passed under both rules. Only the injection test, which forces each abstention, shows the difference.

## Limits

- Same corpus as step 7, and the fix was designed after the miss.
- The live runs test new model draws, not new data. A fresh certificate set, frozen before the rule meets it, is the next test.
- The key plays the person, and the rules match the planted classes by design.

## Spend

- No Jev calls.
- General model on the subscription, list-price estimates, not charges: r1 $2.80, r2 void $2.67, r2 repeat $2.13, r3 $2.35. **Total $9.95.**
