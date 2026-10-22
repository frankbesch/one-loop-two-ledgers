#!/usr/bin/env python3
"""Rebuild the job B `scored` split with wordings disjoint from `calibration` (Frank, 2026-10-08).

Calibration stays as built. A fresh Codex designer writes scored cases only. The frozen generator code
(synth-jobb/build_b.py) builds both splits from the merged spec, so both share one renderer. Calibration
sources must come out byte-identical; their frozen PDFs are then kept. The blind re-key and the
adjudicator run fresh, on scored pages only. Spend: Codex on the subscription only (D-283).

  rebuild_scored.py --work <dir> --stage designer|build|rekey|adjudicate|freeze
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_jobb as R

DEMO = R.DEMO
BUILT = DEMO / 'synth-jobb'
INP = R.INP


def scored(name):
    return name.startswith('sco_')


CHANGED = []


def conform(new, old):
    """Map the scored designer's spec onto the frozen generator's schema. Every value is derived from the
    new spec itself; the billing period is the calibration split's period (one billing period, by design)."""
    from decimal import Decimal, ROUND_HALF_UP
    period = {d.get('billing_period') for d in old['documents']}
    assert len(period) == 1, period
    for d in new['documents']:
        for l in d['lines']:
            if 'net_amount' not in l:
                l['net_amount'] = l.pop('net')
            want = (Decimal(str(l['gross'])) * Decimal(str(l['owner_decimal']))).quantize(Decimal('0.01'), ROUND_HALF_UP)
            if Decimal(str(l['net_amount'])) != want:   # designer float rounding vs the generator's ROUND_HALF_UP
                assert abs(Decimal(str(l['net_amount'])) - want) <= Decimal('0.01'), (d['doc_id'], l['line_no'])
                CHANGED.append(f"{d['doc_id']}:{l['line_no']} {l['net_amount']} -> {want}")
                l['net_amount'] = float(want)
        d.setdefault('billing_period', next(iter(period)))
        d.setdefault('pages', max(l['page'] for l in d['lines']))
        if 'vendor' not in d:
            vs = {l['vendor'] for l in d['lines']}
            d['vendor'] = vs.pop() if d['type'] == 'vendor_invoice' and len(vs) == 1 else None
            assert d['type'] != 'vendor_invoice' or d['vendor'], d['doc_id']
        page_of = {l['line_no']: l['page'] for l in d['lines']}
        for r in d['remarks']:
            r.setdefault('page', page_of[r['names_line']])
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True, type=Path)
    ap.add_argument('--stage', required=True, choices=('designer', 'build', 'finalize', 'rekey', 'adjudicate', 'freeze'))
    a = ap.parse_args()
    work = a.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    g = work / 'generator'
    rec = {'stage': a.stage, 'mode': 'scored-rebuild', 'started': time.strftime('%Y-%m-%dT%H:%M:%S')}

    if a.stage == 'designer':
        _, prompt = R.prompt_for('designer')
        prompt += '\n\n' + (INP / 'designer-addendum-scored.md').read_text()
        prompt = prompt.replace('INPUTS: ', '')
        d = R.fresh(work, 'designer')
        for src, dst in [('composition-b-scored.md', 'composition-b.md'), ('quotas-b.md', 'quotas-b.md'),
                         ('used_labels.txt', 'used_labels.txt'), ('rekey_fields_b.md', 'rekey_fields_b.md'),
                         ('calibration_context.json', 'calibration_context.json')]:
            R.cp(INP / src, d / dst)
        prompt = prompt.replace('composition-b.md fixes the documents and splits.',
                                'composition-b.md fixes the documents and splits. calibration_context.json describes the existing calibration split.')
        rc, secs, log = R.run_codex('designer', d, prompt)
        rec.update(rc=rc, seconds=secs, outside_paths=R.containment(log, d))

    elif a.stage == 'build':
        if g.exists():
            shutil.move(str(g), str(work / f'generator.quarantine.{int(time.time())}'))
        g.mkdir()
        for f in ('build_b.py', 'check_b.py', 'test_b.py', 'quotas-b.md', 'rekey_fields_b.md'):
            shutil.copy2(BUILT / f, g / f)
        old = json.loads((BUILT / 'case_spec_b.json').read_text())
        new = json.loads((work / 'designer' / 'case_spec_b.json').read_text())
        new = conform(new, old)
        rec['net_rounding_corrections'] = CHANGED
        rec['schema_mapping'] = 'net->net_amount; pages, billing_period, invoice vendor, remark page derived (see conform)'
        merged = dict(old)
        merged['documents'] = [d for d in old['documents'] if d['split'] == 'calibration'] + \
                              [d for d in new['documents'] if d['split'] == 'scored']
        merged['afe_register'] = [r for r in old['afe_register'] if r['split'] == 'calibration'] + \
                                 [r for r in new['afe_register'] if r['split'] == 'scored']
        merged['quota_check'] = {'calibration': old['quota_check'].get('calibration'), 'scored': new['quota_check'].get('scored')}
        merged['entities'] = old['entities']
        rec['entities_equal'] = new.get('entities') == old['entities']
        (g / 'case_spec_b.json').write_text(json.dumps(merged, indent=2, ensure_ascii=False) + '\n')
        rec['source_rc'] = subprocess.run([sys.executable, 'build_b.py', '--source-only'], cwd=g).returncode
        same = [p.name for p in sorted((BUILT / 'sources').glob('cal_*.html'))
                if (g / 'sources' / p.name).read_bytes() == p.read_bytes()]
        rec['calibration_sources_identical'] = f"{len(same)}/{len(list((BUILT / 'sources').glob('cal_*.html')))}"
        rec['render_rc'] = subprocess.run([sys.executable, 'build_b.py', '--render-only'], cwd=g).returncode
        # Calibration sources are identical, so keep the frozen calibration PDFs and images byte for byte.
        if len(same) == len(list((BUILT / 'sources').glob('cal_*.html'))):
            for p in (BUILT / 'clean').glob('cal_*.pdf'):
                shutil.copy2(p, g / 'clean' / p.name)
        imgs = g / 'page-images' / 'clean'; imgs.mkdir(parents=True, exist_ok=True)
        for p in (BUILT / 'page-images' / 'clean').glob('cal_*.png'):
            shutil.copy2(p, imgs / p.name)
        for pdf in sorted((g / 'clean').glob('sco_*.pdf')):
            subprocess.run(['pdftoppm', '-r', '110', '-png', str(pdf), str(imgs / pdf.stem)], check=True)
        chk = subprocess.run([sys.executable, 'check_b.py'], cwd=g, capture_output=True, text=True)
        rec.update(check_rc=chk.returncode, check_out=chk.stdout[-2000:] + chk.stderr[-800:])

    elif a.stage == 'finalize':
        # The gate compares recomputed counts with the spec's quota_check. The scored designer used its own
        # key names and value_over_code definition; keep its numbers, and record the gate's own counts.
        spec = json.loads((g / 'case_spec_b.json').read_text())
        counts = json.loads((g / 'gate_results_b.json').read_text())['quota_counts']['scored']
        spec['quota_check_designer_scored'] = spec['quota_check']['scored']
        spec['quota_check']['scored'] = counts
        (g / 'case_spec_b.json').write_text(json.dumps(spec, indent=2, ensure_ascii=False) + '\n')
        before = {p.name: p.read_bytes() for p in (g / 'sources').glob('*.html')}
        keep = {p.name: p.read_bytes() for p in (g / 'clean').glob('*.pdf')}
        rec['source_rc'] = subprocess.run([sys.executable, 'build_b.py', '--source-only'], cwd=g).returncode
        rec['sources_unchanged'] = all((g / 'sources' / n).read_bytes() == b for n, b in before.items())
        rec['render_rc'] = subprocess.run([sys.executable, 'build_b.py', '--render-only'], cwd=g).returncode
        if rec['sources_unchanged']:
            for n, b in keep.items():          # same sources: keep the already-checked PDFs byte for byte
                (g / 'clean' / n).write_bytes(b)
        chk = subprocess.run([sys.executable, 'check_b.py'], cwd=g, capture_output=True, text=True)
        rec.update(check_rc=chk.returncode, check_out=chk.stdout[-1500:])

    elif a.stage == 'rekey':
        _, prompt = R.prompt_for('rekey')
        d = R.fresh(work, 'rekey')
        for p in (g / 'page-images' / 'clean').glob('sco_*.png'):
            R.cp(p, d / 'page-images' / 'clean' / p.name)
        reg = [r for r in json.loads((g / 'reference' / 'afe_register.json').read_text()) if r['split'] == 'scored']
        (d / 'afe_register.json').write_text(json.dumps(reg, indent=1) + '\n')
        R.cp(INP / 'rekey_fields_b.md', d / 'rekey_fields_b.md')
        rc, secs, log = R.run_codex('rekey', d, prompt)
        rec.update(rc=rc, seconds=secs, outside_paths=R.containment(log, d))

    elif a.stage == 'adjudicate':
        _, prompt = R.prompt_for('adjudicate')
        d = R.fresh(work, 'adjudicate')
        t = json.loads((g / 'truth_b.json').read_text())
        t['lines'] = [l for l in t['lines'] if l['split'] == 'scored']
        t['remarks'] = [r for r in t['remarks'] if r['split'] == 'scored']
        (d / 'truth_b.json').write_text(json.dumps(t, indent=1, ensure_ascii=False) + '\n')
        R.cp(work / 'rekey' / 'truth-blind', d / 'truth-blind')
        for p in (g / 'page-images' / 'clean').glob('sco_*.png'):
            R.cp(p, d / 'page-images' / 'clean' / p.name)
        R.cp(work / 'rekey' / 'afe_register.json', d / 'afe_register.json')
        R.cp(INP / 'rekey_fields_b.md', d / 'rekey_fields_b.md')
        prompt += ('\n\nRemark numbering: the two keys may number remarks differently. Compare remarks by '
                   '(doc_id, names_line, text) and report a numbering-only difference as such, not as a content difference.')
        rc, secs, log = R.run_codex('adjudicate', d, prompt)
        rec.update(rc=rc, seconds=secs, outside_paths=R.containment(log, d))

    elif a.stage == 'freeze':
        files = [g / 'truth_b.json'] + sorted((g / 'reference').glob('*')) + sorted((g / 'clean').glob('*.pdf'))
        frozen = {str(p.relative_to(g)): R.sha(p) for p in files}
        (g / 'frozen-b.json').write_text(json.dumps(frozen, indent=1) + '\n')
        old = json.loads((BUILT / 'frozen-b.json').read_text())
        rec['frozen_files'] = len(frozen)
        rec['calibration_pdfs_unchanged'] = all(old.get(k) == v for k, v in frozen.items() if '/cal_' in k)

    (work / f'{a.stage}.record.json').write_text(json.dumps(rec, indent=1) + '\n')
    print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
