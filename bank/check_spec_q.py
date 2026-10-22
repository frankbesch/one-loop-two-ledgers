#!/usr/bin/env python3
"""Independent check of the Codex banking key: rebuild every unit label from the printed values and the agreement
(bcode.py, written from rekey_fields_q.md by the brain session, not by Codex), and compare with the spec's labels.

  check_spec_q.py <case_spec_q.json> [--reference <dir>]   exits 1 on any difference
The true category, realized, and certified values come from the spec's addback units (they are judgments, keyed
from the description); everything else is recomputed. Prior cures: the spec's pre-2025 history plus every cure
printed on an earlier quarter's certificate.
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bcode as B  # noqa: E402

LABELS = ('error_class', 'breach', 'disposition', 'owner')


def prior_cures(spec, quarter):
    out = [dict(c) for c in spec['prior_cures']]
    for c in spec['certificates']:
        if c['quarter'] < quarter and c.get('cure'):
            out.append(dict(borrower_id=c['borrower_id'], quarter_label=f"2025-Q{c['quarter']}", amount=c['cure']['amount']))
    return out


def judged_from_units(cert):
    j = {}
    for u in cert['units']:
        if u.get('unit_type') == 'addback':
            n = int(u['addback_no'])
            j[n] = dict(category=u['category_true'], realized=u.get('realized'), certified=u.get('certified'))
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    ags = {g['borrower_id']: g for g in spec['agreements']}
    bad, counts, n = [], Counter(), 0
    for cert in sorted(spec['certificates'], key=lambda c: (c['quarter'], c['cert_id'])):
        ag = ags[cert['borrower_id']]
        units, _ = B.evaluate(cert, ag, prior_cures(spec, cert['quarter']), judged_from_units(cert))
        keyed = {u['unit_id']: u for u in cert['units']}
        if set(keyed) != set(units):
            bad.append((cert['cert_id'], 'unit set', sorted(keyed), sorted(units)))
        for uid, mine in units.items():
            k = keyed.get(uid)
            if not k:
                continue
            n += 1
            for f in LABELS:
                if str(k.get(f)) != str(mine[f]):
                    bad.append((cert['cert_id'], uid, f, k.get(f), mine[f]))
            if k.get('error_class') != 'none':
                counts[(cert['quarter'], k['error_class'])] += 1
            if k.get('breach') == 'yes' and k.get('error_class') == 'none':
                counts[(cert['quarter'], 'honest_breach')] += 1
    # printed-text consistency: certification text names exactly the certified numbers; descriptions are not templated
    import re
    for cert in spec['certificates']:
        cer = cert.get('certification') or {}
        txt = cer.get('text') or ''
        named = {int(x) for x in re.findall(r'\d+', txt)} if cer.get('present') else set()
        for u in cert['units']:
            if u.get('unit_type') == 'addback' and u.get('category_true') == 'cost_savings':
                want = 'yes' if int(u['addback_no']) in named and int(u['addback_no']) in set(cer.get('addback_nos_named') or []) else 'no'
                if u.get('certified') != want:
                    bad.append((cert['cert_id'], u['unit_id'], 'certified vs printed paragraph', u.get('certified'), want))
    descs = [a_['description'] for c in spec['certificates'] for a_ in c['addbacks']]
    stems = Counter(re.sub(r'[^a-z ]', '', d.lower())[:60] for d in descs)
    rep = sum(v for v in stems.values() if v > 1)
    if rep > len(descs) * 0.05:
        bad.append(('corpus', 'descriptions', 'templated: lines sharing a 60-char opening', rep, len(descs)))
    if re.search(r'workstream|division \d', ' '.join(descs), re.I):
        bad.append(('corpus', 'descriptions', 'tag suffix present', 'workstream/division', ''))
    print(f'{n} units checked; {len(bad)} differences')
    for b in bad[:40]:
        print('  ', b)
    for q in (1, 2, 3, 4):
        print(f'Q{q}:', {k[1]: v for k, v in sorted(counts.items()) if k[0] == q})
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
