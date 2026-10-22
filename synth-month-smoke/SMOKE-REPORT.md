# Step 6 smoke run (2026-10-08)

**Verdict: PASS with prompt fixes, applied to the brief before the full build.** Five documents (month 1, format A; one month 4 document, format B), 40 lines, 7 remarks. Codex on the subscription only; no metered call.

| Check | Result |
|---|---|
| Designer, first try | Stopped and asked: the prompt assumed six months and the splits, named four reference changes, and pointed to job B definitions that were missing. Fixed; second try PASS (198 s). |
| Independent spec check (`month/check_spec_m.py`): every money label recomputed from the reference in force | ALL PASS, after making the checker format-aware (below) |
| Generator gates G2-G8 after render | PASS: G5 claim text read from word boxes; G6 format headers. Chrome polling and header detection held on the first render. |
| Generator G1 | FAIL by prompt: "every month" against corpus-wide smoke quotas. Prompt fixed. |
| Blind re-key, first try | 29 UNSURE: no property master, and the money definitions pointed to a quota table the keyer never sees. Fixed. |
| Blind re-key, second try, against the generator key | 0 differences on money_error, error_dollars, property_no, the job B labels, and disposition, over all 40 lines |
| Adjudicator | 26 field differences, 0 unresolved: 22 property_print values the keyer marked UNSURE (definition fixed), 4 claim spans with the "Line N:" lead-in |
| Freeze | 17 files hashed |

## Findings that shape the full build and the month runner

1. **AFE display drift is real and breaks job B's code.** Format A prints `CE08425~K` and format B prints `K::08425::CE`. The `~` and `::` separators, and the letter groups reversing order, defeat job B's tokenizer and normalizer. The month runner needs a per-operator-format AFE map (flow step 5) and the drift monitor. My checker uses an order-free matcher meant for checking only.
2. **The owner needs a property master** (`properties.json`: number and official name). Name variants still need resolving by the linking question.
3. Money prints with two decimals (prompt fixed).
4. Prompts are now mode-neutral (per month or corpus-wide, months from the composition).
