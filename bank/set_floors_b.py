#!/usr/bin/env python3
"""Step 7: set arm D's floors on the calibration quarters (Q1-Q2). Configured from month/set_floors_m.py.

  set_floors_b.py --calls runs/bank/<calibration run>/calls.jsonl --out bank/frozen/floors-B.json
Replays the logged answers only (no model call). Policy fixed before the sweep, as in step 6: the fewest silent
units, then the fewest held, then the highest floors in a tie. Coordinate descent over 0.40..0.95, two passes.
One model (R3), so no per-question model choice.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as RB  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--calls', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--corpus', default=str(HERE.parent / 'synth-bank')); ap.add_argument('--quarters', type=int, nargs='+', default=[1, 2])
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    labels = {(u['cert_id'], u['unit_id']): u['disposition'] for u in truth['units'] if u['quarter'] in a.quarters}
    idx = RB.replay_index(a.calls)
    args = RB.argparse.Namespace(corpus=a.corpus, backend='claude', mode='dry-run', model=None, deadline_s=0, floors=None)

    def ev(fl):
        arm = RB.Arm(args, truth, None); arm.floors, arm.replay = dict(fl), idx
        res = RB.run_quarters(arm, args, truth, a.quarters)
        s = h = 0
        for q in a.quarters:
            x = RB.silent_held(res[q], labels); s += x[0]; h += x[1]
        return s, h, arm.unsimulated
    floors = {q: RB.DEFAULT_FLOOR for q in RB.QIDS}
    trace = []
    for _ in range(2):
        for q in RB.QIDS:
            cands = []
            for f in RB.GRID:
                s, h, un = ev(dict(floors, **{q: f}))
                cands.append(((s, h, -f), f, s, h, un))
            cands.sort(key=lambda c: c[0])
            floors[q] = cands[0][1]; trace.append(dict(question=q, floor=cands[0][1], silent=cands[0][2], held=cands[0][3]))
    s, h, un = ev(floors)
    out = dict(policy=__doc__, floors=floors, calibration=dict(quarters=a.quarters, silent=s, held=h, key_holds=sum(1 for v in labels.values() if v == 'hold'), unsimulated=un), trace=trace)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(floors, indent=1) + '\n')
    Path(a.out).with_name('calibration-sweep-B.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out['calibration'] | {'floors': floors}, indent=1))


if __name__ == '__main__':
    main()
