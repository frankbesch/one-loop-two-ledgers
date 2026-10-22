# Source report

No lines, remarks, values, entities, or page assignments were changed from case_spec_m.json.
Sources use landscape Letter pages and the local reference page style.
No scan set was generated. Chrome rendering was not run during source authoring.

## Gate results

- G1: FAIL
- G2: PASS
- G3: PASS
- G4: PASS
- G5: PASS
- G6: PASS
- G7: PASS
- G8: PASS

## Deviations and conflicts

Corpus content deviations: none.
The current instruction requires quotas in every month. quotas-m.md:3 instead applies them across the smoke corpus; that line is set aside.
The checker follows the current instruction and recounts spec labels independently of quota_check.
Corpus-wide smoke quotas: PASS; monthly results appear above.
AFE spending accumulates in spec billing order, using the reference effective on each service date.
Prior ledgers 5 and 6 contain all specified lines because the spec ends at month 4.

- G1: Month 1: unmet monthly quotas: format_B_document.
- G1: Month 2: unmet monthly quotas: wrong_decimal, wrong_rate, nonconsent_property, afe_overrun, duplicate, date_window, supported, unsupported, contradicted, other_authority, no_claim, hard, name_variant_property, format_B_document, dated_reference_change.
- G1: Month 3: unmet monthly quotas: wrong_decimal, wrong_rate, nonconsent_property, afe_overrun, duplicate, date_window, supported, unsupported, contradicted, other_authority, no_claim, hard, name_variant_property, format_B_document.
- G1: Month 4: unmet monthly quotas: wrong_decimal, date_window, contradicted, other_authority.

## UNVERIFIED

See failed PDF checks above, if any.

Next action: run python3 build_m.py --render-only, then python3 check_m.py.
Resolve the monthly quota conflict before treating the full gate as passed.
