#!/usr/bin/env python3
"""Step 7 data build (banking mirror): run one stage of the Codex build (one-loop-step7 01-bank-data-brief.md).
Configured copy of month/run_build.py (step 6); the session plumbing (jobb/run_jobb.py) is reused unchanged.

Reuses job B's session plumbing (jobb/run_jobb.py): fresh folder per session, prompts read from the brief,
codex exec on the subscription with stdin closed, a containment scan of every command. No metered call.

  run_build.py --mode full --work <dir> --stage designer|generator|render|rekey|adjudicate|freeze [--quarter k] [--art <artifact folder>]
  --art one-loop-step7c-2026-10-09 builds the fresh step 7c set from its own brief and inputs.
"""
import argparse, json, re, shutil, subprocess, sys, time
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO / 'jobb'))
import run_jobb as R  # noqa: E402

ART = DEMO.parent / 'artifacts' / 'one-loop-step7-2026-10-08'
INP = ART / 'inputs'
R.BRIEF = ART / '01-bank-data-brief.md'


def stage_inputs(stage, mode, work, d):
    g = work / 'generator'
    if stage == 'designer':
        for f in ('composition-q.md', 'quotas-q.md', 'rekey_fields_q.md', 'used_labels.txt'):
            R.cp(INP / f, d / f)
    elif stage == 'generator':
        R.cp(work / 'designer' / 'case_spec_q.json', d / 'case_spec_q.json')
        R.cp(INP / 'quotas-q.md', d / 'quotas-q.md'); R.cp(INP / 'rekey_fields_q.md', d / 'rekey_fields_q.md')
        R.cp(DEMO / 'synth-month' / 'build_m.py', d / 'ref-step6-build.py')
    elif stage == 'rekey':
        R.cp(g / 'page-images' / 'clean', d / 'page-images' / 'clean')
        R.cp(g / 'reference', d / 'reference')
        R.cp(INP / 'rekey_fields_q.md', d / 'rekey_fields_q.md')
    elif stage == 'adjudicate':
        R.cp(g / 'truth_q.json', d / 'truth_q.json')
        for k in sorted(work.glob('rekey*/truth-blind')):
            for f in k.glob('*.json'):
                R.cp(f, d / 'truth-blind' / f.name)
        R.cp(g / 'page-images' / 'clean', d / 'page-images' / 'clean')
        R.cp(g / 'reference', d / 'reference')
        R.cp(INP / 'rekey_fields_q.md', d / 'rekey_fields_q.md')


CLAUDE_BUILDER = 'claude-opus-5-5'


def run_claude(stage, d, prompt):
    """The same session through the Claude CLI on the subscription (step 7d amendment 1: Codex hit its usage limit).
    --setting-sources project in a folder outside every repo: no CLAUDE.md, no user hooks; no web tools."""
    log = d.parent / f'{stage}.jsonl'
    cmd = ['claude', '-p', '--model', CLAUDE_BUILDER, '--setting-sources', 'project', '--output-format', 'stream-json', '--verbose',
           '--allowedTools', 'Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep', '--disallowedTools', 'WebFetch', 'WebSearch']
    t0 = time.time()
    with open(log, 'w') as f:
        rc = subprocess.run(cmd, input=prompt, text=True, cwd=d, stdout=f, stderr=subprocess.STDOUT).returncode
    return rc, round(time.time() - t0), log


def claude_containment(log, d):
    """Flag tool calls that name a path outside the stage folder (blindness check), and report the served model."""
    flags, served = [], set()
    for ln in log.read_text(errors='replace').splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        if ev.get('type') == 'result':
            served |= set((ev.get('modelUsage') or {}).keys())
        for c in ((ev.get('message') or {}).get('content') or []) if ev.get('type') == 'assistant' else []:
            if isinstance(c, dict) and c.get('type') == 'tool_use':
                s = json.dumps(c.get('input'))
                for p in re.findall(r'(/(?:Users|private|tmp|var|Volumes)/[^\s"\'\\]+)', s):
                    if not p.startswith(str(d)) and not p.startswith(str(d.resolve())) and not p.startswith('/Applications/Google Chrome.app'):
                        flags.append(p)
                if re.search(r'(?<![\w.])\.\./', s):
                    flags.append('../ in tool input')
    return sorted(set(flags)), sorted(served)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('smoke', 'full'), required=True)
    ap.add_argument('--work', required=True, type=Path)
    ap.add_argument('--stage', required=True, choices=('designer', 'generator', 'render', 'rekey', 'adjudicate', 'freeze'))
    ap.add_argument('--quarter', type=int, help='rekey only: key this quarter in its own session (rekey-q<k>)')
    ap.add_argument('--builder', choices=('codex', 'claude'), default='codex', help='claude: step 7d amendment 1')
    ap.add_argument('--art', help='artifact folder holding 01-bank-data-brief.md and inputs/')
    a = ap.parse_args()
    global ART, INP
    if a.art:
        ART = DEMO.parent / 'artifacts' / a.art; INP = ART / 'inputs'; R.BRIEF = ART / '01-bank-data-brief.md'
    work = a.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    g = work / 'generator'
    rec = {'stage': a.stage, 'mode': a.mode, 'started': time.strftime('%Y-%m-%dT%H:%M:%S')}
    if a.stage in R.SESSION_HEAD:
        _, prompt = R.prompt_for(a.stage)
        name = f'rekey-q{a.quarter}' if a.stage == 'rekey' and a.quarter else a.stage
        d = R.fresh(work, name)
        stage_inputs(a.stage, a.mode, work, d)
        if a.stage == 'rekey' and a.quarter:    # this quarter's pages only; reference unchanged
            for p in (d / 'page-images' / 'clean').glob('*.png'):
                if not p.name.startswith(f'q{a.quarter}_'):
                    p.unlink()
        rec['inputs'] = sorted(str(p.relative_to(d)) for p in d.rglob('*') if p.is_file() and 'ref-run1-src' not in p.parts)
        if a.builder == 'claude':
            rc, secs, log = run_claude(name, d, prompt)
            outside, served = claude_containment(log, d)
            rec.update(builder=CLAUDE_BUILDER, served=served, rc=rc, seconds=secs, outside_paths=outside)
        else:
            rc, secs, log = R.run_codex(name, d, prompt)
            rec.update(rc=rc, seconds=secs, outside_paths=R.containment(log, d))
    elif a.stage == 'render':
        rec['render_rc'] = subprocess.run([sys.executable, 'build_q.py', '--render-only'], cwd=g).returncode
        imgs = g / 'page-images' / 'clean'; imgs.mkdir(parents=True, exist_ok=True)
        for pdf in sorted((g / 'clean').glob('*.pdf')):
            subprocess.run(['pdftoppm', '-r', '110', '-png', str(pdf), str(imgs / pdf.stem)], check=True)
        chk = subprocess.run([sys.executable, 'check_q.py'], cwd=g, capture_output=True, text=True)
        rec.update(check_rc=chk.returncode, check_out=chk.stdout[-3000:] + chk.stderr[-1500:],
                   pdfs=len(list((g / 'clean').glob('*.pdf'))), images=len(list(imgs.glob('*.png'))))
    elif a.stage == 'freeze':
        files = [g / 'truth_q.json'] + sorted((g / 'reference').glob('*')) + sorted((g / 'clean').glob('*.pdf'))
        frozen = {str(p.relative_to(g)): R.sha(p) for p in files}
        (g / 'frozen-q.json').write_text(json.dumps(frozen, indent=1) + '\n')
        rec['frozen_files'] = len(frozen)
    (work / f"{(name if a.stage in R.SESSION_HEAD else a.stage)}.record.json").write_text(json.dumps(rec, indent=1) + '\n')
    print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
