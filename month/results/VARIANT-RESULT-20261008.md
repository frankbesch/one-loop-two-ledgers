# One Loop step 6: arm B with a worksheet prompt (2026-10-08)

Pre-registered before the runs in publishing `one-loop-two-ledgers/06-b-variant-plan.md` (8dce7f8), with the re-freeze in private source 99b55d2.
- Three runs (w1-w3) on months 3-6, `claude-sonnet-5-5`, one call per month, on the subscription.
- No call errors, no void. Every run is reported.
- Summary data: `VARIANT-summary.json`.

## Results (months 3-6; the key holds 148 lines and 96 money errors)

| Arm | Runs | Silent per run | Held per run | False holds | Money caught |
|---|---|---|---|---|---|
| B, worksheet prompt | w1, w2, w3 | **0, 3, 0** | 148, 145, 148 | 0, 0, 0 | 96, 95, 96 |
| B, v1 prompt | r1, r2, r3 | 1, 1, 2 | 147, 147, 147 | 0, 0, 1 | 95, 95, 94 |
| D, this architecture | r1, r2, r3 | **0, 0, 0** | 154, 154, 152 | 6, 6, 4 | 96, 96, 96 |

## Claims (pre-registered)

| # | Claim | Result |
|---|---|---|
| H6 | The decimal blind spot is robust to prompting (the variant posts m3_jib_12 line 1 in at least 2 of 3 runs) | **FAIL**: posted in 1 of 3 (w2) |
| H7 | A better prompt does not close D's silent-error gap (at least 1 silent line in at least 2 of 3 runs) | **FAIL**: silent in 1 of 3 runs, with 3 lines in that run |
| H8 | D holds more lines than B under the variant (the variant's median held is below D's 154) | **PASS**: median 148, with 0 false holds |

## What the failing run shows (w2, read from its own worksheet)

The worksheet logs what the agent claims it looked up. Its three misses fail three different ways:

1. **It wrote the expected value where the printed value belongs.** m3_jib_12 line 1 prints 0.1125. The w2 worksheet row reads `LX/874/P|0.0875|0.0875`: decimal in force 0.0875, "printed" 0.0875. The agent recorded the number it expected, not the number on the page, so its comparison agreed with itself.
2. **It contradicted its own worksheet.** m4_jib_14 line 3: the worksheet marks the claim `unsupported` (AFE K[09140]/BX is not in the register), yet the line is missing from the exception list and posted.
3. **It accepted a reformatted AFE for the wrong property.** m6_jib_07 line 3 cites K[07305]/BX. The worksheet marks it `supported`. The register approves that AFE for LX/908/P, but the line bills LX/891/P.

D's design takes all three steps away from the model. Code reads the printed value from the page, code looks up the register and the property, and code combines the answers into the outcome. The model only picks from fixed options, and D's runs showed none of these failures.

## Revised findings (replace replication finding 2)

- **A better prompt makes the single agent excellent on most runs, not on every run.**
  - With the worksheet, B matched the key exactly in 2 of 3 runs: 0 silent, 0 false holds, fewer reviews than D.
  - In the third run it let 3 lines through unseen, including the money error it caught in the other two.
  - D let nothing through in 3 of 3 runs.
- **The reliability difference is per run, which is where an auditor lives.** An owner cannot tell a good draw from a bad one at review time. Each B run looks the same, and the bad one is not flagged.
- **The price of D's reliability is about 1.5 extra reviews a month,** against the best prompt. These are 4-6 correct lines held over four months, mostly claim abstentions in the new-format month.
- **Cost.**
  - B worksheet: $0.50-0.72 a month at list price, an estimate and not a charge on the subscription, at 101-296 s per call.
  - B v1: $0.33-0.53.
  - D: Jev $0.007 a month, measured.
- **Novel and actionable for practitioners:**
  1. A worksheet does not make an agent's reading checkable by itself; the agent can fill the "printed" column from memory.
  2. Have code read the printed numbers and do the lookups. Let the model answer only the narrow questions, and route its abstentions to a person.
  3. Judge an agent per run, not on its best run.

## Limits (in addition to REPLICATION-RESULT-20261008.md)

- **The two prompts were both written by us.** The worksheet was written after we saw v1's miss, as the strongest fix we could think of. Other designs, such as tools, a calculator, or per-document calls, are untested.
- **Three runs per prompt.** "1 bad run in 3" is an observation, not a rate.
