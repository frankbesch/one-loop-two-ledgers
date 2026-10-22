# Source report

Deviations from case_spec_b.json: None detected.

## Build gate

- G1: PASS.
- G2: PASS.
- G3: PASS.
- G4: PASS.
- G5: PASS.
- G6: PASS.
- G7: PASS.
- G8: PASS.
- G9: PASS.

## Quotas per split

| Quota | Minimum | Calibration | Scored |
|---|---:|---:|---:|
| supported_exact | 20 | 21 | 24 |
| supported_reformatted_or_reworded | 20 | 24 | 24 |
| supported_reworded | 10 | 12 | 12 |
| unsupported_placeholder | 20 | 24 | 24 |
| unsupported_placeholder_paraphrased | 10 | 12 | 12 |
| unsupported_unknown_number | 20 | 21 | 24 |
| unsupported_no_number | 15 | 18 | 18 |
| unsupported_wrong_property | 15 | 18 | 18 |
| contradicted | 15 | 18 | 18 |
| other_authority | 15 | 18 | 18 |
| other_authority_kinds | 5 | 6 | 6 |
| no_claim_ordinary | 30 | 33 | 30 |
| no_claim_bait | 15 | 15 | 18 |
| hard | 15 | 24 | 20 |
| remarks_no_claim | 15 | 24 | 24 |
| value_over_code | 20 | 56 | 58 |

calibration authority kinds: emergency=3, operating_agreement_clause=3, operator_policy=3, prior_election=3, service_contract=3, verbal_or_informal=3.

scored authority kinds: emergency=3, operating_agreement_clause=3, operator_policy=3, prior_election=3, service_contract=3, verbal_or_informal=3.

## Verification limits

- Amounts round half-up to cents per line; totals sum rounded line amounts.
- Sources use the reference page style, with wrapped cells and explicit spec page boundaries.
- No scan set was generated (D-286).
- PDF visual appearance remains UNVERIFIED; this gate checks text and geometry, not visual rendering.
