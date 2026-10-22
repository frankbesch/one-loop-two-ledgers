#!/usr/bin/env python3
"""Replication summary for step 6 (publishing one-loop-two-ledgers/05-replication-plan.md, claims H1-H5).

  replicate_summary.py --arm B=results/B-claude-m3456,results/B-claude-m3456-r2,... --arm D=... [--out file.json]

Per arm and run, over months 3-6: silent, held, false holds, money caught, dollars share, and per-month silent.
Per arm: minimum, median, maximum. Repeatability: for each pair of runs, the share of lines with the same
disposition, and how many lines are held in one run but posted in the other (the lines whose review depends on
the draw). Then the five pre-registered claims, each PASS or FAIL with the evidence.
"""
import argparse, itertools, json, statistics
from pathlib import Path

MONTHS = [3, 4, 5, 6]


def outcomes(run, m):
    for tag in (f'm{m}-remap', f'm{m}'):
        p = Path(run) / tag / 'outcomes.json'
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError(f'{run}: no outcomes for month {m}')


def run_stats(run, tl):
    per, disp = {}, {}
    for m in MONTHS:
        s = h = fh = mc = 0; cd = td = 0.0
        for r in outcomes(run, m):
            k = (r['doc_id'], r['line_no']); t = tl[k]
            hold = r['disposition'] == 'hold'; disp[k] = hold
            h += hold; s += (not hold) and t['disposition'] == 'hold'; fh += hold and t['disposition'] == 'post'
            if t['money_error'] != 'none':
                td += t['error_dollars']
                if hold:
                    mc += 1; cd += t['error_dollars']
        per[m] = dict(silent=s, held=h, false_hold=fh, money=mc, dollars_share=round(cd / td, 4) if td else None)
    tot = {k: sum(per[m][k] for m in MONTHS) for k in ('silent', 'held', 'false_hold', 'money')}
    return dict(run=str(run), per_month=per, **tot), disp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--arm', action='append', required=True, help='NAME=run1,run2,...')
    ap.add_argument('--corpus', default=str(Path(__file__).resolve().parents[1] / 'synth-month'))
    ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_m.json').read_text())
    tl = {(t['doc_id'], t['line_no']): t for t in truth['lines']}
    rep = {}
    for spec in a.arm:
        name, runs = spec.split('=', 1)
        stats, disps = zip(*(run_stats(r, tl) for r in runs.split(',')))
        summ = {k: dict(min=min(s[k] for s in stats), median=statistics.median(s[k] for s in stats), max=max(s[k] for s in stats))
                for k in ('silent', 'held', 'false_hold', 'money')}
        pairs = []
        for (i, d1), (j, d2) in itertools.combinations(enumerate(disps, 1), 2):
            diff = [k for k in d1 if d1[k] != d2[k]]
            pairs.append(dict(runs=f'r{i}-r{j}', agree=round(1 - len(diff) / len(d1), 4), lines_differ=len(diff),
                              differ_key_hold=sum(tl[k]['disposition'] == 'hold' for k in diff)))
        rep[name] = dict(runs=list(stats), summary=summ, repeatability=pairs)
    claims = {}
    if 'D' in rep:
        D = rep['D']['runs']
        claims['H1'] = all(r['per_month'][m]['silent'] == 0 for r in D for m in MONTHS)
        claims['H2'] = all((r['per_month'][m]['dollars_share'] or 0) >= 0.90 for r in D for m in MONTHS)
        claims['H5'] = all(r['per_month'][4]['silent'] == 0 for r in D)
        if 'B' in rep:
            B = rep['B']['runs']
            claims['H3'] = (rep['D']['summary']['held']['median'] < rep['B']['summary']['held']['median']
                            and all(d['held'] < b['held'] for d in D for b in B))
    if 'B' in rep:
        claims['H4'] = all(r['per_month'][m]['silent'] <= 2 for r in rep['B']['runs'] for m in MONTHS)
    out = dict(months=MONTHS, arms=rep, claims={k: 'PASS' if v else 'FAIL' for k, v in sorted(claims.items())})
    for name, r in rep.items():
        print(f'{name}: ' + '; '.join(f"r{i} silent {s['silent']} held {s['held']} f.hold {s['false_hold']} money {s['money']}/96"
                                       for i, s in enumerate(r['runs'], 1)))
        print('   min/median/max ' + ', '.join(f"{k} {v['min']}/{v['median']}/{v['max']}" for k, v in r['summary'].items()))
        print('   repeatability ' + ', '.join(f"{p['runs']} agree {p['agree']:.1%} ({p['lines_differ']} lines differ, {p['differ_key_hold']} key-hold)"
                                             for p in r['repeatability']))
    print('claims:', out['claims'])
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
