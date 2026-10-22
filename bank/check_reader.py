#!/usr/bin/env python3
"""Gate for arm D's certificate reader (bunits.py): every printed value it reads must equal the spec's printed value.
  check_reader.py <generator dir>     exits 1 on any difference
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bunits as BU  # noqa: E402


def main():
    g = Path(sys.argv[1])
    spec = json.loads((g / 'case_spec_q.json').read_text())
    ags = {a['borrower_id']: a for a in spec['agreements']}
    bad = 0
    for c in spec['certificates']:
        try:
            r = BU.read_certificate(g / 'clean' / f"{c['cert_id']}.pdf", c['quarter'])
        except Exception as e:  # noqa: BLE001
            bad += 1; print(c['cert_id'], 'ERR', e); continue
        d = []
        if r['borrower'] != ags[c['borrower_id']]['borrower']: d.append(('borrower', r['borrower']))
        if r['delivery_date'] != c['delivery_date']: d.append('delivery')
        if r['signer_title'] != c['signer_title']: d.append(('title', r['signer_title'], c['signer_title']))
        if r['ebitda']['unadjusted'] != c['ebitda']['unadjusted']: d.append('unadj')
        if r['adjusted_ebitda_printed'] != c['adjusted_ebitda_printed']: d.append('adj')
        if len(r['addbacks']) != len(c['addbacks']): d.append(('n_addbacks', len(r['addbacks']), len(c['addbacks'])))
        for x, y in zip(r['addbacks'], c['addbacks']):
            for f in ('addback_no', 'amount', 'action_date', 'description', 'category_printed'):
                if str(x[f]).strip() != str(y[f]).strip(): d.append((f, x['addback_no'], str(x[f])[:70], str(y[f])[:70]))
        if (r['cure'] or {}).get('amount') != (c['cure'] or {}).get('amount'): d.append('cure')
        for x, y in zip(r['covenants'], c['covenants']):
            for f in ('input', 'ratio_printed', 'threshold_printed', 'status_printed'):
                if str(x[f]) != str(y[f]) and not (isinstance(y[f], (int, float)) and abs(float(x[f]) - float(y[f])) < 1e-9): d.append((x['covenant'], f, x[f], y[f]))
        ct = (c['certification'] or {}).get('text')
        if (ct or '').split() != (r['certification_text'] or '').split():
            d.append(('cert_text', (r['certification_text'] or '')[:90], (ct or '')[:90]))
        if d:
            bad += 1; print(c['cert_id'], d[:4])
    print('certificates with differences:', bad, 'of', len(spec['certificates']))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
