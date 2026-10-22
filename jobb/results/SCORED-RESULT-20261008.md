# Job B scored result (2026-10-08): the study result for job B

**Both architectures pass every mark on the held-out split. Neither sends any line through silently wrong. Claude with code gets 210 of 216 lines right and sends 6 to a person; Jev with code gets 195 right and sends 21. Code alone gets 142 right.** Both runs used the freeze `frozen/FREEZE.json` (private source `a219f7c`), with floors and rules fixed on calibration only. No model and no sweep had seen the scored split before these runs.

Data: `synth-jobb` scored split, 216 lines in 24 documents. Synthetic, with a blind second key (0 unresolved). Calibration wording overlap is 0%. The truth hash `15778a60212a` matches every arm.

## Marks (frozen 10-08; at least 15 targets each)

| Mark | Targets | Claude + code | Jev + code | Rule |
|---|---|---|---|---|
| M1 silent misses (unsupported or contradicted ending supported or no_claim) | 102 | **0**, PASS | **0**, PASS | at most 2 |
| M2 false alarms on supported lines | 48 | **0 (0.0%)**, PASS | 1 (2.1%), PASS | at most 10% |
| M3 value over code (lines the code-only arm gets wrong) | 74 | **72 (97.3%)**, PASS | 69 (93.2%), PASS | at least 80% right |

## Lines

| | Claude + code | Jev + code | Code only |
|---|---|---|---|
| Right | **210**/216 (97.2%) | 195/216 (90.3%) | 142/216 (65.7%) |
| To a person (needs_review) | 6 | 21 | none; code never abstains |
| Silently wrong | 0 | 0 | 74 lines wrong |
| All lines sent to a person (every flag plus review) | 123 | 130 | n/a |

The code-only figure is 216 lines minus its 74 errors, the M3 targets.

## Run cost and time

| | Claude | Jev |
|---|---|---|
| Model | `claude-sonnet-5-5`, CLI 2.1.294 | `jev-1.13.0` |
| Calls | 526 | 525 |
| Wall | 45.5 min (5.2 s per call) | 99 s |
| Spend | subscription (envelope costs are list-price estimates, not charges) | **$0.013485** [measured; `usage.input_tokens` at $0.042/Mtok] |
| Transport errors | 1 timeout at 60 s (`sco_jib_15:7`, failed closed to review) | 1 HTTP 529 overload (`sco_inv_06:7`, failed closed to review) |

## Where each sends a line to a person

- **Claude (6).** 2 placeholder lines with new wording ("A separate reconciliation memo will identify the AFE…", "Charge the approved AFE; the records clerk must still fill in…"), where Q7 and Q9 disagreed. 1 labelled stand-in ("AFE consent locator: -") where Q2 was unsure. 2 bait lines under the floor. 1 timeout.
- **Jev (21).**
  - 9 bait lines, where Jev was unsure whether "approved" language is a claim.
  - 10 placeholders under the scored split's new labels.
  - 1 HTTP 529.
  - The cross-check row (`code_model_conflict`, added 10-08) caught 2 labelled stand-ins on which Jev answered `no_claim` (`sco_inv_03:7`, `sco_inv_05:4`). Without that row, both would have been silent misses, and Jev's M1 would read 2, still a pass at the limit.

## What this supports, and what it does not

- **Supported.** On synthetic partner-bill lines, small typed questions plus code rules flag unsupported approval claims with no silent misses, for both models. The model adds most where code is weakest: 74 lines code alone gets wrong; Claude + code gets 72 of them right, and Jev + code 69.
- **Supported.** The architecture fails closed. Every model doubt, failed quote, transport error, and code-model conflict became a person's review, never a silent pass.
- **Not supported.** Any claim about real operator bills. The data is synthetic, single-period, clean renderings, with one operator's format.
- **Not supported.** A ranking claim with confidence intervals: this is one run per model. Claude varied run to run on calibration.
- **Limit.** The runner does not retry HTTP 429/529 (it is frozen). One Jev line went to review on a transport error, not on its answer. A retry belongs in the next runner version, recorded as a deviation.

Folders: `claude-scored-20261008/`, `jev-scored-20261008/` (each with `score.json`, `outcomes.json`, `calls.jsonl`, `TRACES.md`).
