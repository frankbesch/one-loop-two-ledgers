# Claude calibration arm, job B (2026-10-08)

**Verdict: no line silently wrong. 195 of 210 lines right; the other 15 went to a person. All three marks pass on the calibration split.** This is a calibration result at the provisional 0.60 floors, not the study result. The scored split stays unseen.

Arm: `claude-sonnet-5-5` via `claude -p` 2.1.294, auth claude.ai (subscription). Standard vocabulary, calibration split, floors 0.60. 507 calls, 0 errors. Wall 48.8 min (5.8 s per call, against the 4.2 s planned). Runner `jobb/run_b.py`; this folder holds its outputs.
Cost: subscription usage. The envelopes' `total_cost_usd` values are list-price estimates under claude.ai auth, not charges, so no dollar figure is given here.

## Marks (at least 15 targets each)

| Mark | Targets | Result | Rule | Verdict |
|---|---|---|---|---|
| M1 silent misses (unsupported or contradicted ending supported or no_claim) | 99 | 0 | at most 2 | PASS |
| M2 false alarms on supported lines | 45 | 1 (2.2%), routed to review | at most 10% | PASS |
| M3 value over code (lines code alone gets wrong) | 75 | 65 right (86.7%); all 75 right or routed | at least 80% right | PASS |

Outcomes: contradicted 18/18, other_authority 18/18, no_claim 48/48, supported 44/45 (1 to review), unsupported 67/81 (14 to review). Sent to a person: 118 lines, which are every flag plus review.

## Per question

| Question | Asked | needs_review | Q17 fails | Right when answered |
|---|---|---|---|---|
| Q2 (line) | 210 | 7 | 5 | 198/203 |
| Q6 | 18 | 0 | 0 | 18/18 |
| Q7 | 129 | 1 | 1 | 128/128 |
| Q9 | 102 | 0 | 1 | (scored through outcomes) |

## Trace findings (TRACES.md and the full review list), before any floor is set

1. **A labelled AFE field with a placeholder is the main gap (13 of 15 reviews).** In "Approved AFE: N/A", "Approved AFE: TBD", or "Approved AFE: Budget reference is reserved for later completion", Claude splits between `no_claim` and low confidence. The key counts these lines as AFE claims with a stand-in, so they are unsupported. Q2's option text never says whether an empty labelled AFE field is a claim.
   - Q17 caught five of them: `no_claim` answers that quoted the placeholder span failed the check and were routed instead of being silently wrong.
   - Proposed Q2 wording, for Frank to rule on before the floors freeze, added to `afe`: "A labelled AFE field counts, even when its value is a stand-in such as N/A, TBD, or a promise to supply the number later."
2. **Q7 evidence wording (1 review).** One `no_reference` answer still quoted "no evidence in text", under the old rule. Proposed fix to the prompt line: the quote is the claim that lacks a number.
3. **Q9 (1 review).** One `none_of_these` answer quoted a span holding the register number (`cal_jib_12:1`). Q17 routed it.
4. **Q7 floor (no effect on the outcome).** One `number_given` answer at 0.58, just under 0.60 (`cal_jib_17:7`). The Q9 token still decided the line correctly, because rows 8-13 use Q9 before Q7. Calibration sets that floor.

## Not yet run

- **Jev A1 and A2** (metered; D-283 case; Frank's Terminal) per `LABEL-SWAP-PREREG.md`.
- **Floors and freeze.** Step 3 sets per-question floors from calibration and freezes them after Frank rules on the Q2 wording above. Changing the wording means re-running the calibration arms.
