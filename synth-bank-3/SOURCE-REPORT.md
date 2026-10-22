# SOURCE-REPORT: quarterly compliance certificates (step 7d)

## Outputs
- `sources/<cert_id>.html` for all 48 certificates (12 per quarter): portrait US Letter, plain serif style.
- `truth_q.json`: 395 units. They are copied verbatim from the spec, and each one carries cert_id, quarter, borrower_id, every field and every label.
- `reference/agreements.json`, `reference/categories.json`, `reference/prior_cures_q1..q4.json`. These hold no labels.
- `manifest_q.json`: the spec SHA-256 plus each source's SHA-256. `--render-only` refuses to render a source that has changed since the manifest was written.
- `build_q.py` (`--source-only` / `--render-only`) and `check_q.py` (the gate).

## Deviations from the spec
None. Every value is printed as the spec gives it. Money is printed as `$` plus whole dollars with thousands separators. Ratios and thresholds use two decimals followed by "x". Status is printed "Pass" or "Fail". No addback, statement or section was added or dropped.

Interpretation (not a deviation): the spec's `prior_cures` list also contains 2025 entries, and those entries match the printed cures exactly. The reference files take only the pre-2025 entries from the spec and then add the cures printed in quarters before k. A Q1 file built from the whole spec list would have leaked cures from later quarters.

## Gate results (`python3 check_q.py`, exit 0)
- G1 PASS: quotas recounted per quarter. This covers the error classes, the 4 cap lines in 4 certificates, both hidden_breach mechanisms, both cure_invalid mechanisms, the benign cases, the volumes, the reference rules and the stress-amendment anchor rules. The recount also matches the spec's `quota_check`.
- G2 PASS · G3 PASS · G4 PASS · G7 PASS
- G5, G6 SKIPPED: `clean/` is empty. The G6 heading-order check passes on the HTML sources.

I mutation-tested the gate on a scratch copy by flipping a label, dropping a field, changing a printed amount and truncating the prior-cure history. Each mutation made the gate fail.

## UNVERIFIED
- PDF rendering: G5 text matching, G6 heading order in the PDF text, and the 1-2 page / portrait checks. These run once `build_q.py --render-only` has been run.
- The judgment labels `category_true` and `realized`, the anchor wording requirement ("hard to classify", no shared construction) and "the cap line is plainly worded" were taken from the spec and not re-judged.
- `permitted_approval_or_one_time` is counted with a keyword heuristic (`approv` or `one-time`).
- Ten deliveries fall on the due date or one day before it. They are on time under "delivered after the due date".
