#!/usr/bin/env python3
"""Step 5 table: the four arms side by side on the same months (publishing 03-full-month-brief.md §6).

  compare_arms.py --months 3 4 5 6 --run A=<run dir> --run B=<run dir> --run C=<run dir> --run D=<run dir>

Per arm, summed over --months: lines, to a person (held), silent (posted but the key holds them), false holds,
planted money errors caught per class and in dollars, claim cases held, lines right, months over the silent mark,
and metered spend from meta.json. Subscription minutes are reported as wall time, not as dollars.
Arm A also shows the mean over its random draws (expected.json) beside its one seeded run.
"""
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

CLASSES = ['wrong_decimal', 'wrong_rate', 'nonconsent_property', 'afe_overrun', 'duplicate', 'date_window']


def outcomes(run, m):
    for tag in (f'm{m}-remap', f'm{m}'):       # arm D: the re-run after the person adds the map is the month's result
        p = Path(run) / tag / 'outcomes.json'
        if p.exists():
            return json.loads(p.read_text()), tag
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--months', type=int, nargs='+', default=[3, 4, 5, 6])
    ap.add_argument('--corpus', default=str(Path(__file__).resolve().parents[1] / 'synth-month'))
    ap.add_argument('--out')
    ap.add_argument('--run', dest='runs', action='append', required=True, help='ARM=run dir; repeat per arm')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_m.json').read_text())
    tl = {(t['doc_id'], t['line_no']): t for t in truth['lines']}
    table = {}
    for spec in a.runs:
        name, run = spec.split('=', 1)
        meta = json.loads((Path(run) / 'meta.json').read_text())
        c, cls, cls_n = Counter(), Counter(), Counter()
        caught = total = 0.0
        over = []
        for m in a.months:
            res, tag = outcomes(run, m)
            if res is None:
                c['months_missing'] += 1; continue
            silent_m = 0
            for r in res:
                t = tl[(r['doc_id'], r['line_no'])]
                hold = r['disposition'] == 'hold'
                c['lines'] += 1; c['held'] += hold; c['right'] += r['disposition'] == t['disposition']
                s = not hold and t['disposition'] == 'hold'
                c['silent'] += s; silent_m += s
                c['false_hold'] += hold and t['disposition'] == 'post'
                if t['money_error'] != 'none':
                    cls_n[t['money_error']] += 1; total += t['error_dollars']
                    if hold:
                        cls[t['money_error']] += 1; caught += t['error_dollars']
                if t['outcome'] in ('unsupported', 'contradicted', 'other_authority'):
                    c['claim_targets'] += 1; c['claim_held'] += hold
            if silent_m > 2:
                over.append(m)
        row = dict(c, dollars_share=round(caught / total, 4) if total else None,
                   per_class={k: f'{cls[k]}/{cls_n[k]}' for k in CLASSES}, months_over_silent_mark=over,
                   spend_usd=meta.get('spend_usd', meta.get('cost_usd', 0.0)), wall_s=meta.get('wall_s'),
                   run=meta.get('arm'))
        ex = Path(run) / 'expected.json'
        if ex.exists():
            e = json.loads(ex.read_text())['months']
            row['expected_mean'] = {k: round(sum(e[str(m)][k]['mean'] for m in a.months if str(m) in e), 3)
                                    for k in ('silent', 'reviewed')}
        table[name] = row
    hdr = f"{'arm':<5}{'lines':>6}{'held':>6}{'silent':>7}{'f.hold':>7}{'$share':>8}{'claims':>9}{'right':>7}{'over':>10}{'$ spend':>9}"
    print(hdr)
    for k, r in table.items():
        print(f"{k:<5}{r.get('lines', 0):>6}{r.get('held', 0):>6}{r.get('silent', 0):>7}{r.get('false_hold', 0):>7}"
              f"{str(r['dollars_share']):>8}{str(r.get('claim_held', 0)) + '/' + str(r.get('claim_targets', 0)):>9}"
              f"{r.get('right', 0):>7}{str(r['months_over_silent_mark']):>10}{r['spend_usd']:>9.4f}")
    print('\nper money class (caught/planted):')
    for k, r in table.items():
        print(f"  {k}: " + ', '.join(f'{c} {v}' for c, v in r['per_class'].items()))
    for k, r in table.items():
        if 'expected_mean' in r:
            print(f"\n{k} mean over its random audit draws: {r['expected_mean']}")
    if a.out:
        Path(a.out).write_text(json.dumps(dict(months=a.months, arms=table), indent=1) + '\n')


if __name__ == '__main__':
    main()
