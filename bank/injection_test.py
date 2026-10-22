#!/usr/bin/env python3
"""Abstention injection test (13-capfix-preregistration.md, H21-H22). No model call.

Feeds the code the key's true answers on every certificate (Q1-Q4, 48 certificates), then replaces one answer
(single) or two answers (pairs) with needs_review, as the model would by abstaining, and runs the runner's own
decision code (run_bank.decide_certificate) under each rule. A silent unit is one the code posts while the key
holds it. An extra hold is a unit the code holds while the key posts it, other than the doubted addbacks themselves.
Slots: QC on every addback; QR and QX on cost-savings addbacks. A doubted QC clears QR and QX, as in the live flow,
where they are asked only when QC says cost savings.

  injection_test.py [--out results/INJECTION-20261009.json]
"""
import argparse, itertools, json, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as RB  # noqa: E402
import bunits as BU  # noqa: E402
from bcode import NEEDS_REVIEW  # noqa: E402

RULES = ('frozen', 'invariant')


def true_judged(cert_units):
    j = {}
    for u in cert_units:
        if u['unit_id'].startswith('A'):
            cs = u['category_true'] == 'cost_savings'
            j[u['addback_no']] = dict(category=u['category_true'], realized=u['realized'] if cs else 'n_a',
                                      certified=u['certified'] if cs else 'n_a')
    return j


def slots(judged):
    out = []
    for n, j in sorted(judged.items()):
        out.append((n, 'category'))
        if j['category'] == 'cost_savings':
            out += [(n, 'realized'), (n, 'certified')]
    return out


def inject(judged, picks):
    j = {n: dict(v) for n, v in judged.items()}
    for n, f in picks:
        if f == 'category':
            j[n] = dict(category=NEEDS_REVIEW, realized='n_a', certified='n_a')
        elif j[n]['category'] != NEEDS_REVIEW:
            j[n][f] = NEEDS_REVIEW
    return j


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--corpus', default=str(HERE.parent / 'synth-bank')); ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    by_cert = {}
    for u in truth['units']:
        by_cert.setdefault(u['cert_id'], []).append(u)
    res = {kind: {r: Counter() for r in RULES} for kind in ('single', 'pair')}
    silent_cases = {kind: {r: [] for r in RULES} for kind in ('single', 'pair')}
    base_mismatch = []
    for q in (1, 2, 3, 4):
        ags, cats, prior = RB.load_ref(a.corpus, q)
        by_name = {g['borrower']: g for g in ags}
        for pdf in sorted((Path(a.corpus) / 'clean').glob(f'q{q}_*.pdf')):
            cid = pdf.stem
            cert = BU.read_certificate(pdf, q); ag = by_name[cert['borrower']]; cert['borrower_id'] = ag['borrower_id']
            key = {u['unit_id']: u for u in by_cert[cid]}
            base = true_judged(by_cert[cid])
            for r in RULES:
                units, _ = RB.decide_certificate(cert, ag, prior, base, cats, r)
                bad = [uid for uid in key if units[uid]['disposition'] != key[uid]['disposition']]
                if bad:
                    base_mismatch.append((cid, r, bad))
            sl = slots(base)
            picks_by_kind = {'single': [(s,) for s in sl],
                             'pair': [p for p in itertools.combinations(sl, 2)
                                      if not (p[0][0] == p[1][0] and 'category' in (p[0][1], p[1][1]))]}
            for kind, picks_list in picks_by_kind.items():
                for picks in picks_list:
                    j = inject(base, picks)
                    doubted = {f'A{n}' for n in {p[0] for p in picks}}
                    for r in RULES:
                        units, _ = RB.decide_certificate(cert, ag, prior, j, cats, r)
                        c = res[kind][r]; c['injections'] += 1
                        for uid, k in key.items():
                            post = units[uid]['disposition'] == 'post'
                            if post and k['disposition'] == 'hold':
                                c['silent'] += 1; c[f"silent_{k['unit_type']}"] += 1
                                silent_cases[kind][r].append(dict(cert_id=cid, picks=[list(p) for p in picks], unit=uid,
                                                                   key_class=k['error_class']))
                            elif not post and k['disposition'] == 'post' and uid not in doubted:
                                c['extra_holds'] += 1
                        c['injections_with_silent'] += any(units[uid]['disposition'] == 'post' and key[uid]['disposition'] == 'hold' for uid in key)
    out = dict(note=__doc__, base_mismatch=base_mismatch,
               results={kind: {r: dict(c) for r, c in v.items()} for kind, v in res.items()},
               silent_cases=silent_cases)
    h21 = res['single']['invariant']['silent'] == 0
    h21_power = res['single']['frozen']['silent'] >= 1
    h22 = res['pair']['invariant']['silent'] == 0
    out['claims'] = dict(H21='PASS' if h21 else 'FAIL', H21_detector='PASS' if h21_power else 'FAIL', H22='PASS' if h22 else 'FAIL',
                         base_check='PASS' if not base_mismatch else 'FAIL')
    for kind in res:
        for r in RULES:
            print(kind, r, dict(res[kind][r]))
    print('claims:', out['claims'])
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
