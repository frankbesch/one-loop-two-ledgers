# Step 6 blind re-key: label definitions

You key labels for every bill line and every remark, by eye, from the page images. The only other files you may read are the reference files in `reference/`: property master (`properties.json`: each property's number and its one official name), division order (`doi.json`), contract rates (`contract_rates.json`), AFE register (`afe_register.json`), elections (`elections.json`), JOA terms (`joa_terms.json`), and the owner's earlier ledger (`prior_ledger.json`, the lines already billed in earlier months).

## Per line

One record per line: `doc_id`, `month`, `page`, `line_no`, `property_printed`, `property_no` (the owner's property this line belongs to: the printed number, or the printed name matched to `properties.json`, allowing for spelling and format variants), `claim_text` (the exact words carrying an approval claim, or null), and these labels:

| Label | Values | Definition |
|---|---|---|
| `money_error` | `none` · `wrong_decimal` · `wrong_rate` · `nonconsent_property` · `afe_overrun` · `duplicate` · `date_window` | Use the reference in force on the line's service date. `wrong_decimal`: the printed owner decimal differs from the division order (`doi.json`). `wrong_rate`: a rate-billed line's unit rate differs from the contract rate for that vendor and service (`contract_rates.json`). `nonconsent_property`: the owner elected non-consent on the line's property before the service date (`elections.json`). `afe_overrun`: the line's cumulative gross billed to its AFE, in billing order across months (earlier months in the prior ledger), passes the approved amount times (1 + the tolerance in `joa_terms.json`). `duplicate`: the same vendor invoice number and gross were billed on an earlier line, in this month or the prior ledger; the later line carries the label. `date_window`: the service date is after the billing month's end, or more than the window in `joa_terms.json` before it. At most one per line. |
| `error_dollars` | number, or 0 | The owner's net overcharge |
| `claim_type` | `claims_afe` · `claims_other` · `no_claim` | `claims_afe`: the line, or a remark naming it, says the charge is covered by an approved AFE (budget approval), in any wording; a labelled AFE field counts even when its value is a stand-in. `claims_other`: it cites another authority instead. `no_claim`: neither. Approval words inside a name ("Approved-vendor list fee") are not a claim. |
| `reference_kind` | `exact` · `reformatted` · `reworded` · `placeholder` · `unknown_number` · `no_number` · `none` | `exact`: the AFE number as the register prints it. `reformatted`: the same number in a different format (spacing, separators, zero padding, case, or the month's display format). `reworded`: the number sits inside a sentence. `placeholder`: a stand-in for a number (N/A, TBD, Pending, To follow, a dash, or wording that promises a number later). `unknown_number`: a number the register does not hold. `no_number`: a claim with no number and no stand-in; an empty reference counts here. `none`: no AFE claim. |
| `placeholder_style` | `literal` · `paraphrased` · `n_a` | `literal`: exactly N/A, TBD, Pending, To follow, or a dash. `paraphrased`: any other stand-in wording. `n_a`: not a placeholder. |
| `property_match` | `match` · `mismatch` · `n_a` | Only when the claimed number is in the register as approved: does its property equal the line's property? Otherwise `n_a`. |
| `authority_kind` | `emergency` · `service_contract` · `operating_agreement_clause` · `prior_election` · `verbal_or_informal` · `operator_policy` · `other` · `n_a` | Only for `claims_other`; otherwise `n_a`. |
| `outcome` | `supported` · `unsupported` · `contradicted` · `other_authority` · `no_claim` | `supported`: AFE claim, register shows it approved for the line's property. `unsupported`: AFE claim with a placeholder, an unknown number, no number, or an approved AFE for another property. `contradicted`: the register shows it declined. `other_authority`: `claims_other`. `no_claim`: no claim. "Unsupported" means the record is missing, not that the charge is false. |
| `difficulty` | `plain` · `hard` | `hard`: the claim appears only in a remark that names the line. |
| `property_print` | `exact` · `variant` | Whether the printed property is exactly a property number or official name from `properties.json` |
| `disposition` | `post` · `hold` | `hold` when `money_error` is not `none` or `outcome` is `unsupported`, `contradicted`, or `other_authority` |

## Per remark

`doc_id`, `remark_id` (reading order in the document, from 1), `names_line`, `text` exactly as printed, `remark_role` (`claim` or `no_claim`).

## Output

One JSON file per document: `truth-blind/<doc_id>.json` with `{"doc_id": ..., "lines": [...], "remarks": [...]}`. Then `truth-blind/REPORT.md` (under 150 words): documents, lines, remarks, and the lines you were unsure of. Mark an undecidable value `"UNSURE"`.
