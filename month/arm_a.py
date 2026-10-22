#!/usr/bin/env python3
"""Step 6 arm A, the manual proxy: an audit samples properties, and finds the planted errors in the sample only.

  arm_a.py --months 3 4 5 6 [--share 0.45] [--seed 6] [--draws 2000]

A calculation, no model and no network. Per month, properties are drawn at random until the drawn ones carry
the share of the month's billed gross closest to --share (COPAS 2006 survey: 34-56% of billed cost is audited; the default is the
midpoint, 0.45; run 0.34 and 0.56 for the range). A person (the auditor) reviews every line of a drawn property and
decides it as the key does, with the key's money reason. Every other line posts unreviewed.
The auditor is assumed perfect and to know each line's property (the key's property_no): both favour arm A.

Outputs, scored by score_month.py like arm D: m<k>/outcomes.json ("hold" = reviewed by a person), meta.json,
and expected.json: the mean and 5th-95th percentile over --draws random samples, so one lucky seed decides nothing.
"""
import argparse, datetime, json, random, statistics
from pathlib import Path

import arms_common as AC


def sample_props(lines, share, rng):
    by = {}
    for t in lines:
        by[t['property_no']] = by.get(t['property_no'], 0.0) + t['gross']
    total, got, picked = sum(by.values()), 0.0, []
    props = sorted(by)
    rng.shuffle(props)
    for p in props:                  # stop where the drawn share is closest to the target (6 properties: coarse)
        if abs(got + by[p] - share * total) >= abs(got - share * total):
            break
        picked.append(p); got += by[p]
    return set(picked), (got / total if total else 0.0)


def month_rows(lines, picked, m):
    rows = []
    for t in sorted(lines, key=lambda t: (t['doc_id'], t['line_no'])):
        seen = t['property_no'] in picked
        hold = seen and t['disposition'] == 'hold'
        rows.append(dict(month=m, doc_id=t['doc_id'], line_no=t['line_no'], property_no=t['property_no'],
                         reviewed=seen, disposition='hold' if seen else 'post',
                         money=[t['money_error']] if hold and t['money_error'] != 'none' else [],
                         reasons=(['audit:' + (t['money_error'] if t['money_error'] != 'none' else t['outcome'])] if hold
                                  else ['audit:clean'] if seen else [])))
    return rows


def stats(lines, picked):
    s = h = 0; caught = total = 0.0
    for t in lines:
        seen = t['property_no'] in picked
        h += seen
        if t['disposition'] == 'hold' and not seen:
            s += 1
        if t['money_error'] != 'none':
            total += t['error_dollars']; caught += t['error_dollars'] if seen else 0
    return s, h, (caught / total if total else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(AC.DEMO / 'synth-month'))
    ap.add_argument('--months', type=int, nargs='+', required=True)
    ap.add_argument('--share', type=float, default=0.45)
    ap.add_argument('--seed', type=int, default=6)
    ap.add_argument('--draws', type=int, default=2000)
    ap.add_argument('--out')
    a = ap.parse_args()
    truth, _, _ = AC.load(a.corpus)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm = f"A-audit{int(round(a.share * 100))}-m{''.join(map(str, a.months))}-{stamp}"
    out = Path(a.out) if a.out else AC.DEMO / 'runs' / 'month' / arm
    out.mkdir(parents=True, exist_ok=True)
    expected = {}
    for m in a.months:
        lines = [t for t in truth['lines'] if t['month'] == m]
        picked, got = sample_props(lines, a.share, random.Random(f'{a.seed}-A-{m}'))
        AC.write_month(out, m, month_rows(lines, picked, m))
        draws = [stats(lines, sample_props(lines, a.share, random.Random(f'A-draw-{m}-{i}'))[0]) for i in range(a.draws)]
        col = lambda i: sorted(x[i] for x in draws if x[i] is not None)  # noqa: E731
        pct = lambda v, q: v[min(len(v) - 1, int(q * len(v)))]  # noqa: E731
        expected[m] = {k: dict(mean=round(statistics.mean(v), 3), p05=pct(v, 0.05), p95=pct(v, 0.95))
                       for k, v in (('silent', col(0)), ('reviewed', col(1)), ('dollars_share', col(2)))}
        expected[m]['seeded_run'] = dict(properties=sorted(picked), gross_share=round(got, 4))
    (out / 'expected.json').write_text(json.dumps(dict(share=a.share, draws=a.draws, months=expected), indent=1) + '\n')
    meta = dict(arm=arm, corpus=str(Path(a.corpus).resolve()), months=a.months, backend='calculation', mode='dry-run',
                share=a.share, seed=a.seed, draws=a.draws, cost_usd=0.0, started=stamp,
                held_means='reviewed by the auditor (every line of a sampled property)')
    (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps(expected, indent=1)); print(f'outputs: {out}')


if __name__ == '__main__':
    main()
