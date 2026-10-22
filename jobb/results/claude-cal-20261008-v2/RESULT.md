# Claude calibration arm v2, job B (2026-10-08): Q2 wording ruled

**Verdict: 207 of 210 lines right; 3 went to a person; no line silently wrong. Q2 is now right on all 210 lines. All three marks pass on the calibration split.** This is a calibration result at the provisional 0.60 floors, not the study result. The scored split stays unseen.

Changes from v1 (`../claude-cal-20261008/`):
- Q2's `afe` option adds: "A labelled AFE field counts, even when its value is a stand-in such as N/A, TBD, or a promise to supply the number later." (Frank, 10-08)
- The evidence line now says a claim without a number is its own evidence.
- Commits: `acd5b20`, plus the prompt fix `854e8ec`. The 15:40 rerun in between is void (`../claude-cal-20261008-void/`).

Arm: `claude-sonnet-5-5`, `claude -p` 2.1.294, subscription. Calibration split, standard vocabulary, floors 0.60. 514 calls, 0 errors, 46 min (5.4 s per call). Envelope costs are list-price estimates under claude.ai auth, not charges.

## v1 against v2

| | v1 | v2 |
|---|---|---|
| Lines right | 195 | **207** |
| Routed to a person (needs_review) | 15 | **3** |
| Silently wrong | 0 | 0 |
| Q2 right when answered (line) | 198/203, 7 at needs_review | **210/210**, 0 at needs_review |
| M1 silent misses (99 targets) | 0 | 0 |
| M2 false alarms (45 supported) | 1 (2.2%) | 2 (4.4%), both routed |
| M3 value over code (75 targets) | 65 right (86.7%) | **74 right (98.7%)** |

All 13 labelled-placeholder lines that v1 routed are now right.

## The 3 lines still routed

1. **`cal_jib_03:1` and `cal_jib_12:1`.** Q7 answered `no_reference` but quoted "no evidence in text", so Q17 routed them. Both were right in v1, or routed for another reason, so this is run-to-run variation on Q7's evidence. On `cal_jib_12:1`, a supported reworded line, `no_reference` was also the wrong answer, and Q17 caught it.
2. **`cal_jib_13:3`.** The remark's Q2 answer was `afe` at 0.55, under the 0.60 floor. It was right in v1. This is noise at the floor.

## Noise note

Two lines that v1 got right went to review in v2. Repeat runs vary near the floor and on the evidence phrasing. Step 3 should set floors with that variation in view; a second Claude repeat would measure it.

## Next

- **Jev A1 and A2** per `../../LABEL-SWAP-PREREG.md`, metered, from Frank's Terminal. The Q2 wording change applies to Jev as well.
- **Step 3.** Read `TRACES.md`, set per-question floors from the calibration split, freeze, and only then run the scored split.
