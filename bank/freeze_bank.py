#!/usr/bin/env python3
"""Write bank/frozen/FREEZE-BANK.json: hashes of every file the step 7 arms depend on, before Q3-Q4 run.
Configured from month/freeze_abc.py. The runners re-hash these on a live run of Q3-Q4 and refuse on any change.

  freeze_bank.py --note "<what the freeze rests on>"
  freeze_bank.py --note "..." --out FREEZE-BANK-2.json --add ../injection_test.py ...     a later freeze; the first stays intact
"""
import argparse, datetime, hashlib, json
from pathlib import Path

FROZEN = Path(__file__).resolve().parent / 'frozen'
FILES = ['../bcode.py', '../bunits.py', '../bquestions.py', '../run_bank.py', '../arm_a_bank.py', '../arm_b_bank.py', '../arm_c_bank.py',
         '../score_bank.py', '../set_floors_b.py', 'floors-B.json',
         '../../jobb/units.py', '../../jobb/run_b.py', '../../jobb/codelayer.py', '../../jobb/questions.py', '../../typed/jev_backend.py',
         '../../month/arm_b.py', '../../month/calc_mcp.py', '../../month/arms_common.py',
         '../../synth-bank/frozen-q.json', '../../synth-bank/truth_q.json',
         '../../../artifacts/one-loop-step7-2026-10-08/inputs/rekey_fields_q.md',
         '../../../../../publishing/one-loop-two-ledgers/10-banking-mirror-plan.md']


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--note', required=True)
    ap.add_argument('--out', default='FREEZE-BANK.json'); ap.add_argument('--add', nargs='*', default=[], help='more files, relative to frozen/')
    a = ap.parse_args()
    hashes = {f: hashlib.sha256((FROZEN / f).read_bytes()).hexdigest() for f in FILES + a.add}
    out = dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), note=a.note,
               floors_file='floors-B.json', floors=json.loads((FROZEN / 'floors-B.json').read_text()), hashes=hashes)
    (FROZEN / a.out).write_text(json.dumps(out, indent=1) + '\n')
    print(f'{len(hashes)} files frozen -> {FROZEN / a.out}')


if __name__ == '__main__':
    main()
