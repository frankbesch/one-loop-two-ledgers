#!/usr/bin/env python3
"""Score banking-mirror runs (10-banking-mirror-plan.md §5-§6), any arm, one or more runs per arm.

  score_bank.py --quarters 3 4 --arm D=runs/bank/D1,runs/bank/D2,runs/bank/D3 --arm B=... [--out file.json]

Each run folder holds q<k>/outcomes.json rows: cert_id, unit_id, disposition (hold/post), and optionally owner and
breach. Per run and quarter: units, held, silent (key holds, arm posts), false holds, planted errors caught per
class, hidden breaches caught, false breach flags (arm marks a breach the key does not), owner accuracy on units both
hold. Per arm: min/median/max, pairwise agreement, and whether any differing unit is key-held (H16).
Claims H12-H17, H19, H20 are evaluated when arms B, C, D are present (H18, reuse, is reported by reuse_count.py).
"""
import argparse, itertools, json, statistics
from collections import Counter
from pathlib import Path

CLASSES = ['ratio_arithmetic', 'hidden_breach', 'cap_exceeded', 'window_expired', 'category_not_permitted',
           'certification_missing', 'signer_not_officer', 'late_delivery', 'cure_invalid', 'duplicate_addback']


def load_rows(run, q):
    p = Path(run) / f'q{q}' / 'outcomes.json'
    return json.loads(p.read_text()) if p.exists() else None


def score_run(run, quarters, key):
    per, disp = {}, {}
    for q in quarters:
        rows = load_rows(run, q)
        if rows is None:
            per[q] = None; continue
        c, cls_n, cls_c = Counter(), Counter(), Counter()
        got = {(r['cert_id'], r['unit_id']): r for r in rows}
        for k, u in key.items():
            if u['quarter'] != q:
                continue
            r = got.get(k)
            hold = r is not None and r['disposition'] == 'hold'     # a unit the arm never reported counts as posted
            disp[k] = hold
            c['units'] += 1; c['held'] += hold
            kh = u['disposition'] == 'hold'
            c['silent'] += kh and not hold
            c['false_hold'] += hold and not kh
            if u['error_class'] != 'none':
                cls_n[u['error_class']] += 1; cls_c[u['error_class']] += hold
            if u['error_class'] == 'hidden_breach':
                c['hidden'] += 1; c['hidden_caught'] += hold
            if r is not None and r.get('breach') == 'yes' and u['breach'] != 'yes':
                c['false_breach'] += 1
            if hold and kh and r.get('owner') not in (None, ''):
                c['owner_n'] += 1; c['owner_ok'] += r['owner'] == u['owner']
        c['planted'] = sum(cls_n.values()); c['planted_caught'] = sum(cls_c.values())
        per[q] = dict(c, per_class={k: f'{cls_c[k]}/{cls_n[k]}' for k in CLASSES})
    tot = Counter()
    for v in per.values():
        if v:
            for k in ('units', 'held', 'silent', 'false_hold', 'planted', 'planted_caught', 'hidden', 'hidden_caught',
                      'false_breach', 'owner_n', 'owner_ok'):
                tot[k] += v.get(k, 0)
    meta = json.loads((Path(run) / 'meta.json').read_text()) if (Path(run) / 'meta.json').exists() else {}
    return dict(run=str(run), per_quarter=per, **tot, meta={k: meta.get(k) for k in ('arm', 'model', 'wall_s', 'spend_usd', 'live_calls')}), disp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(Path(__file__).resolve().parents[1] / 'synth-bank'))
    ap.add_argument('--quarters', type=int, nargs='+', default=[3, 4])
    ap.add_argument('--arm', action='append', required=True, help='NAME=run1,run2,...')
    ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    key = {(u['cert_id'], u['unit_id']): u for u in truth['units']}
    rep = {}
    for spec in a.arm:
        name, runs = spec.split('=', 1)
        stats, disps = zip(*(score_run(r, a.quarters, key) for r in runs.split(',')))
        summ = {k: dict(min=min(s[k] for s in stats), median=statistics.median(s[k] for s in stats), max=max(s[k] for s in stats))
                for k in ('silent', 'held', 'false_hold', 'planted_caught', 'hidden_caught', 'false_breach')}
        pairs = []
        for (i, d1), (j, d2) in itertools.combinations(enumerate(disps, 1), 2):
            diff = [k for k in d1 if d1[k] != d2.get(k)]
            pairs.append(dict(runs=f'r{i}-r{j}', agree=round(1 - len(diff) / max(1, len(d1)), 4), differ=len(diff),
                              differ_key_hold=sum(key[k]['disposition'] == 'hold' for k in diff)))
        rep[name] = dict(runs=list(stats), summary=summ, repeatability=pairs)
    claims = {}
    if 'D' in rep:
        D = rep['D']['runs']
        qs = [q for q in a.quarters]
        claims['H12'] = all(r['per_quarter'][q] and r['per_quarter'][q].get('silent', 0) <= 1 for r in D for q in qs)
        claims['H13'] = all(r['hidden_caught'] == r['hidden'] for r in D)
        claims['H14'] = all(r['planted'] and r['planted_caught'] / r['planted'] >= 0.90 for r in D)
        claims['H16'] = all(p['differ_key_hold'] == 0 for p in rep['D']['repeatability'])
        claims['H20'] = all(r['owner_n'] and r['owner_ok'] / r['owner_n'] >= 0.95 for r in D)
        claims['mark_false_breach'] = all(r['per_quarter'][q].get('false_breach', 0) <= 1 for r in D for q in qs)
        if 'B' in rep:
            claims['H17'] = rep['D']['summary']['held']['median'] < rep['B']['summary']['held']['median']
        if 'C' in rep:
            claims['H19'] = min(r['silent'] for r in rep['C']['runs']) > rep['D']['summary']['silent']['max']
    if 'B' in rep:
        claims['H15'] = any(r['silent'] >= 1 for r in rep['B']['runs'])
    out = dict(quarters=a.quarters, arms=rep, claims={k: 'PASS' if v else 'FAIL' for k, v in sorted(claims.items())})
    for name, r in rep.items():
        print(f'{name}: ' + '; '.join(f"r{i} silent {s['silent']} held {s['held']} f.hold {s['false_hold']} planted {s['planted_caught']}/{s['planted']} "
                                       f"hidden {s['hidden_caught']}/{s['hidden']} f.breach {s['false_breach']} owner {s['owner_ok']}/{s['owner_n']}"
                                       for i, s in enumerate(r['runs'], 1)))
        if len(r['runs']) > 1:
            print('   repeatability ' + ', '.join(f"{p['runs']} agree {p['agree']:.1%} ({p['differ']} differ, {p['differ_key_hold']} key-hold)" for p in r['repeatability']))
    print('claims:', out['claims'])
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
