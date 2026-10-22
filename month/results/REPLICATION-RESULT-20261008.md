# One Loop step 6: replication of arms B and D (2026-10-08)

Plan and claims were pre-registered before the runs: publishing `one-loop-two-ledgers/05-replication-plan.md` (959c297), with the re-freeze in private source f81ab3e.
Each arm has three runs on months 3-6 (840 lines; the key holds 148, including 96 planted money errors).
- r1 is the step 5 run. r2 and r3 are the replicates, on the same frozen code, data, models, and starting floors.
- No run was voided. Every run is reported.
- Summary data: `REPLICATION-summary.json`, from `replicate_summary.py`.

## Results (months 3-6)

| Arm | Run | Silent | Held | False holds | Money caught |
|---|---|---|---|---|---|
| B, one agent | r1 | 1 | 147 | 0 | 95/96 |
| B | r2 | 1 | 147 | 0 | 95/96 |
| B | r3 | 2 | 147 | 1 | 94/96 |
| D, this architecture | r1 | 0 | 154 | 6 | 96/96 |
| D | r2 | 0 | 154 | 6 | 96/96 |
| D | r3 | 0 | 152 | 4 | 96/96 |

Range (min/median/max):
- B: silent 1/1/2; held 147/147/147; money 94/95/95.
- D: silent 0/0/0; held 152/154/154; money 96/96/96.

## Claims (pre-registered)

| # | Claim | Result |
|---|---|---|
| H1 | D lets nothing through unseen | **PASS**: 0 silent in all 12 run-months |
| H2 | D catches at least 90% of planted dollars | **PASS**: 100% in all 12 run-months |
| H3 | D sends fewer lines to a person than B | **FAIL**: D held 152-154 lines, B held 147, in every run pair |
| H4 | B stays within the silent mark (at most 2 a month) | **PASS**: its worst month had 2 |
| H5 | D recovers from the format change within the month | **PASS**: 0 silent in month 4 after the map, all runs |

## Findings that survive replication

1. **The architecture turns model randomness into review load, never into misses.**
   - D's runs differ on 2-4 lines out of 840 (99.5-99.8% agreement). Every line that differs is a clean line held or released, never a planted error.
   - B's runs differ on 0-2 lines. In r3 the line that changed was a real error: a non-consent billing on m3_jib_09 line 4, caught in r1 and r2, posted unseen in r3.
   - In D, a model's bad draw costs a person a look. In B it can cost money nobody sees.
2. **The single agent has a blind spot it repeats.** All three B runs posted the same wrong owner decimal (m3_jib_12 line 1).
   - The line bills LX/874/P at 0.1125; the division order in force is 0.0875.
   - 0.1125 is a real decimal: another property's (LX/840/P), in force since the month 2 share transfer.
   - A plausible value from the wrong row passed review three times out of three. The exact lookup in D's code layer caught it every time.
3. **D's extra reviews are a known, bounded cost.**
   - D holds 5-7 more lines than B over four months. All of them are false holds, about 1.5 a month, mostly claim abstentions (`claim:needs_review`).
   - 3 of the false holds repeat in every run. All 3 are supported AFE claims in month 4, the new-format month: the drift cost shows up as review, not error.
   - Those abstentions are what the learning loop can reduce. The loop promoted challengers that cut held lines on replay.
4. **Cost per month (months 3-6).**
   - D: Jev $0.040898 per six-month run, measured, about $0.007 a month.
   - B: one subscription call a month. The list-price estimate is $0.34-0.53 a month; this is not a charge (login claude.ai).
   - Treat the ratio, about 50-80x at list price, as an estimate.

## Limits a reader will raise (state them in the write-up)

- **One synthetic corpus,** built by one generator (Codex) and keyed blind by a second session. Real billing data was not used.
- **The person is the answer key,** so reviewer error is out of scope.
- **Arm B is one prompt design,** run 3 times on one model. A different prompt, or tools, could change its blind spot.
- **Arm C ran once** (28 silent). Its structural gap, no record of earlier months' lines, does not depend on the draw; its exact count might.
- **Three runs per arm** show the range, not a distribution. Spending more runs would tighten H3's margin, not its sign: D's held count was above B's in all 9 run pairs.
- **The month 4 recovery assumes the person adds the column map at once.**

## Spend (Jev, D-300) [measured, usage.input_tokens at $0.042/Mtok]

- D r2: $0.040898. D r3: $0.040898. **Replication total: $0.081796.**
- Arm B replicates: 8 subscription calls.
