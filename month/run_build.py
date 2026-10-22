#!/usr/bin/env python3
"""Step 6 data build: run one stage of the four-session Codex build (one-loop-step6 01-month-data-brief.md).

Reuses job B's session plumbing (jobb/run_jobb.py): fresh folder per session, prompts read from the brief,
codex exec on the subscription with stdin closed, a containment scan of every command. No metered call.

  run_build.py --mode smoke|full --work <dir> --stage designer|generator|render|rekey|adjudicate|freeze
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO / 'jobb'))
import run_jobb as R  # noqa: E402

ART = DEMO.parent / 'artifacts' / 'one-loop-step6-2026-10-08'
INP = ART / 'inputs'
R.BRIEF = ART / '01-month-data-brief.md'


def stage_inputs(stage, mode, work, d):
    comp = INP / ('composition-m-smoke.md' if mode == 'smoke' else 'composition-m.md')
    quot = INP / ('quotas-m-smoke.md' if mode == 'smoke' else 'quotas-m.md')
    g = work / 'generator'
    if stage == 'designer':
        R.cp(comp, d / 'composition-m.md'); R.cp(quot, d / 'quotas-m.md')
        R.cp(INP / 'used_labels.txt', d / 'used_labels.txt'); R.cp(INP / 'rekey_fields_m.md', d / 'rekey_fields_m.md')
    elif stage == 'generator':
        R.cp(work / 'designer' / 'case_spec_m.json', d / 'case_spec_m.json')
        R.cp(quot, d / 'quotas-m.md'); R.cp(INP / 'rekey_fields_m.md', d / 'rekey_fields_m.md')
        shutil.copytree(DEMO / 'synth-heldout' / 'src', d / 'ref-run1-src', ignore=shutil.ignore_patterns('__pycache__'))
    elif stage == 'rekey':
        R.cp(g / 'page-images' / 'clean', d / 'page-images' / 'clean')
        R.cp(g / 'reference', d / 'reference')
        R.cp(INP / 'rekey_fields_m.md', d / 'rekey_fields_m.md')
    elif stage == 'adjudicate':
        R.cp(g / 'truth_m.json', d / 'truth_m.json')
        for k in sorted(work.glob('rekey*/truth-blind')):           # one session, or one per month
            for f in k.glob('*.json'):
                R.cp(f, d / 'truth-blind' / f.name)
        R.cp(g / 'page-images' / 'clean', d / 'page-images' / 'clean')
        R.cp(g / 'reference', d / 'reference')
        R.cp(INP / 'rekey_fields_m.md', d / 'rekey_fields_m.md')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('smoke', 'full'), required=True)
    ap.add_argument('--work', required=True, type=Path)
    ap.add_argument('--stage', required=True, choices=('designer', 'generator', 'render', 'rekey', 'adjudicate', 'freeze'))
    ap.add_argument('--month', type=int, help='rekey only: key this month in its own session (rekey-m<k>)')
    a = ap.parse_args()
    work = a.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    g = work / 'generator'
    rec = {'stage': a.stage, 'mode': a.mode, 'started': time.strftime('%Y-%m-%dT%H:%M:%S')}
    if a.stage in R.SESSION_HEAD:
        _, prompt = R.prompt_for(a.stage)
        name = f'rekey-m{a.month}' if a.stage == 'rekey' and a.month else a.stage
        d = R.fresh(work, name)
        stage_inputs(a.stage, a.mode, work, d)
        if a.stage == 'rekey' and a.month:      # this month's pages only; reference and ledgers unchanged
            for p in (d / 'page-images' / 'clean').glob('*.png'):
                if not p.name.startswith(f'm{a.month}_'):
                    p.unlink()
        rec['inputs'] = sorted(str(p.relative_to(d)) for p in d.rglob('*') if p.is_file() and 'ref-run1-src' not in p.parts)
        rc, secs, log = R.run_codex(name, d, prompt)
        rec.update(rc=rc, seconds=secs, outside_paths=R.containment(log, d))
    elif a.stage == 'render':
        rec['render_rc'] = subprocess.run([sys.executable, 'build_m.py', '--render-only'], cwd=g).returncode
        imgs = g / 'page-images' / 'clean'; imgs.mkdir(parents=True, exist_ok=True)
        for pdf in sorted((g / 'clean').glob('*.pdf')):
            subprocess.run(['pdftoppm', '-r', '110', '-png', str(pdf), str(imgs / pdf.stem)], check=True)
        chk = subprocess.run([sys.executable, 'check_m.py'], cwd=g, capture_output=True, text=True)
        rec.update(check_rc=chk.returncode, check_out=chk.stdout[-3000:] + chk.stderr[-1500:],
                   pdfs=len(list((g / 'clean').glob('*.pdf'))), images=len(list(imgs.glob('*.png'))))
    elif a.stage == 'freeze':
        files = [g / 'truth_m.json'] + sorted((g / 'reference').glob('*')) + sorted((g / 'clean').glob('*.pdf'))
        frozen = {str(p.relative_to(g)): R.sha(p) for p in files}
        (g / 'frozen-m.json').write_text(json.dumps(frozen, indent=1) + '\n')
        rec['frozen_files'] = len(frozen)
    (work / f"{(name if a.stage in R.SESSION_HEAD else a.stage)}.record.json").write_text(json.dumps(rec, indent=1) + '\n')
    print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
