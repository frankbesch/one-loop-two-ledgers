# Job B blind re-key: label definitions

You key labels for every bill line and every remark, by eye, from the page images. The only other file you may read is `afe_register.json`, the owner's record of approval budgets (AFEs).

## Per line

Write one record per line: `doc_id`, `page`, `line_no`, `property` as printed, `claim_text` (the exact printed words that carry an approval claim, or null), and the labels below.

| Label | Values | Definition |
|---|---|---|
| `claim_type` | `claims_afe` · `claims_other` · `no_claim` | `claims_afe`: the line, or a remark naming it, says the charge is covered by an approved AFE (budget approval), in any wording. `claims_other`: it cites another authority instead. `no_claim`: neither. Approval words inside a name ("Approved-vendor list fee") are not a claim. |
| `reference_kind` | `exact` · `reformatted` · `reworded` · `placeholder` · `unknown_number` · `no_number` · `none` | `exact`: the AFE number as the register prints it. `reformatted`: the same number in a different format (spacing, dashes, leading zeros, case). `reworded`: the number sits inside a sentence, not in the reference column. `placeholder`: a stand-in for a number (N/A, TBD, Pending, To follow, a dash, or any wording that promises a number later). `unknown_number`: a number the register does not hold. `no_number`: a claim with no number and no stand-in; an empty reference column counts here. `none`: no AFE claim. |
| `placeholder_style` | `literal` · `paraphrased` · `n_a` | `literal`: exactly N/A, TBD, Pending, To follow, or a dash. `paraphrased`: any other stand-in wording. `n_a`: not a placeholder. |
| `property_match` | `match` · `mismatch` · `n_a` | Only when the claimed number is in the register as approved: does the register's property equal the line's property? Otherwise `n_a`. |
| `authority_kind` | `emergency` · `service_contract` · `operating_agreement_clause` · `prior_election` · `verbal_or_informal` · `operator_policy` · `other` · `n_a` | Only for `claims_other`; otherwise `n_a`. |
| `outcome` | `supported` · `unsupported` · `contradicted` · `other_authority` · `no_claim` | `supported`: AFE claim, register shows that AFE approved for the line's property. `unsupported`: AFE claim, but placeholder, unknown number, no number, or approved for a different property. `contradicted`: the register shows that AFE declined. `other_authority`: `claims_other`. `no_claim`: no claim. |
| `difficulty` | `plain` · `hard` | `hard`: the claim appears only in a remark that names the line. |

"Unsupported" means the record is missing. It does not mean the charge is false.

## Per remark

One record per remark: `doc_id`, `remark_id` (order on the page, from 1), `names_line` (the line number it names), `text` exactly as printed, and `remark_role`: `claim` (it makes an approval claim about that line) or `no_claim`.

## Output

One JSON file per document: `truth-blind/<doc_id>.json` with `{"doc_id": ..., "lines": [...], "remarks": [...]}`.
Then `truth-blind/REPORT.md`, under 150 words: documents, lines, and remarks keyed; nulls; lines you were unsure of, by id.
Key what is printed. Do not correct anything. Mark a value you cannot decide as `"UNSURE"` and list it in the report.
