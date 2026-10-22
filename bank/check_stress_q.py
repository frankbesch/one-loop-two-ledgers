#!/usr/bin/env python3
"""Stress-set gate (15-stress-set-preregistration.md): every cap_exceeded line depends on an earlier line.

  check_stress_q.py <case_spec_q.json>     exits 1 on any failure
Per quarter: exactly 4 cap_exceeded lines, in 4 certificates. Each one's own amount is at or below the cap, and it
crosses only because earlier valid cost-savings lines (error_class none, certified yes) count in the bucket; every
such anchor line has an action date no more than 12 months before the quarter end.
"""
import json, sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bcode as B  # noqa: E402


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    ags = {a['borrower_id']: a for a in spec['agreements']}
    bad, per_q, certs = [], Counter(), {}
    for c in spec['certificates']:
        units = {u['addback_no']: u for u in c['units'] if u.get('unit_type') == 'addback'}
        cap = Decimal(str(ags[c['borrower_id']]['cost_savings_cap_pct'])) * Decimal(int(c['ebitda']['unadjusted']))
        for a in c['addbacks']:
            n = a['addback_no']
            if units[n]['error_class'] != 'cap_exceeded':
                continue
            per_q[c['quarter']] += 1; certs.setdefault(c['quarter'], set()).add(c['cert_id'])
            anchors = [x for x in c['addbacks'] if x['addback_no'] < n and units[x['addback_no']]['category_true'] == 'cost_savings'
                       and units[x['addback_no']]['error_class'] == 'none']
            if Decimal(int(a['amount'])) > cap:
                bad.append((c['cert_id'], n, 'over the cap on its own'))
            if not anchors:
                bad.append((c['cert_id'], n, 'no earlier valid cost-savings line'))
            for x in anchors:
                if units[x['addback_no']].get('certified') != 'yes':
                    bad.append((c['cert_id'], x['addback_no'], 'anchor not certified'))
                if B.day(x['action_date']) < B.add_months(B.QUARTER_END[c['quarter']], -12):
                    bad.append((c['cert_id'], x['addback_no'], 'anchor older than 12 months'))
    for q in (1, 2, 3, 4):
        if per_q[q] != 4 or len(certs.get(q, ())) != 4:
            bad.append((f'Q{q}', 'cap_exceeded count', per_q[q], len(certs.get(q, ()))))
    print(f'cap cases per quarter: {dict(sorted(per_q.items()))}; failures: {len(bad)}')
    for b in bad[:30]:
        print('  ', b)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
