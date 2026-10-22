#!/usr/bin/env python3
"""Confident-error injection (16-floor-lock-preregistration.md, H39-H40). No model call.

Feeds the code the key's true answers on every certificate, then replaces one answer with a WRONG option that the
model states with confidence between the learned floor and the locked floor (accepted, but below the lock), as the
model did on step 7d's q3_b01 A3. Runs the runner's decision code under 'invariant' (step 7b, ignores the lock) and
'invariant-lock'. Counts silent units OTHER than the injected line: a unit the code posts while the key holds it.
The injected line's own outcome rests on the wrong answer by design and is excluded; it is reported separately.
Wrong options: every other category on QC (a wrong cost_savings answer is tried with each realized and certified
value); the other value on QR and QX.

  injection_confident.py [--corpus ../synth-bank-3] [--out results/INJECTION-confident-....json]
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as RB  # noqa: E402
import bunits as BU  # noqa: E402
import injection_test as IT  # noqa: E402

RULES = ('invariant', 'invariant-lock')


def wrong_answers(j, cats):
    """-> [(judged_for_line, weak_fields)]"""
    out = []
    for c in cats:
        if c == j['category']:
            continue
        if c == 'cost_savings':
            out += [(dict(category=c, realized=r, certified=x), {'category', 'realized', 'certified'})
                    for r in ('realized', 'projected') for x in ('yes', 'no')]
        else:
            out.append((dict(category=c, realized='n_a', certified='n_a'), {'category'}))
    if j['category'] == 'cost_savings':
        out.append((dict(j, realized='projected' if j['realized'] == 'realized' else 'realized'), {'realized'}))
        out.append((dict(j, certified='no' if j['certified'] == 'yes' else 'yes'), {'certified'}))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--corpus', default=str(HERE.parent / 'synth-bank-3')); ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    by = {}
    for u in truth['units']:
        by.setdefault(u['cert_id'], []).append(u)
    res = {r: Counter() for r in RULES}; cases = {r: [] for r in RULES}
    for q in (1, 2, 3, 4):
        ags, cats, prior = RB.load_ref(a.corpus, q)
        bn = {g['borrower']: g for g in ags}
        for pdf in sorted((Path(a.corpus) / 'clean').glob(f'q{q}_*.pdf')):
            cid = pdf.stem
            cert = BU.read_certificate(pdf, q); ag = bn[cert['borrower']]; cert['borrower_id'] = ag['borrower_id']
            key = {u['unit_id']: u for u in by[cid]}
            base = IT.true_judged(by[cid])
            for n, j in sorted(base.items()):
                for jw, fields in wrong_answers(j, cats):
                    judged = {**base, n: jw}
                    for r in RULES:
                        units, _ = RB.decide_certificate(cert, ag, prior, judged, cats, r, {n: set(fields)})
                        c = res[r]; c['injections'] += 1
                        other = [uid for uid, k in key.items() if uid != f'A{n}' and units[uid]['disposition'] == 'post' and k['disposition'] == 'hold']
                        c['silent_other'] += len(other); c['injections_with_silent_other'] += bool(other)
                        if units[f'A{n}']['disposition'] == 'post' and key[f'A{n}']['disposition'] == 'hold':
                            c['silent_own_line'] += 1
                        c['extra_holds_other'] += sum(1 for uid, k in key.items() if uid != f'A{n}' and units[uid]['disposition'] == 'hold' and k['disposition'] == 'post')
                        for uid in other:
                            cases[r].append(dict(cert_id=cid, line=n, wrong=jw, unit=uid, key_class=key[uid]['error_class']))
    out = dict(note=__doc__, results={r: dict(c) for r, c in res.items()}, silent_cases=cases)
    out['claims'] = dict(H39='PASS' if res['invariant-lock']['silent_other'] == 0 else 'FAIL',
                         H39_detector='PASS' if res['invariant']['silent_other'] >= 1 else 'FAIL')
    for r in RULES:
        print(r, dict(res[r]))
    print('claims:', out['claims'])
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
