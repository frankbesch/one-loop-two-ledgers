#!/usr/bin/env python3
"""POST-HOC (not pre-registered): replay arm D's logged answers through a corrected cap rule. No model call.

Found on the scored quarters (D r1, q4_b07): an addback held for review (needs_review) was left out of the
cost-savings bucket, so a later addback that the key puts over the cap was posted unseen. The frozen rule fails
closed on the doubted line but not on lines whose cap test depends on it.
The fix tested here: when any earlier cost-savings line in the certificate is under review, evaluate each later
cost-savings line's cap test twice (the doubted line counted, and not counted); if the two disagree, hold the later
line for review too. Everything else is the frozen code and the logged answers at each run's floors.

  posthoc_capfix.py runs/bank/D-q1234-r1 [...]
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bcode as B  # noqa: E402
import run_bank as RB  # noqa: E402

_frozen = B.addback_tests


def addback_tests_fixed(addbacks, ag, quarter, unadjusted, judged):
    out = _frozen(addbacks, ag, quarter, unadjusted, judged)
    doubt = [a['addback_no'] for a in addbacks if out[a['addback_no']][0] == B.NEEDS_REVIEW and judged[a['addback_no']]['category'] == 'cost_savings']
    if not doubt:
        return out
    as_ok = {n: (dict(j, realized='realized', certified='yes') if n in doubt else j) for n, j in judged.items()}
    alt = _frozen(addbacks, ag, quarter, unadjusted, as_ok)
    for a in addbacks:
        n = a['addback_no']
        if n in doubt or judged[n]['category'] != 'cost_savings' or n < min(doubt):
            continue
        if out[n][0] != alt[n][0]:
            out[n] = (B.NEEDS_REVIEW, False)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('runs', nargs='+'); ap.add_argument('--corpus', default=str(HERE.parent / 'synth-bank'))
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    key = {(u['cert_id'], u['unit_id']): u for u in truth['units']}
    fz = json.loads((HERE / 'frozen' / 'FREEZE-BANK.json').read_text())
    B.addback_tests = addback_tests_fixed
    res = {}
    for run in a.runs:
        promos = json.loads((Path(run) / 'promotions.json').read_text()) if (Path(run) / 'promotions.json').exists() else []
        idx = RB.replay_index(Path(run) / 'calls.jsonl')
        args = argparse.Namespace(corpus=a.corpus, backend='claude', mode='dry-run', model=None, deadline_s=0, floors=None)
        floors = dict(fz['floors']); out = {}
        for q in (1, 2, 3, 4):
            arm = RB.Arm(args, truth, None); arm.floors, arm.replay = dict(floors), idx
            out[q] = RB.run_quarters(arm, args, truth, [q])[q]
            p = next((x for x in promos if x['after_quarter'] == q and x['promoted']), None)
            if p:
                floors = dict(p['challenger'])
        s = {q: sum(1 for r in out[q] if r['disposition'] == 'post' and key[(r['cert_id'], r['unit_id'])]['disposition'] == 'hold') for q in (3, 4)}
        h = {q: sum(1 for r in out[q] if r['disposition'] == 'hold') for q in (3, 4)}
        res[run] = dict(silent=s, held=h, silent_total=sum(s.values()), held_total=sum(h.values()))
        print(Path(run).name, res[run])
    (HERE / 'results' / 'POSTHOC-capfix.json').write_text(json.dumps(dict(note=__doc__, runs=res), indent=1) + '\n')


if __name__ == '__main__':
    main()
