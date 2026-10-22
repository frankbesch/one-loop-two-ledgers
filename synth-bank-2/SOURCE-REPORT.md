# Source report

Built 48 certificate sources and 396 truth units.

Deviations from spec: none. Printed values and supplied truth remain unchanged.

The spec caches 2025 cures in prior_cures. References use pre-2025 history plus earlier printed cures, once each.

Gate results:
- G1: PASS.
- G2: PASS.
- G3: PASS.
- G4: PASS.
- G5: PASS.
- G6: PASS.
- G7: PASS.

Quota recounts:

```json
{
  "1": {
    "duplicate_addback": 2,
    "cure_invalid": 2,
    "category_not_permitted": 2,
    "hidden_breach": 2,
    "signer_not_officer": 2,
    "cap_exceeded": 2,
    "late_delivery": 2,
    "window_expired": 2,
    "ratio_arithmetic": 2,
    "certification_missing": 2,
    "valid_equity_cure": 1,
    "realized_cost_savings_older_than_window": 1,
    "different_addbacks_same_amount": 1,
    "permitted_approval_word_addback": 1,
    "abbreviated_officer_title": 1,
    "honestly_reported_breach": 1,
    "average_addbacks": 4.0
  },
  "2": {
    "certification_missing": 2,
    "hidden_breach": 2,
    "cure_invalid": 2,
    "signer_not_officer": 2,
    "duplicate_addback": 2,
    "category_not_permitted": 2,
    "late_delivery": 2,
    "cap_exceeded": 2,
    "ratio_arithmetic": 2,
    "window_expired": 2,
    "valid_equity_cure": 1,
    "realized_cost_savings_older_than_window": 1,
    "different_addbacks_same_amount": 1,
    "permitted_approval_word_addback": 1,
    "abbreviated_officer_title": 1,
    "honestly_reported_breach": 1,
    "average_addbacks": 4.0
  },
  "3": {
    "window_expired": 2,
    "cure_invalid": 2,
    "certification_missing": 2,
    "hidden_breach": 2,
    "signer_not_officer": 2,
    "duplicate_addback": 2,
    "late_delivery": 2,
    "category_not_permitted": 2,
    "cap_exceeded": 2,
    "ratio_arithmetic": 2,
    "valid_equity_cure": 1,
    "realized_cost_savings_older_than_window": 1,
    "different_addbacks_same_amount": 1,
    "permitted_approval_word_addback": 1,
    "abbreviated_officer_title": 1,
    "honestly_reported_breach": 1,
    "average_addbacks": 4.0
  },
  "4": {
    "category_not_permitted": 2,
    "ratio_arithmetic": 2,
    "cap_exceeded": 2,
    "cure_invalid": 2,
    "window_expired": 2,
    "certification_missing": 2,
    "hidden_breach": 2,
    "late_delivery": 2,
    "signer_not_officer": 2,
    "duplicate_addback": 2,
    "valid_equity_cure": 1,
    "realized_cost_savings_older_than_window": 1,
    "different_addbacks_same_amount": 1,
    "permitted_approval_word_addback": 1,
    "abbreviated_officer_title": 1,
    "honestly_reported_breach": 1,
    "average_addbacks": 4.0
  }
}
```

Interpretation: “about 4” means 3.5–4.5 average addbacks. Each observed quarterly average is reported above.

UNVERIFIED: agreements provide lender commitments, but do not identify a Required Lenders coalition. No coalition was invented.
Required Lenders means more than 50% of commitments; a named coalition cannot be checked from this spec.

UNVERIFIED: visual appearance beyond extracted PDF text, page count, and portrait geometry.

Next action: run `python3 build_q.py --render-only`, then `python3 check_q.py`.
