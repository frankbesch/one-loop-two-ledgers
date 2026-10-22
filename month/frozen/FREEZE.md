# Step 6 freeze (build order step 4, 2026-10-08)

**Frozen: arm D's model per question, floors, code, format maps, data, and the brief. Months 3-6 run only through this freeze.** `run_month.py --frozen month/frozen/FREEZE.json` re-hashes 20 files and refuses on any change. Without `--frozen` it refuses months 3-6. Both guards were tested, plus a changed-file test.

## Calibration (months 1-2, 420 lines; the key holds 72)

| Run | Calls | Errors | Wall | Spend | Silent | Held | Money caught (right reason) |
|---|---|---|---|---|---|---|---|
| Claude `claude-sonnet-5-5`, subscription | 508 | 0 | 43 min | subscription | 0 | 72 | 48/48 (48) |
| Jev `jev-1.13.0`, Frank's Terminal, D-300 | 508 | 0 | 132 s | **$0.013619** [measured] | 0 | 74 | 48/48 (48) |

## Model per question and floors (`set_floors_m.py`, replay of the logged answers; no new calls)

Policy, fixed before the sweep: the fewest silent lines, then the fewest held, then the highest floors in a tie. F4 (Frank): per question, the cheapest model that passes the calibration marks (at most 2 silent per month, at least 90% of planted dollars caught).

- **All 16 assignments of Claude or Jev to Q2, Q5, Q7, and Q9 pass.**
- **The pick: Jev for every question** (Q6 too, as a note). Floors: Q2 0.75, Q5 0.95, Q6 0.60, Q7 0.95, Q9 0.95. Calibration: 0 silent and 74 held, against 72 held by the key: 2 lines held without need, 1 per month.
- **The trade-off:** Claude on Q2 instead would hold 72, saving 2 reviews over two months at about 22 minutes of subscription per month. F4 picks the cheaper model.
- **The floors are high** (0.95 on Q5, Q7, Q9) by the tie rule. On calibration they cost nothing. If they cost reviews on months 3-6, that is the policy's real cost, reported as found. The learning loop may lower them only under the promotion rule.

## Also frozen

- Format maps: `formats_known.json` (format A at start). `person_maps_B.json` holds what the person adds at the month 4 drift event.
- Promotion rule (Frank, 10-08): automatic when strictly better on every past month.
- Marks: publishing `03-full-month-brief.md` §6.
- Data: `synth-month/frozen-m.json`, `truth_m.json`, `case_spec_m.json`.

## Not run (step 5, Frank's go)

1. **Arm D on months 3-6** (Jev, D-300):
   `run_month.py --months 3 4 5 6 --backend jev --mode live --yes --d283 D-300 --person-maps month/person_maps_B.json --loop --frozen month/frozen/FREEZE.json`
2. **Arms A** (manual proxy), **B** (one agent, cloud credit), **and C** (v1 cascade) need their own runners, still to build.
