#!/usr/bin/env python3
"""Write month/frozen/FREEZE-ABC.json: hashes of every file arms A, B and C depend on (before months 3-6 run).

  freeze_abc.py --note "<what the freeze rests on>"
The runners re-hash these files on a live run of months 3-6 (`--frozen month/frozen/FREEZE-ABC.json`) and refuse
on any change. Paths are relative to month/frozen/, as in arm D's FREEZE.json.
"""
import argparse, datetime, hashlib, json
from pathlib import Path

FROZEN = Path(__file__).resolve().parent / 'frozen'
FILES = ['../arms_common.py', '../arm_a.py', '../arm_b.py', '../arm_c.py', '../compare_arms.py', '../score_month.py',
         '../munits.py', '../person_maps_B.json', '../../jobb/units.py', '../../jobb/questions.py', '../../jobb/codelayer.py',
         '../../jobb/run_b.py', '../../typed/jev_backend.py', '../../synth-month/frozen-m.json',
         '../../synth-month/truth_m.json', '../../synth-month/case_spec_m.json',
         '../../../../../publishing/one-loop-two-ledgers/03-full-month-brief.md',
         '../../../../../publishing/one-loop-two-ledgers/04-arms-abc-as-built.md',
         '../../../../../publishing/one-loop-two-ledgers/05-replication-plan.md',
         '../../../../../publishing/one-loop-two-ledgers/06-b-variant-plan.md',
         '../../../../../publishing/one-loop-two-ledgers/07-b-tools-plan.md', '../calc_mcp.py']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--note', required=True)
    a = ap.parse_args()
    hashes = {f: hashlib.sha256((FROZEN / f).read_bytes()).hexdigest() for f in FILES}
    out = dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), note=a.note,
               arms={'A': 'calculation, share 0.45 (range 0.34, 0.56), 2,000 draws',
                     'B': 'claude -p, one call a month, claude-sonnet-5-5',
                     'C': 'jev-1.13.0 per document, threshold 0.80, Claude claude-sonnet-5-5 below it'},
               hashes=hashes)
    (FROZEN / 'FREEZE-ABC.json').write_text(json.dumps(out, indent=1) + '\n')
    print(f'{len(hashes)} files frozen -> {FROZEN / "FREEZE-ABC.json"}')


if __name__ == '__main__':
    main()
