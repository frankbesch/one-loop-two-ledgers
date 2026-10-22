# Source report

Deviations from case_spec_b.json: none.

Built 3 documents, 24 lines, and 8 remarks.
Amounts use decimal multiplication, ROUND_HALF_EVEN to cents, and sums of printed line amounts.
Page style derives from the run-1 HTML template; no run-1 entity names are copied.
No scan set was created (D-286).

## Gate results

- G1: PASS
- G2: PASS
- G3: PASS
- G4: PASS
- G5: PASS
- G6: PASS
- G7: PASS
- G8: PASS — remark targets and rendered row containment verified.
- G9: PASS

## Quotas by split

- smoke: supported, exact: 1 / minimum 1
- smoke: supported, reformatted or reworded: 2 / minimum 1
- smoke: unsupported, placeholder (literal): 1 / minimum 1
- smoke: unsupported, placeholder (paraphrased): 10 / minimum 1
- smoke: unsupported, unknown number: 1 / minimum 1
- smoke: unsupported, no number: 1 / minimum 1
- smoke: unsupported, wrong property: 1 / minimum 1
- smoke: contradicted: 1 / minimum 1
- smoke: other_authority: 2 / minimum 2
- smoke: no_claim, ordinary: 3 / minimum 3
- smoke: no_claim, bait: 1 / minimum 1
- smoke: hard (claim only in a remark): 5 / minimum 1
- smoke: remarks that name a line and claim nothing: 3 / minimum 1

## UNVERIFIED

Visual appearance remains UNVERIFIED; text extraction does not replace visual inspection.

Next action: run `python3 build_b.py --render-only`; it runs `check_b.py` after rendering.
