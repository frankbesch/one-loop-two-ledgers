#!/usr/bin/env python3
"""H18: share of the platform reused by the banking mirror (10-banking-mirror-plan.md §7, inventory fixed there).

  reuse_count.py [--out bank/results/REUSE.json]
For each of the 25 pre-registered components: the step 6 file(s) it lives in, the banking file that uses it, and the
class. "unchanged" is verified, not asserted: the banking code must import the step 6 file (checked by text search)
and the step 6 file must still hash to its step 6 freeze value. Lines of code are the step 6 files' line counts.
"""
import argparse, hashlib, json, re
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
BANK = DEMO / 'bank'
FZ = {}
for f in ('month/frozen/FREEZE.json', 'month/frozen/FREEZE-ABC.json'):
    d = json.loads((DEMO / f).read_text())
    for k, h in d['hashes'].items():
        FZ[(DEMO / 'month' / 'frozen' / k).resolve()] = h

# (n, component, step 6 files, banking user, class, how)
INVENTORY = [
    (1, 'Freeze tooling', ['month/freeze_abc.py'], 'bank/freeze_bank.py', 'configured', 'same hash-manifest method, new file list'),
    (2, 'PDF word-box reader', ['jobb/units.py'], 'bank/bunits.py', 'unchanged', 'imports page_words, visual_lines'),
    (3, 'Format-map table parser', ['month/munits.py'], 'bank/bunits.py', 'rewritten', 'certificate sections, not bill columns'),
    (4, 'Typed-question adapter, general model', ['jobb/questions.py', 'month/mquestions.py'], 'bank/bquestions.py', 'configured', 'same prompt contract, new questions and options'),
    (5, 'Typed-question adapter, small model', ['jobb/questions.py'], 'bank/arm_c_bank.py', 'configured', 'choice-question body, new options'),
    (6, 'Decide-and-floor rule', ['jobb/questions.py'], 'bank/bquestions.py', 'configured', 'same rule, new option sets'),
    (7, 'Quote (evidence) check', ['jobb/codelayer.py'], 'bank/bquestions.py', 'configured', 'imports _squash; number-in-quote rule added'),
    (8, 'CLI call wrapper', ['jobb/run_b.py'], 'bank/run_bank.py', 'unchanged', 'imports ask_claude'),
    (9, 'Small-model HTTP backend', ['typed/jev_backend.py'], 'bank/arm_c_bank.py', 'unchanged', 'imports jev_backend'),
    (10, 'Replay', ['month/run_month.py'], 'bank/run_bank.py', 'rewritten', 'keyed by certificate and addback'),
    (11, 'Reference in force by date', ['month/mcode.py'], None, 'not used', 'credit agreements carry no dated versions here'),
    (12, 'Domain money rules', ['month/mcode.py'], 'bank/bcode.py', 'rewritten', 'covenant, addback, cure, signer, delivery rules'),
    (13, 'Claim-outcome table', ['month/mcode.py'], 'bank/bcode.py', 'rewritten', 'addback permitted / cap / window tests'),
    (14, 'Hold/post policy', ['month/mcode.py'], 'bank/bcode.py', 'rewritten', 'hold on error or breach, plus the owner rule'),
    (15, 'Ledger state across periods', ['month/mcode.py'], 'bank/run_bank.py', 'rewritten', 'cure history from the bank records'),
    (16, 'Close step with audit sample', ['month/run_month.py'], 'bank/run_bank.py', 'configured', 'same 5% audit, units instead of lines'),
    (17, 'Learning-step challenger and promotion', ['month/loop.py'], 'bank/run_bank.py', 'configured', 'same promotion rule, new replay'),
    (18, 'Floor sweep', ['month/set_floors_m.py'], 'bank/set_floors_b.py', 'configured', 'same policy and grid, one model'),
    (19, 'Per-period scorer', ['month/score_month.py'], 'bank/score_bank.py', 'rewritten', 'unit key, breach and owner metrics'),
    (20, 'Cross-arm table', ['month/compare_arms.py'], 'bank/score_bank.py', 'rewritten', 'folded into the bank scorer'),
    (21, 'Replication summary', ['month/replicate_summary.py'], 'bank/score_bank.py', 'rewritten', 'folded into the bank scorer'),
    (22, 'Arm A sampler', ['month/arm_a.py'], 'bank/arm_a_bank.py', 'configured', 'certificates instead of properties'),
    (23, 'Arm B runner with calculator tool', ['month/arm_b.py', 'month/calc_mcp.py'], 'bank/arm_b_bank.py', 'unchanged', 'imports claude_stream, calc_args; calc_mcp run as is'),
    (24, 'Arm C cascade runner', ['month/arm_c.py'], 'bank/arm_c_bank.py', 'configured', 'same flow, new options and arithmetic'),
    (25, 'Codex data-build runner', ['jobb/run_jobb.py', 'month/run_build.py'], 'bank/run_build.py', 'configured', 'run_jobb plumbing imported unchanged; stage inputs configured'),
]
IMPORT_NAME = {'jobb/units.py': r'import units|from units|BU\.U|units as U|import units as U', 'jobb/run_b.py': r'from run_b import',
               'typed/jev_backend.py': r'import jev_backend', 'month/arm_b.py': r'import arm_b', 'month/calc_mcp.py': r'calc_args'}


def loc(p):
    return sum(1 for ln in (DEMO / p).read_text().splitlines() if ln.strip() and not ln.strip().startswith('#'))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); a = ap.parse_args()
    rows, problems = [], []
    for n, comp, files, user, cls, how in INVENTORY:
        if cls == 'unchanged':
            for f in files:
                p = (DEMO / f).resolve()
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                if FZ.get(p) and FZ[p] != h:
                    problems.append(f'{comp}: {f} changed since the step 6 freeze')
                pat = IMPORT_NAME.get(f)
                if pat and not re.search(pat, (DEMO / user).read_text()):
                    problems.append(f'{comp}: {user} does not import {f}')
        if user and not (DEMO / user).exists():
            problems.append(f'{comp}: {user} missing')
        rows.append(dict(n=n, component=comp, step6=files, bank=user, cls=cls, how=how, loc=sum(loc(f) for f in files)))
    tot = len(rows)
    by = {c: [r for r in rows if r['cls'] == c] for c in ('unchanged', 'configured', 'rewritten', 'not used')}
    out = dict(components=tot, counts={c: len(v) for c, v in by.items()},
               share_unchanged=round(len(by['unchanged']) / tot, 3),
               share_unchanged_or_configured=round((len(by['unchanged']) + len(by['configured'])) / tot, 3),
               loc={c: sum(r['loc'] for r in v) for c, v in by.items()},
               loc_note='lines of the step 6 files behind each class; a file behind several components counts in each, so the classes overlap',
               rows=rows, problems=problems,
               new_banking_only=sorted(p.name for p in BANK.glob('*.py') if p.name not in {Path(r['bank']).name for r in rows if r['bank']}))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
