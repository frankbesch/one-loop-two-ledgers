#!/usr/bin/env python3
"""Job B data build: run one stage of the four-session Codex build (02-jobb-codex-brief.md).

Each Codex stage runs in a fresh folder that holds only its listed inputs. Prompts are read from the
brief's fenced blocks, so the brief stays the single source. Spend: Codex on the subscription only;
no parser, Jev, or Claude API call (D-283).

  run_jobb.py --mode smoke --work <dir> --stage designer|generator|render|rekey|adjudicate|freeze
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
ART = DEMO.parent / 'artifacts' / 'jev-v2-2026-10-05'
BRIEF = ART / '02-jobb-codex-brief.md'
INP = ART / 'jobb-inputs'
CHROME_OK = ('/Applications/Google Chrome.app',)
SESSION_HEAD = {'designer': '## Session 1', 'generator': '## Session 2', 'rekey': '## Session 3', 'adjudicate': '## Session 4'}


def prompt_for(stage):
    text = BRIEF.read_text()
    i = text.index(SESSION_HEAD[stage])
    m = re.search(r'```\n(.*?)\n```', text[i:], re.S)
    lines = m.group(1).splitlines()
    head, body = {}, []
    for j, ln in enumerate(lines):
        k, _, v = ln.partition(':')
        if k in ('INPUTS', 'OUTPUTS', 'COPY_OUT'):
            head[k] = v.strip()
        else:
            body = lines[j:]
            break
    return head, '\n'.join(body).strip()


def fresh(work, stage):
    d = work / stage
    if d.exists():
        shutil.move(str(d), str(work / f'{stage}.quarantine.{int(time.time())}'))
    d.mkdir(parents=True)
    return d


def cp(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)


def stage_inputs(stage, mode, work, d):
    comp = INP / ('composition-b-smoke.md' if mode == 'smoke' else 'composition-b.md')
    quot = INP / ('quotas-b-smoke.md' if mode == 'smoke' else 'quotas-b.md')
    gen = work / 'generator'
    if stage == 'designer':
        cp(comp, d / 'composition-b.md'); cp(quot, d / 'quotas-b.md')
        cp(INP / 'used_labels.txt', d / 'used_labels.txt'); cp(INP / 'rekey_fields_b.md', d / 'rekey_fields_b.md')
    elif stage == 'generator':
        cp(work / 'designer' / 'case_spec_b.json', d / 'case_spec_b.json')
        cp(quot, d / 'quotas-b.md'); cp(INP / 'rekey_fields_b.md', d / 'rekey_fields_b.md')
        shutil.copytree(DEMO / 'synth-heldout' / 'src', d / 'ref-run1-src', ignore=shutil.ignore_patterns('__pycache__'))
        for s in ('jib_statement.json', 'invoice.json'):
            cp(DEMO / 'schemas' / s, d / 'schemas' / s)
    elif stage == 'rekey':
        cp(gen / 'page-images' / 'clean', d / 'page-images' / 'clean')
        cp(gen / 'reference' / 'afe_register.json', d / 'afe_register.json')
        cp(INP / 'rekey_fields_b.md', d / 'rekey_fields_b.md')
    elif stage == 'adjudicate':
        cp(gen / 'truth_b.json', d / 'truth_b.json')
        cp(work / 'rekey' / 'truth-blind', d / 'truth-blind')
        cp(gen / 'page-images' / 'clean', d / 'page-images' / 'clean')
        cp(gen / 'reference' / 'afe_register.json', d / 'afe_register.json')
        cp(INP / 'rekey_fields_b.md', d / 'rekey_fields_b.md')


def clean_env():
    return {k: v for k, v in os.environ.items() if not re.search(r'KEY|TOKEN|SECRET', k)}


def run_codex(stage, d, prompt):
    log, last = d.parent / f'{stage}.jsonl', d.parent / f'{stage}.last.md'
    cmd = ['codex', 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', str(d),
           '--json', '-o', str(last), prompt]
    t0 = time.time()
    with open(log, 'w') as f:
        rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, env=clean_env()).returncode
    return rc, round(time.time() - t0), log


def containment(log, d):
    """Flag shell commands that name a path outside the stage folder (blindness check)."""
    flags = []
    for ln in log.read_text(errors='replace').splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        s = json.dumps(ev)
        if 'command' not in s:
            continue
        for p in re.findall(r'(/(?:Users|private|tmp|var|Volumes)/[^\s"\'\\]+)', s):
            if not p.startswith(str(d)) and not p.startswith(str(d.resolve())) and not p.startswith(CHROME_OK):
                flags.append(p)
        if re.search(r'(?<![\w.])\.\./', s):
            flags.append('../ in command')
    return sorted(set(flags))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('smoke', 'full'), required=True)
    ap.add_argument('--work', required=True, type=Path)
    ap.add_argument('--stage', required=True, choices=('designer', 'generator', 'render', 'rekey', 'adjudicate', 'freeze'))
    a = ap.parse_args()
    work = a.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    rec = {'stage': a.stage, 'mode': a.mode, 'started': time.strftime('%Y-%m-%dT%H:%M:%S')}
    if a.stage in SESSION_HEAD:
        head, prompt = prompt_for(a.stage)
        d = fresh(work, a.stage)
        stage_inputs(a.stage, a.mode, work, d)
        rec['inputs'] = sorted(str(p.relative_to(d)) for p in d.rglob('*') if p.is_file() and 'ref-run1-src' not in p.parts)
        rc, secs, log = run_codex(a.stage, d, prompt)
        rec.update(rc=rc, seconds=secs, outside_paths=containment(log, d))
    elif a.stage == 'render':
        g = work / 'generator'
        rec['render_rc'] = subprocess.run([sys.executable, 'src/build_b.py' if (g / 'src/build_b.py').exists() else 'build_b.py', '--render-only'], cwd=g).returncode
        imgs = g / 'page-images' / 'clean'; imgs.mkdir(parents=True, exist_ok=True)
        for pdf in sorted((g / 'clean').glob('*.pdf')):
            subprocess.run(['pdftoppm', '-r', '110', '-png', str(pdf), str(imgs / pdf.stem)], check=True)
        chk = subprocess.run([sys.executable, 'src/check_b.py' if (g / 'src/check_b.py').exists() else 'check_b.py'], cwd=g, capture_output=True, text=True)
        rec.update(check_rc=chk.returncode, check_out=chk.stdout[-3000:] + chk.stderr[-1500:],
                   pdfs=len(list((g / 'clean').glob('*.pdf'))), images=len(list(imgs.glob('*.png'))))
    elif a.stage == 'freeze':
        g = work / 'generator'
        files = [g / 'truth_b.json'] + sorted((g / 'reference').glob('*')) + sorted((g / 'clean').glob('*.pdf'))
        frozen = {str(p.relative_to(g)): sha(p) for p in files}
        (g / 'frozen-b.json').write_text(json.dumps(frozen, indent=1) + '\n')
        rec['frozen_files'] = len(frozen)
    (work / f'{a.stage}.record.json').write_text(json.dumps(rec, indent=1) + '\n')
    print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
