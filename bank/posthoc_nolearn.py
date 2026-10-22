#!/usr/bin/env python3
"""POST-HOC (not pre-registered; step 7d): replay runs' logged answers on the scored quarters with the learning step
off, floors held at the frozen start (floors-B.json), under both rules. No model call.

  posthoc_nolearn.py --corpus ../synth-bank-3 ../runs/bank/D4-stress-r1 [...] [--out file.json]
"""
import argparse, json
from pathlib import Path
import run_bank as RB


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('runs', nargs='+'); ap.add_argument('--corpus', required=True); ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads(Path(a.corpus, 'truth_q.json').read_text())
    key = {(u['cert_id'], u['unit_id']): u for u in truth['units']}
    start = json.loads((Path(__file__).resolve().parent / 'frozen' / 'floors-B.json').read_text())
    res = {}
    for run in a.runs:
        idx = RB.replay_index(Path(run, 'calls.jsonl'))
        for rule in ('invariant', 'frozen'):
            ns = argparse.Namespace(corpus=a.corpus, backend='claude', mode='dry-run', model=None, deadline_s=0, floors=None, rule=rule)
            arm = RB.Arm(ns, truth, None); arm.floors, arm.replay = dict(start), idx
            out = RB.run_quarters(arm, ns, truth, [3, 4])
            rows = [x for q in (3, 4) for x in out[q]]
            r = dict(silent=sum(1 for x in rows if x['disposition'] == 'post' and key[(x['cert_id'], x['unit_id'])]['disposition'] == 'hold'),
                     held=sum(1 for x in rows if x['disposition'] == 'hold'),
                     false_holds=sum(1 for x in rows if x['disposition'] == 'hold' and key[(x['cert_id'], x['unit_id'])]['disposition'] == 'post'))
            res[f'{Path(run).name}:{rule}'] = r
            print(Path(run).name, rule, r)
    if a.out:
        Path(a.out).write_text(json.dumps(dict(note=__doc__, floors=start, runs=res), indent=1) + '\n')


if __name__ == '__main__':
    main()
