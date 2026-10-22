#!/usr/bin/env python3
"""Write month/frozen/FREEZE-SIZE.json: hashes of every file the packet-size test (arm B packet mode) depends on.

  freeze_size.py --note "<what the freeze rests on>"                       the real freeze, frozen/FREEZE-SIZE.json
  freeze_size.py --note test --out frozen/_scratch/FREEZE-SIZE-test.json   scratch test: the doc says "scratch": true
The runners re-hash these files on a live run of months 3-6 (`--frozen month/frozen/FREEZE-SIZE.json`) and refuse
on any change; arm_b.py refuses a live run on a "scratch": true freeze.
The file list: every key of frozen/FREEZE-ABC.json, plus this script, run_size.sh, the packet draw (packets.json,
draw_packets.py, DRAW-REPORT.md), formats_known.json, every synth-month/reference/*.json, every month 3-6 clean PDF,
and the preregistration (18). Paths are written relative to month/frozen/; each key in the output is relative to the
output file's own folder, because guard_months resolves keys against the freeze file's parent. The inventory is
enforced: exactly 11 synth-month/reference/*.json, exactly 96 synth-month/clean/m[3-6]_*.pdf, and every EXTRA and
FREEZE-ABC file present; a shortfall or any missing file stops the freeze (exit 1, nothing written). The counts go
into the freeze doc under "inventory". --out other than the default is allowed only for a path containing "_scratch".
"""
import argparse, datetime, glob, hashlib, json, os, sys
from pathlib import Path

FROZEN = Path(__file__).resolve().parent / 'frozen'
DEFAULT_OUT = FROZEN / 'FREEZE-SIZE.json'
EXTRA = ['../freeze_size.py', '../run_size.sh', '../packets/packets.json', '../packets/draw_packets.py',
         '../packets/DRAW-REPORT.md', '../packets/targets.json', '../score_size.py', '../formats_known.json']
PREREG = '../../../../../publishing/one-loop-two-ledgers/18-packet-size-preregistration.md'
EXPECT_REFS, EXPECT_PDFS = 11, 96


def rel_glob(pattern):
    """Sorted matches of a pattern written relative to frozen/, returned in the same relative form."""
    return sorted(os.path.relpath(p, FROZEN) for p in glob.glob(str(FROZEN / pattern)))


def inventory():
    """-> (files, counts). Exits 1 naming every shortfall (reference json count, month 3-6 PDF count, missing EXTRA,
    FREEZE-ABC or preregistration files); the caller writes nothing in that case."""
    abc = list(json.loads((FROZEN / 'FREEZE-ABC.json').read_text())['hashes'])
    refs = rel_glob('../../synth-month/reference/*.json')
    pdfs = rel_glob('../../synth-month/clean/m[3-6]_*.pdf')
    files, seen = [], set()
    for f in abc + EXTRA + refs + pdfs + [PREREG]:
        key = os.path.normpath(FROZEN / f)
        if key not in seen:
            seen.add(key); files.append(f)
    short = []
    if len(refs) != EXPECT_REFS:
        short.append(f'synth-month/reference/*.json: {len(refs)} files, expected exactly {EXPECT_REFS}')
    if len(pdfs) != EXPECT_PDFS:
        short.append(f'synth-month/clean/m[3-6]_*.pdf: {len(pdfs)} files, expected exactly {EXPECT_PDFS}')
    for name, group in (('EXTRA', EXTRA), ('FREEZE-ABC', abc), ('preregistration', [PREREG])):
        miss = [f for f in group if not (FROZEN / f).is_file()]
        if miss:
            short.append(f'{name} files missing: {miss}')
    if short:
        print('freeze_size: inventory shortfall, nothing written: ' + '; '.join(short), file=sys.stderr)
        sys.exit(1)
    counts = dict(reference_json=len(refs), clean_pdfs_m3_6=len(pdfs), extra=len(EXTRA), freeze_abc=len(abc),
                  preregistration=1, files_total=len(files))
    return files, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--note', required=True)
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    a = ap.parse_args()
    out = Path(a.out).resolve()
    scratch = '_scratch' in str(out)
    if not scratch and out != DEFAULT_OUT:
        sys.exit(f'freeze_size: REFUSED --out {out}: only the default {DEFAULT_OUT} or a path containing "_scratch"')
    files, counts = inventory()
    missing = [f for f in files if not (FROZEN / f).is_file()]
    if missing:
        print(f'freeze_size: missing files, nothing written: {missing}', file=sys.stderr)
        sys.exit(1)
    hashes = {os.path.relpath(os.path.normpath(FROZEN / f), out.parent): hashlib.sha256((FROZEN / f).read_bytes()).hexdigest()
              for f in files}
    doc = dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), note=a.note,
               arms={'A': 'calculation, share 0.45 (range 0.34, 0.56), 2,000 draws',
                     'B': 'claude -p, one call a month, claude-sonnet-5-5',
                     'C': 'jev-1.13.0 per document, threshold 0.80, Claude claude-sonnet-5-5 below it',
                     'B-size': 'claude -p, one call a month, claude-sonnet-5-5, worksheet-calc, packet mode d3/d6/d12/d24'},
               inventory=counts, hashes=hashes)
    if scratch:
        doc['scratch'] = True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + '\n')
    print(f'inventory: {json.dumps(counts)}')
    print(f'{len(hashes)} files frozen ({counts["reference_json"]} reference json, {counts["clean_pdfs_m3_6"]} month 3-6 clean PDFs) -> {out}'
          + (' [scratch]' if scratch else ''))


if __name__ == '__main__':
    main()
