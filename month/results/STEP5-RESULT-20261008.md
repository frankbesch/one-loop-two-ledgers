# One Loop step 6, build order step 5: four arms on months 3-6 (2026-10-08)

Scored by `score_month.py` per month and `compare_arms.py` across arms (`STEP5-compare-m3456.json`). Marks: publishing `03-full-month-brief.md` §6 (pre-registered). Arm A/B/C design: publishing `04-arms-abc-as-built.md`.
Months 3-6: 840 lines; the key holds 148 lines, including 96 planted money errors (16 per class) and 56 claim cases.

| Arm | Silent (posted, key holds) | Held for a person | False holds | Money caught | Dollars caught | Claim cases held | Metered spend |
|---|---|---|---|---|---|---|---|
| A, audit at 45% (seeded run) | 87 | 365 | 304 | 34/96 | 38.5% | 27/56 | none |
| A, mean of 2,000 draws per month | 80.8 | 383.0 | | | 43-47% by month | | none |
| B, one agent (`claude-sonnet-5-5`, 4 calls) | 1 | 147 | 0 | 95/96 | 99.8% | 56/56 | subscription |
| C, cascade (Jev, Claude below 0.80) | 28 | 120 | 0 | 68/96 | 81.5% | 56/56 | Jev $0.035388 + subscription |
| D, this architecture (Jev, frozen floors, loop) | **0** | 154 | 6 | **96/96** | **100%** | 56/56 | Jev $0.040906 (months 1-6) |

## Marks for arm D (months 3-6)

- **Silent at most 2 per month: MET.** 0 in each month.
- **At least 90% of planted dollars caught: MET.** 100% in each month.
- **Recovery within one month after the column map: MET.** At the month 4 drift, the first pass held all 210 lines; the documents failed closed. The person added the format B map, and the re-run that month gave 0 silent and 24/24 money.
- **"D lower than B and C at equal or better catch": NOT MET.** D held 154 lines, B 147, and C 120. D's catch beat both: 0 silent against B's 1 and C's 28.

## Per money class (caught/planted)

- A: wrong_decimal 6/16, wrong_rate 6/16, nonconsent 4/16, afe_overrun 6/16, duplicate 6/16, date_window 6/16.
- B: wrong_decimal 15/16; every other class 16/16.
- C: wrong_decimal 14/16, afe_overrun **0/16**, duplicate **6/16**; the other three classes 16/16. These are the classes that need earlier lines, which C does not get, by design.
- D: 16/16 in every class.

## Reading

- **D is the only arm with nothing silent.** B is one silent line from D on catch, and it holds 7 fewer lines.
- **D's extra held lines are claim abstentions.** In month 4, 5 of its 6 false holds are `claim:needs_review`.
- **Cost.**
  - D: Jev, $0.041 for 6 months, 1,524 calls, 5.8 min.
  - B: 4 subscription calls of 36-55 s each, at a list-price estimate of $0.34-0.53 a month. That figure is not a charge: the login is claude.ai.
  - C: Jev $0.035, plus 94 subscription calls in 15 min.
- **C at the 0.80 confidence handoff.** Jev's own confidence was low on whole documents, so 568 of 840 lines (68%) went to Claude. The share rose from 91 lines in month 3 to 153-167 a month in months 4-6, on the new format. The drift shows up in C as more handoffs, not as silent errors.

## Deviations and incidents (logged)

1. **Arm D ran months 1-6, and months 3-6 are scored.** A run starting at month 3 has no ledger, so in the oracle check it missed every cross-month duplicate and AFE overrun (8 in month 3). Months 1-2 were re-run only to carry the ledger.
2. **Two arm D runs collided in one output folder.** One started 20:59:38Z and one 21:01:53Z; the earlier was most likely Frank's paste of the handed-over command. The calls log interleaved and the outcomes were overwritten.
   - The collided folder is kept aside as `runs/month/D-jev-m123456-COLLIDED`, and its scores are void.
   - Arm D was re-run alone; the clean run is the result above.
   - The collided pair cost Jev $0.040873 + $0.040923 [measured].
3. **Jev is not repeatable run to run.** The clean run's loop promoted different floors from the collided run (Q2 0.50, then 0.40, against 0.45). Both runs scored 0 silent on months 3-6.
4. **Arm B ran on the subscription, not cloud credit** (F3: four calls do not justify the cloud setup).

## Spend this step (Jev, D-300) [measured, usage.input_tokens at $0.042/Mtok]

- D clean: $0.040906.
- D collided pair: $0.081796.
- C smoke, month 1: $0.008838.
- C, months 3-6: $0.035388.
- **Total: $0.166928.**

Run folders: `results/A-audit-{0.34,0.45,0.56}-m3456`, `results/B-claude-m3456`, `results/C-smoke-m1`, `results/C-cascade-m3456`, `results/D-jev-m123456`. The loop scratch is excluded; it is 314 MB per run.
