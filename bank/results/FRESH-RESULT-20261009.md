# One Loop step 7c: a fresh certificate set under the fixed rule, scored (2026-10-09)

**Verdict: on 48 unseen certificates the loop lets nothing through silently, and every claim the live runs carry passes. The fix itself was not tested: the fresh set has no cap error that depends on an earlier line, so the injection detector failed, as the pre-registration allowed.**

- **Pre-registration:** publishing `one-loop-two-ledgers/14-fresh-set-preregistration.md` (`4e3db47`), committed before the build and before any model call on the set.
- **Data:** `synth-bank-2/`, built and frozen at 09:55 CT with no rebuilds and no reader change (`BUILD-REPORT.md`; private source `9cb3ad8`).
  - The blind re-key agreed with the key on 396 of 396 units, and the adjudicator left 0 differences unresolved.
- **Run freeze:** `bank/frozen/FREEZE-BANK-3.json`, 28 files: the step 7b rule set, the new corpus, and both pre-registrations.
- **Fixed:**
  - the rule: decision invariance, unchanged from `66bb007`;
  - the model: `claude-sonnet-5-5` on the subscription;
  - the starting floors: QC 0.80, QR 0.85, QX 0.95;
  - the loop: on.
- **Summary data:** `INJECTION-fresh-20261009.json`, `FRESH-summary.json`, `REPLAY-fresh-frozen.json`.
- **Voids:** one.
  - Run 3's model returned truncated JSON on one Q2 question, and that answer failed closed.
  - The run was repeated as `D3-fresh-r3-repeat`; the void note is `D3-fresh-r3/VOID.txt`.
  - For the record, the void run scored 0 silent and 42 held.

## Claims

| # | Test | Result |
|---|---|---|
| H27 | Single-abstention injection, 256 cases: the invariant rule posts 0 key-held units | PASS, **but uninformative** (see H27-d) |
| H27-d | Detector: the frozen step 7 rule posts at least 1 | **FAIL**: it also posts 0 |
| H28 | Pair-abstention injection, 512 cases: invariant 0 | PASS, uninformative for the same reason |
| H29 | 3 live runs, Q3-Q4: 0 silent in every run | **PASS**: 0, 0, 0 |
| H30 | At most 3 false holds in every run | **PASS**: 1, 2, 3. Run 3 sits at the limit. |
| H31 | At least 95% owner accuracy in every run | **PASS**: 42/42 in every run |
| H32 | Every hidden breach and at least 90% of planted errors caught in every run | **PASS**: 4/4 and 40/40 in every run |

The pre-registration also asked for these, reported without a threshold:

| Run | Silent | Held (key 42) | False holds | Floors in force for Q3 (QC/QR/QX) | Units the fix changed | List-price estimate, Q1-Q4 |
|---|---|---|---|---|---|---|
| r1 | 0 | 43 | 1 | 0.50 / 0.65 / 0.95 | 0 | $2.12 |
| r2 | 0 | 44 | 2 | 0.50 / 0.75 / 0.95 | 0 | $2.23 |
| r3 repeat | 0 | 45 | 3 | 0.55 / 0.65 / 0.95 | 0 | $2.20 |

- **Step 7 claims re-scored:** H12, H13, H14, H16, and H20 pass on the fresh set.
  - Pairs of runs agree on 98.0-98.5% of units, and no differing unit is one the key holds.
- **Replay check:** replaying each run's log under the invariant rule reproduces its live outcomes exactly.

## Why the detector failed

- **Fresh set:** every one of its 8 cap errors is over the cap on its own.
- **Step 7 set:** 4 of its 8 cap errors crossed the cap only because an earlier, valid cost-savings line counted toward it.
- **The cause:** the brief does not fix this; the designer chose it at random.
- **The consequence:** doubting an earlier line cannot change any cap outcome here, so neither rule can fail, and the injection test has no power. The pre-registration named this case and said H27 would then be reported as uninformative.

## Findings

1. **The loop carried over to unseen certificates without a silent error.** It ran with the same rules, prompts, floors, and model. All three runs caught all 40 planted errors and all 4 hidden breaches, routed every held unit to the right owner, and let 0 errors through.
2. **The fix is still untested on data it was not designed on.** Its evidence remains step 7b's injection test on the step 7 set. The fresh set confirms only that the fix costs nothing: on every run it changed no unit.
3. **Exposure to the cap gap is a property of the data.** Whether a dependent-line gap can bite turns on how cap cases are built. A test of the fix needs a set that requires dependent cap cases, pre-registered as a stress set.
4. **The learning step lowered floors further on new data.** After Q1-Q2 it promoted lower floors in every run: QC 0.50-0.55, QR 0.65-0.75. The step 7 runs mostly kept 0.80 and 0.85. Silent errors stayed at 0, and held units rose to 43-45. This is reported, not claimed. Lower floors leave more of the safety to the rules, which is where the cap gap was.
5. **Truncated replies are now a recurring fault.** Two runs in this session were voided for one truncated reply each: 2 in about 2,050 live calls across steps 7b and 7c. Each void costs a full repeat run.

## Limits

- Same designer, brief, and rule definitions as step 7. The rules match the planted classes by design.
- The key plays a perfect person.
- Three counted runs.

## Spend

- No Jev calls.
- Codex: 7 sessions on the subscription (designer, generator, 4 re-keys, adjudicator).
- General model on the subscription, list-price estimates, not charges: r1 $2.12, r2 $2.23, r3 void $2.73, r3 repeat $2.20. **Total $9.28.**
