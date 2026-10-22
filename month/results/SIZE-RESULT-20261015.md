# Packet-size test: result (2026-10-15)

Pre-registration: publishing `one-loop-two-ledgers/18-packet-size-preregistration.md` v2 (publishing e37f0e2), frozen in `frozen/FREEZE-SIZE.json` (138 files, 2026-10-14T22:57Z) before any run. Harness: private source 6bb980e. Runs: 2026-10-14 23:00 to 2026-10-15 00:42 UTC, driver log `results/SIZE-driver-20261014T230047Z.log`. Scorer: `score_size.py` -> `results/SIZE-summary.json`. Independent recount: see "Recount" below.

## Bottom line

- **On identical targets, packet size did not order the misses: 0 silent errors on the 23 primary targets at every size, in all 15 counted run-sets (H45 FAIL as pre-registered).** The 95% Wilson interval on the primary rate is 0 to 3.2% at each of d6, d12, d24 (0 of 115 target-runs each).
- **The only planted-error misses were the known line, at full size only:** `m3_jib_12` line 1 (owner decimal 0.1125 printed, 0.0875 in force, $38.18) posted silently in 2 of 5 full-size runs (r2, r4) and was held in the other 3. Both misses are category (a) misreads: the worksheet's printed-decimal cell holds 0.0875, the in-force value, and no calculator call carries this line's gross (1527.11) or its decimal pair. That is the 10-08 mechanism again (H48 PASS). The line is in the full-size packet only by the seeded draw, so its own size dependence was not tested.
- One further whole-packet silent item at full size (r5): `m6_jib_07` line 3, a claim hold (unsupported AFE claim), not a planted money error. No silent item at d3, d6, or d12 in any run.
- H46 PASS (d6: 0 silent in 5 of 5). H47 PASS (d24: 1 silent in 3 of 5). H49 PASS (worksheet identity coverage exact in every run at every claim size).
- 20 of 20 run-sets complete, none void, none incomplete, none invalid; every month-evaluation took 1 attempt; served model `claude-sonnet-5-5` on every call; calculator connected on every call.

## Table (counted run-sets, rounds 1-5; whole packet unless marked)

| Size | Lines (m3-6) | Prompt chars per month | Silent per run | Held per run | False holds | Planted caught (of) | Silent on P (23) | Silent on D (8) | Calc calls per 100 lines (calc log) | Wall s per run-set |
|---|---|---|---|---|---|---|---|---|---|---|
| d3 | 105 | 101,225-172,617 | 0,0,0,0,0 | 14 x5 | 0 | 12/12 x5 | 0 (of 10 present) | 0 | 30.5-74.3 | 116-145 |
| d6 | 210 | 114,892-184,242 | 0,0,0,0,0 | 31 x5 | 0 | 24/24 x5 | 0,0,0,0,0 | 0 | 13.3-66.2 | 194-236 |
| d12 | 417 | 141,309-207,518 | 0,0,0,0,0 | 71 x5 | 0 | 49/49 x5 | 0,0,0,0,0 | 0 | 11.3-15.1 | 355-375 |
| d24 | 840 | 195,980-255,353 | 0,1,0,1,1 | 148,148,148,147,149 | 0,1,0,0,2 | 96,95,96,95,96 /96 | 0,0,0,0,0 | 0 | 5.0-9.5 | 484-552 |

Worst run on P: 0 at d6, d12, d24. H45 needs S(d6) <= S(d12) <= S(d24) with a strict step: no step, FAIL.

Calculator calls are counted from the per-attempt calculator logs (`calc-m<k>-a1.jsonl` lines), not from the stream envelope's `tool_uses`, which double counts re-emitted messages in 3 of 80 months (d6-r4 m3, d6-r5 m4, d24-r1 m4); `SIZE-summary.json` carries the envelope figure. Prompt characters run 110 higher than the pre-registration's section 1 dumps because the outside-packet header was reworded before the freeze (the d24 prompt is unchanged and sha-matches 10-08).

## Claims

| # | Pre-registered | Result |
|---|---|---|
| H45 | Worst-run silent on P non-decreasing d6 -> d12 -> d24, one strict step | **FAIL**: 0, 0, 0 |
| H46 | d6: 0 silent on the whole packet in 5 of 5 | **PASS** |
| H47 | d24: at least 1 silent in at least 1 of 5 | **PASS**: 3 of 5 |
| H48 | every silent planted money error is (a) misread or (b) missing row | **PASS**: 2 items, both (a); `packets/h48-adjudication.json` |
| H49 | worksheet keys equal the packet line set in every counted run | **PASS** |

## What the test says

- On the same 23 lines, surrounded by 52, 104, or 210 lines of review, the single agent missed nothing in 15 runs. Size showed no effect at this power on these targets (pre-registration section 1, flat case). A flat result does not show that the misread is item-specific.
- The miss it does make is one line, one mechanism (writing the expected value in the printed cell): 1 of 3 for this design on 10-08 (c3), 2 of 5 now; 5 of 9 across the three 10-08 single-agent designs, with the printed-cell mechanism logged in the 2 worksheet-design misses. The write-up's finding 1 stands; its finding 4 hypothesis (misses grow with packet size) is dropped.
- Descriptive outputs, no claim: calculator calls per 100 lines fall from 30-74 at d3 to 5-10 at d24, and held counts stay exactly at the key's count at d3-d12 (no false holds in 15 runs) while d24 shows 0-2 false holds. Per-line tool use thins as the packet grows, without producing misses on the shared targets.

## Deviations and voids

- Before the first counted run, 11 run-set folders (rounds 1-2, and round 3 through d24) voided in 20-67 ms each with 0 input tokens: the terminal CLI's OAuth session had expired. No model answer was produced, so no result was observed or selected on. Those folders are kept under `results/SIZE-VOID-AUTH-20261014T2258/` and the round numbering restarted at 1 after Frank re-logged in (`claude auth login`). Logged as a post-freeze deviation in the pre-registration.
- No other deviation. No run-set was repeated.

## Limits

- One corpus, one operator format, synthetic data; the ledger-style cut shows outside-packet lines as compact rows (pre-registration section 2), so the test speaks to review-workload size, not to prompt length alone (prompt length varied about 2x; lines 8x).
- The only line the agent ever misses is in d24 only by the seeded draw; a draw that placed it in d6 would have tested its size dependence directly. That is a follow-up, not a reanalysis.
- Five runs per size bound the primary rate at 3.2% per target-run; a smaller true effect is not excluded.

## Recount

An independent recount by a second model family (Codex, read-only, from truth, packets, targets, and the run folders only; by its own statement it read no scorer) reproduced every figure above: 20 run-sets, 3 silent items in all (d24 r2 and r4 `m3_jib_12` line 1; d24 r5 `m6_jib_07` line 3), 0 silent on P and D at every size, worst run on P = 0 at d3, d6, d12, d24, 80 of 80 month-evaluations served exactly `claude-sonnet-5-5` in 1 attempt, 7,860 worksheet rows and 7,860 outcome rows matching the packet line sets with no missing, extra, duplicate, or unparsed keys, no VOID.txt, no failed-closed month. Its classification of the two decimal-line misses is (a) in both, from the same worksheet rows. Report and its command: `results/SIZE-RECOUNT-codex-20261015.md`. One note from the recount: the agent's exception on that line reports `dollars_at_stake` 171.80 (owner net at the printed decimal) where the key's `error_dollars` is 38.18 (the difference); the scorer does not use the agent's dollar field.

## Spend

Subscription, no key, no metered spend. 80 month-evaluations, 80 attempts; the envelopes' `total_cost_usd` sum to $19.22 at list price (an estimate, not a charge; auth method claude.ai, `meta.json` `claude_auth_method`).
