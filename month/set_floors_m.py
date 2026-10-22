#!/usr/bin/env python3
"""Step 4 of the step 6 build order: set floors and choose the model per question on the calibration months.

  set_floors_m.py --claude <run dir> --jev <run dir> [--months 1 2] --out month/frozen/

Replays logged answers only; no model call. For every assignment of Claude or Jev to Q2, Q5, Q7, Q9 (Q6 is a
note to the person and never changes an outcome; it goes to the cheaper model), floors are set by coordinate
descent over 0.40..0.95 under the policy fixed before the sweep:
  1. fewest silent lines (posted while the key holds them);
  2. then fewest lines held for a person;
  3. then the highest floors (the most conservative point of a tie).
F4 (Frank, 10-08): per question, the cheapest model that passes. "Passes" = the calibration months meet the
arm D marks: at most 2 silent lines per month and at least 90% of planted dollars caught. Among passing
assignments the one with the most Jev questions wins (Jev is metered at about $0.015 per month; Claude costs
subscription minutes); then fewer lines held. A line a replay cannot simulate (a question the logged run never
asked) counts as held, and the count is reported.
"""
import argparse, itertools, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mcode as M  # noqa: E402
import munits as MU  # noqa: E402
import run_month as RM  # noqa: E402

GRID = [round(0.40 + 0.05 * i, 2) for i in range(12)]
QS = ['Q2', 'Q5', 'Q7', 'Q9']


class A:   # the argument object Arm expects
    backend, mode, jev_model, model, deadline_s, max_spend = 'replay', 'dry-run', 'jev-1.13.0', None, 60, 0
    floors = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--claude', required=True)
    ap.add_argument('--jev', required=True)
    ap.add_argument('--months', type=int, nargs='+', default=[1, 2])
    ap.add_argument('--corpus', default=str(HERE.parent / 'synth-month'))
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    corpus = Path(a.corpus)
    truth = json.loads((corpus / 'truth_m.json').read_text())
    tl = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
    ref = {k: json.loads((corpus / 'reference' / f'{k}.json').read_text())
           for k in ('doi', 'contract_rates', 'afe_register', 'elections', 'joa_terms', 'properties')}
    spec = json.loads((corpus / 'case_spec_m.json').read_text())
    period = {m['month']: m['billing_period'] for m in spec['months']}
    formats = json.loads((HERE / 'formats_known.json').read_text())
    reg = M.Register(ref['afe_register'], formats)
    units = {m: sorted(MU.load_month(corpus, m, formats)[0], key=lambda u: (u['doc_id'], u['line_no'])) for m in a.months}
    tmp = Path(a.out) / '_scratch'; tmp.mkdir(parents=True, exist_ok=True)

    def evaluate(src, floors):
        A.floors = None
        arm = RM.Arm(A, truth, reg, ref['properties'], tmp)
        arm.floors = floors
        arm.replay = RM.Replay({q: (a.claude if src[q] == 'claude' else a.jev) for q in src} | {'*': a.claude})
        silent = held = 0
        per = {}
        state = None
        for m in a.months:
            money = M.Money(ref, reg, state)
            sm = hm = 0; caught = total = 0.0
            for u in units[m]:
                arm.ord = {}
                r = arm.line(m, u, money, period[m])
                t = tl[(u['doc_id'], u['line_no'])]
                sm += r['disposition'] == 'post' and t['disposition'] == 'hold'
                hm += r['disposition'] == 'hold'
                if t['money_error'] != 'none':
                    total += t['error_dollars']; caught += t['error_dollars'] if r['disposition'] == 'hold' else 0
            state = money.state()
            per[m] = dict(silent=sm, held=hm, dollars_share=round(caught / total, 4) if total else None)
            silent += sm; held += hm
        arm.log.close()
        passes = all(p['silent'] <= 2 and (p['dollars_share'] or 0) >= 0.90 for p in per.values())
        return silent, held, passes, per, arm.unsimulated

    results = []
    for combo in itertools.product(['jev', 'claude'], repeat=len(QS)):
        src = dict(zip(QS, combo)); src['Q6'] = 'jev'
        floors = {q: 0.60 for q in QS + ['Q6']}
        best = evaluate(src, floors)
        for _ in range(2):                         # coordinate descent, two passes
            for q in QS:
                cands = []
                for f in GRID:
                    trial = dict(floors, **{q: f})
                    s, h, ok, per, un = evaluate(src, trial)
                    cands.append(((s, h, -f), f, (s, h, ok, per, un)))
                cands.sort(key=lambda x: x[0])
                floors[q] = cands[0][1]; best = cands[0][2]
        s, h, ok, per, un = best
        results.append(dict(sources=src, floors=floors, silent=s, held=h, passes=ok, per_month=per, unsimulated=un,
                            jev_questions=sum(1 for q in QS if src[q] == 'jev')))
        print(f"{src}  silent={s} held={h} pass={ok} floors={floors} unsim={un}", flush=True)
    passing = [r for r in results if r['passes']]
    pick = max(passing, key=lambda r: (r['jev_questions'], -r['held'])) if passing else None
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'calibration-sweep.json').write_text(json.dumps(dict(policy=__doc__, results=results, pick=pick), indent=1) + '\n')
    print('PICK:', json.dumps(pick, indent=1) if pick else 'no assignment passes the calibration marks')


if __name__ == '__main__':
    main()
