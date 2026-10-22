#!/usr/bin/env python3
"""Replay a run's logged answers through a chosen decision rule. No model call (13-capfix-preregistration.md, H26).

Re-runs the quarters with each run's floors, applying the run's own promotions after each quarter, exactly as the
live loop did. With --rule frozen on a step 7 run it must reproduce that run's outcomes unit for unit (the fidelity
check); with --rule invariant it gives the fixed rule's outcome on the same answers.

  replay_rule.py --rule invariant runs/bank/D-q1234-r1 [...] [--fidelity] [--out file.json]
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as RB  # noqa: E402


def replay(run, rule, corpus, truth, start_floors):
    promos = json.loads((Path(run) / 'promotions.json').read_text()) if (Path(run) / 'promotions.json').exists() else []
    idx = RB.replay_index(Path(run) / 'calls.jsonl')
    args = argparse.Namespace(corpus=corpus, backend='claude', mode='dry-run', model=None, deadline_s=0, floors=None, rule=rule)
    floors, out = dict(start_floors), {}
    for q in (1, 2, 3, 4):
        arm = RB.Arm(args, truth, None); arm.floors, arm.replay = dict(floors), idx
        out[q] = RB.run_quarters(arm, args, truth, [q])[q]
        if arm.unsimulated:
            raise SystemExit(f'{run}: {arm.unsimulated} answers missing from the log')
        p = next((x for x in promos if x['after_quarter'] == q and x['promoted']), None)
        if p:
            floors = dict(p['challenger'])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('runs', nargs='+'); ap.add_argument('--rule', required=True, choices=('frozen', 'invariant', 'invariant-lock'))
    ap.add_argument('--corpus', default=str(HERE.parent / 'synth-bank')); ap.add_argument('--fidelity', action='store_true'); ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    key = {(u['cert_id'], u['unit_id']): u for u in truth['units']}
    res = {}
    for run in a.runs:
        meta = json.loads((Path(run) / 'meta.json').read_text())
        out = replay(run, a.rule, a.corpus, truth, json.loads(Path(meta['floors']).read_text()))
        r = dict(silent={q: sum(1 for x in out[q] if x['disposition'] == 'post' and key[(x['cert_id'], x['unit_id'])]['disposition'] == 'hold') for q in (3, 4)},
                 held={q: sum(1 for x in out[q] if x['disposition'] == 'hold') for q in (3, 4)})
        r.update(silent_total=sum(r['silent'].values()), held_total=sum(r['held'].values()))
        if a.fidelity:
            diff = []
            for q in (1, 2, 3, 4):
                live = {(x['cert_id'], x['unit_id']): x['disposition'] for x in json.loads((Path(run) / f'q{q}' / 'outcomes.json').read_text())}
                diff += [k for k in live if live[k] != {(x['cert_id'], x['unit_id']): x['disposition'] for x in out[q]}[k]]
            r['fidelity_differences'] = len(diff)
        res[run] = r
        print(Path(run).name, a.rule, r)
    if a.out:
        Path(a.out).write_text(json.dumps(dict(rule=a.rule, runs=res), indent=1) + '\n')


if __name__ == '__main__':
    main()
