# Job B: data build and line runner

Study: publishing `one-loop-two-ledgers/` (brief §12). Question set: `02-question-set.md` there.
Data: `../synth-jobb/` (frozen; calibration 210 lines, scored 216) and `../synth-jobb-smoke/` (24 lines).

## Files

| File | Role |
|---|---|
| `run_jobb.py`, `rebuild_scored.py` | Data build: four Codex sessions, then the scored-split rebuild |
| `check_spec.py`, `check_overlap.py` | Independent spec checks: quotas, register, wording overlap between splits |
| `units.py` | One unit per bill line from the rendered PDF: cells from word boxes, remarks joined by line number. `--check` compares every cell with the key. |
| `codelayer.py` | Code-owned questions: Q8, the Q9 token lister, Q10, Q11, Q14, Q16 rows, Q17 evidence check, the code-only arm |
| `questions.py` | Model questions Q2, Q6, Q7, Q9; the Claude prompt; the Jev body (answer plus evidence-span choice); the floor decision; the label-swap vocabulary |
| `run_b.py` | The line runner: backends oracle, claude, jev; dry-run or live |
| `score_b.py` | Marks M1-M3, per-question accuracy, review load, cost; `--compare` gives the label-swap reading |
| `q_replay.py` | Q16 replay from the key alone (no PDF), used during the build |
| `LABEL-SWAP-PREREG.md` | D-295 test, reading fixed before any live call |

## Evidence (Q17) per backend

Claude quotes the unit verbatim, or writes `no evidence in text`. Jev cannot write text. Each Jev request therefore asks a second, independent choice on the same state: which code-cut span of the unit carries the answer, or none. Code then checks that the picked span agrees with the answer.

## Verified 2026-10-08

- `units.py --check`: PASS on both corpora (450 lines, 100 remarks equal to the key).
- Oracle through the whole path (PDF units, Q17, Q16): smoke 24/24, calibration 210/210, scored 216/216. All three marks have at least 45 targets per split. This proves the harness, not a model.
- Dry runs, calibration: 516 requests per arm. Jev bound $0.0265 per arm, about $0.009 expected. Claude about 36 minutes at 4.2 s per call.
- Live Claude check (subscription, `claude-sonnet-5-5`, CLI 2.1.294, 3 smoke lines, 8 calls): pinned model served, envelopes parsed. It found one rule fix: Q7 `no_reference` now quotes the claim that lacks a number. After the fix, 2 lines were right; line 1 went to `needs_review` (Q7 at 0.55, under the 0.60 floor).

## Order for step 3 (calibration)

1. **Jev A1, standard vocabulary, calibration split.** Metered: Frank runs it under a D-283 case. It sizes the Claude budget and serves as the label-swap baseline.
2. **Jev A2, alternate vocabulary.** Read it with the pre-registration. A 20-point move on any question triggers a rebuild.
3. **Claude arm, calibration split.** Subscription, daytime, `--model` pinned, about 36 minutes.
4. **A person reads about 10 traces per arm**, then sets per-question floors in a floors file from the calibration split only. Freeze the questions, floors, marks, and hashes.
5. **Scored split**, each arm once, with the frozen floors.
