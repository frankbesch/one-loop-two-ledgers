# One Loop step 7e: the floor lock on the stress set, scored (2026-10-09)

**Verdict: with the floor lock, every pre-registered claim passes. On the stress set the loop let 0 errors through in all three live runs. It held 47-50 units against the key's 46, and the lock stopped one real error live.**

- **Pre-registration:** publishing `one-loop-two-ledgers/16-floor-lock-preregistration.md` (`8a6ce1c`), committed before any run under the lock.
  - Code: private source `e0c2fd4`. Run freeze: `bank/frozen/FREEZE-BANK-5.json` (`60e3342`).
- **The rule:**
  - The learned floor decides whether an answer is accepted for its own line.
  - The locked floor (the frozen start: QC 0.80, QR 0.85, QX 0.95) decides whether other units may rely on that answer.
  - An answer accepted below the lock is "weak". Every other unit must post under every resolution of it.
- **Data:** the step 7d stress set (`synth-bank-3`), unchanged.
- **Summary data:** `INJECTION-confident-stress-20261009.json`, `REPLAY-stress-lock.json`, `LOCK-summary.json`, `REPLAY-lock-runs-nolock.json`.
- **Voids:** none. All three runs completed with 0 call errors.

## Claims

| # | Test | Result |
|---|---|---|
| H39 | Confident-error injection, 1,468 cases: no key-held unit other than the injected line posts | **PASS**: 0 |
| H39-d | Detector: the step 7b rule (no lock) posts at least 1 | **PASS**: 155 (126 cap errors, 29 hidden breaches, 20 distinct units) |
| H40 | Step 7d logs under the lock: 0 silent in every run | **PASS**: 0, 0, 0; held 48, 49, 50 |
| H41 | 3 fresh live runs, Q3-Q4: 0 silent in every run | **PASS**: 0, 0, 0 |
| H42 | At most 55 held in every run | **PASS**: 47, 50, 49 |
| H43 | At least 95% owner accuracy in every run | **PASS**: 46/46 in every run |
| H44 | Every hidden breach and at least 90% of planted errors caught | **PASS**: 4/4 and 44/44 in every run |
| Power check | Does the step 7b rule (no lock), replayed on the live answers, post a key-held unit? | **Yes**: in run 3 it posts 1 (q4_b04 A4). The lock was exercised live and stopped it. |

The pre-registration also asked for these, reported without a threshold:

| Run | Silent | Held (key 46) | False holds | Q3 floors (QC/QR/QX) | Accepted answers below the lock, Q3-Q4 | No-lock replay | List-price estimate |
|---|---|---|---|---|---|---|---|
| r1 | 0 | 47 | 1 | 0.40 / 0.55 / 0.95 | 22 of 151 | 0 silent, 46 held | $2.59 |
| r2 | 0 | 50 | 4 | 0.60 / 0.70 / 0.95, then 0.40 / 0.60 | 17 of 142 | 0 silent, 50 held | $2.65 |
| r3 | 0 | 49 | 3 | 0.55 / 0.70 / 0.95, then 0.55 / 0.60 | 16 of 146 | **1 silent**, 48 held | $2.58 |

- **Injection extra holds:** 0 under both rules. In 175 cases the injected wrong answer decides its own line by design, and that line posts; the lock does not cover the line itself (pre-registered limit).
- **Step 7 claims re-scored:** H12, H13, H14, H16, and H20 pass.
  - Pairs of runs agree on 97.5-98.5% of units, and no differing unit is one the key holds.
- **Replay check:** replaying each run's log under the lock rule reproduces its live outcomes exactly.
- **What the lock cost:** only 1 false hold in the three runs came from the lock itself, a covenant held in r1 because it depended on a weak answer (q4_b02 LEV). The other 7 false holds are lines the model doubted or mislabeled.

## The error the lock stopped (D5 r3, q4_b04)

| Line | Truth | Model's category answer |
|---|---|---|
| A1, anchor | valid cost saving (realized, certified) | "ordinary operating" at 0.68: above the learned QC floor of 0.55, below the 0.80 lock |
| A4 | crosses the cap only with A1 counted | cost savings, 0.80 |

- **Without the lock:** A1 leaves the cost-savings total, A4 falls under the cap, and A4 posts silently. This is step 7d's mechanism on a different certificate.
- **With the lock:** A1's answer is weak. A4 holds under the resolution where A1 is cost savings, so A4 is held.

## Findings

1. **The floor lock lets the learning step cut holds without letting dependent errors through.**
   - The learning step still cut QC to 0.40-0.55 and QR to 0.55-0.60.
   - The loop held 47-50 units against the key's 46. Step 7d, with no lock, held 46-49 and let 1 through per run; post-hoc with no learning, it held 58-61.
   - The lock kept almost all of learning's hold reduction and closed the gap.
2. **The lock stopped a live error in 1 of 3 runs,** the same mechanism as step 7d's miss, on another certificate.
3. **The model's step 7d error did not repeat.** On q3_b01 A3, step 7d's four runs all answered "ordinary operating". This step's three runs answered "cost savings" at 0.80 (r1), "needs review" (r2), and "cost savings" at 0.68 (r3).
   - Step 7d's "systematic" reading holds within a session, not across sessions.
   - Errors on hard items can repeat within a session and vary across sessions. A test that runs once, or runs three times in a row, can under- or over-state them.
4. **The design rule, in one line:** an answer may decide its own line at the learned floor, but another line may rely on it only at the locked floor.

## Limits

- **H39 holds by construction.** It checks the code; the detector shows that the step 7b rule lacks the property.
- **H40 is on seen data.**
- **The stress set is built to contain the gap,** and its builder is Claude Opus.
- **A confident wrong answer still decides its own line.** The injection shows that 175 lines' own outcomes can be wrong. The lock protects only dependents.
- **One certificate set, three runs, and a key that plays a perfect person.**

## Spend

- No Jev calls.
- General model on the subscription, list-price estimates, not charges: $2.59 + $2.65 + $2.58 = **$7.82**.
