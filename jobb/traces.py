#!/usr/bin/env python3
"""Write a short trace file for a person to read before floors are set (step 3, PF-0151 reply 2).

  traces.py <run dir> [--n 10] [--seed 7]
Picks lines across outcome classes, wrong answers first, then a seeded random fill. For each line it shows
the key, every model answer with its top probability and quote, the Q17 result, and code's outcome.
Writes <run dir>/TRACES.md.
"""
import argparse, json, random
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    run = Path(a.run)
    meta = json.loads((run / 'meta.json').read_text())
    res = json.loads((run / 'outcomes.json').read_text())
    truth = json.loads((Path(meta['corpus']) / 'truth_b.json').read_text())
    tl = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
    calls = defaultdict(list)
    for x in open(run / 'calls.jsonl'):
        c = json.loads(x)
        calls[(c['doc_id'], c['line_no'])].append(c)
    rng = random.Random(a.seed)
    wrong = [r for r in res if r['outcome'] != tl[(r['doc_id'], r['line_no'])]['outcome']]
    right = [r for r in res if r not in wrong]
    rng.shuffle(wrong); rng.shuffle(right)
    by_class = defaultdict(list)
    for r in right:
        by_class[tl[(r['doc_id'], r['line_no'])]['outcome']].append(r)
    pick = wrong[: max(1, a.n // 2)]
    while len(pick) < a.n and any(by_class.values()):
        for k in sorted(by_class):
            if by_class[k] and len(pick) < a.n:
                pick.append(by_class[k].pop())
    out = [f"# Traces: {meta['arm']}", '',
           f"{len(pick)} lines: {min(len(wrong), max(1, a.n // 2))} wrong outcomes first (of {len(wrong)}), then one per class. Seed {a.seed}.",
           'Read each: is the model answer defensible from the quote? Note visible failure patterns before setting floors.', '']
    for r in pick:
        t = tl[(r['doc_id'], r['line_no'])]
        mark = 'RIGHT' if r['outcome'] == t['outcome'] else 'WRONG'
        out += [f"## {r['doc_id']} line {r['line_no']}: {mark}",
                f"- Key: {t['outcome']} ({t['claim_type']}, {t['reference_kind']}, {t['difficulty']}); claim text: {t.get('claim_text')!r}",
                f"- Code: {r['outcome']} ({r['reason']}); code-only arm: {r['code_only']}"]
        for c in calls[(r['doc_id'], r['line_no'])]:
            ev = ((c.get('answer') or {}).get('evidence') or '')[:120]
            p = f"{c['p_top']:.2f}" if c.get('p_top') is not None else '-'
            out.append(f"- {c['qid']} ({c['target']}): **{c['value']}** top={c['top']} p={p} Q17={c['q17']}"
                       + (f" error={c['error']}" if c['error'] else '') + f" | quote: {ev!r}")
        out.append('')
    (run / 'TRACES.md').write_text('\n'.join(out) + '\n')
    print(f"wrote {run / 'TRACES.md'} ({len(pick)} lines)")


if __name__ == '__main__':
    main()
