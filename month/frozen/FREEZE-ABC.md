# Step 6 freeze, arms A, B and C (2026-10-08)

**Frozen: the comparison arms' code, policy text, scoring, and data.** A live run of B or C on months 3-6 needs `--frozen month/frozen/FREEZE-ABC.json`. The runner re-hashes 18 files and refuses on any change. Without the freeze it refuses months 3-6. Both guards were tested, plus a changed-file test that refused on `arms_common.py`.
Design and fairness notes: publishing `one-loop-two-ledgers/04-arms-abc-as-built.md`. Arm D's own freeze (`FREEZE.json`) is untouched and still hashes clean.

## Tests on the calibration months (1-2, 420 lines; the key holds 72)

| Arm | Run | Silent | Held | Money caught | Cost |
|---|---|---|---|---|---|
| A, audit at 45% | seeded run | 33 | 187 | 28/48, 72% of dollars | none, a calculation |
| A, audit at 45% | mean of 500 draws per month | 41.7 | 173.6 | about 43% of dollars | none |
| B, oracle | harness proof | 0 | 72 | 48/48 | none |
| B, `claude-sonnet-5-5`, live | month 1, 1 call, 37 s, 39k tokens in, 6.2k out | 0 | 36 | 24/24 | subscription (list-price est. $0.22, not a charge: auth claude.ai) |
| B, `claude-sonnet-5-5`, live | month 2, 1 call, 40 s, 54k tokens in, 6.1k out | 0 | 36 | 24/24 | subscription (list-price est. $0.28, not a charge) |
| C, oracle | harness proof (both paths: 52 of 420 lines handed to Claude) | 0 | 72 | 48/48 | none |

Arm A at 34% / 45% / 56% (mean lines reviewed per month): 79 / 87 / 124. Mean silent per month: 22.6 / 20.9 / 14.9.
Receipts: `month/results/B-smoke-m1/`, `month/results/B-smoke-m2/` (calls, outcomes, meta).

**Arm B was perfect on both calibration months**: every held line right, no false hold, no silent line. Arm D's calibration was 0 silent and 74 held. The step 6 mark "D lower than B and C at equal or better catch" is pre-registered and stays as written. This result is reported as found.

## Not run

- **Arm C live, month 1 (calibration):** Frank's Terminal (Jev key, D-300). It checks the multi-question request shape (V2, V5) and the billing bound (V6). If it needs a code change, re-freeze before any run on months 3-6.
- **Step 5 (all arms on months 3-6):** Frank's go.
