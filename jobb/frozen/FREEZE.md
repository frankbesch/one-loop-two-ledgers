# Job B freeze (step 3, 2026-10-08)

**Frozen: questions, decision rows, floors per backend, marks, models, data, and code. The scored split now runs only through this freeze.** Ruling: Frank in chat, "set the floors and freeze". Manifest: `FREEZE.json`, with SHA-256 of 17 files. `run_b.py --frozen frozen/FREEZE.json` re-hashes every file and refuses on any change. It also refuses a Claude model other than the frozen one, and refuses `--split scored` without `--frozen`. All three guards were tested.

## Floors (from the calibration split only, no new calls)

`set_floors.py` re-decided every logged calibration answer on a grid of 0.40 to 0.95 (step 0.05) for Q2, Q7, and Q9. It then re-applied Q17 and Q16 and compared outcomes with the key. Q6 is a note to the person and never changes an outcome, so it keeps the 0.60 prior.

Policy, stated before the sweep:
1. fewest lines wrong and not routed;
2. then fewest lines at needs_review;
3. then the highest floors in the tie (the most conservative choice).

| Backend (source run) | Q2 | Q6 | Q7 | Q9 | Wrong, not routed | Routed (at 0.60 prior) | Tie band |
|---|---|---|---|---|---|---|---|
| Claude `claude-sonnet-5-5` (`claude-cal-20261008-v2-xcheck`) | 0.60 | 0.60 | **0.80** | **0.80** | 0 | 2 (3) | Q2 0.40–0.60, Q7 0.70–0.80, Q9 0.40–0.80 |
| Jev `jev-1.13.0` (`jev-cal-20261008-standard-xcheck`) | 0.60 | 0.60 | 0.60 | 0.60 | 0 | 7 (7) | Q2 0.55–0.60, Q7 0.40–0.60, Q9 0.40–0.60 |

Why Claude's Q7 floor rises: two Q7 answers of `no_reference` quoted "no evidence in text" and failed Q17. At 0.80 the less confident one (0.68) becomes `needs_review`, so Q17 does not fail it. The line's correct Q9 token then decides it (`cal_jib_12:1`). Raising Q9 to 0.80 changes nothing on calibration and was chosen by the conservative tie rule.

## Frozen elsewhere

- **Questions and rows.** Publishing `one-loop-two-ledgers/02-question-set.md` (hash in the manifest). It covers the Q2 wording, widened Q8, row 5a `code_model_conflict`, and the Q17 Jev rule, all ruled on 10-08.
- **Marks.**
  - M1: at most 2 silent misses per set.
  - M2: at most 10% false alarms on supported lines.
  - M3: at least 80% right on the lines code alone gets wrong.
  - Each mark needs at least 15 targets, else INCONCLUSIVE.
- **Data.** `synth-jobb/frozen-b.json`, `truth_b.json`, `reference/afe_register.json`.
- **Models.** `claude-sonnet-5-5` (CLI 2.1.294 at freeze) and `jev-1.13.0`. Standard vocabulary for the result. The alternate-vocabulary arm is a robustness check only.

## Limits stated at the freeze

- Floors come from one calibration run per backend. Claude varied run to run: two lines that the first run got right went to review in v2. A held-out result near a floor may move on a repeat.
- Claude's Q7 and Q9 floors (0.80) sit at the top of their tie bands, by the conservative rule; on calibration they cost nothing. If they cost reviews on the scored split, that is a real cost of the policy, reported as found.
- The scored split has never been seen by any model or by this sweep.

## Scored runs (the study result)

| Arm | Command (from the repo root) | Cost |
|---|---|---|
| Claude, subscription, daytime | `python3 jobb/run_b.py --split scored --backend claude --mode live --model claude-sonnet-5-5 --frozen jobb/frozen/FREEZE.json` | about 50 min |
| Jev, metered, Frank's Terminal | `python3 jobb/run_b.py --split scored --backend jev --mode live --yes --d283 <case label> --max-spend 0.05 --frozen jobb/frozen/FREEZE.json` | 526 requests; bound $0.029, about $0.014 expected |

Score: `python3 jobb/score_b.py <run dir>`.
