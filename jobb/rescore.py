#!/usr/bin/env python3
"""Re-derive a run's outcomes from its logged answers under the current code layer. Makes no model call.

  rescore.py <run dir> --out <new dir>
Model answers (value, top, probability, evidence) are taken as logged. Code recomputes Q17 with the rule for
the run's backend and re-applies Q16 rows. Use it when a code rule changes after a run (Frank, 10-08:
option 2, Jev nothing-found answers not checked against their span pick).
"""
import argparse, json, shutil, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codelayer as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((run / 'meta.json').read_text())
    register = json.loads((Path(meta['corpus']) / 'reference' / 'afe_register.json').read_text())
    neg = meta['backend'] != 'jev'
    calls, by_line, changed = [], defaultdict(list), 0
    for x in open(run / 'calls.jsonl'):
        c = json.loads(x)
        if c['error'] is None and c['value'] in C.NOTHING_FOUND:
            new = C.q17(c['value'], (c.get('answer') or {}).get('evidence', ''), '', None, negative_needs_quote=neg)
            if new != c['q17']:
                c['q17_logged'], c['q17'] = c['q17'], new
                changed += 1
        calls.append(c)
        by_line[(c['doc_id'], c['line_no'])].append(c)
    res = json.loads((run / 'outcomes.json').read_text())
    import units as U
    units = {(u['doc_id'], u['line_no']): u for u in U.load_units(meta['corpus'], meta['split'])}
    moved = 0
    for r in res:
        recs = by_line[(r['doc_id'], r['line_no'])]
        u = units[(r['doc_id'], r['line_no'])]
        r['q8'] = C.q8(u['reference'], u['description'])          # current Q8 rule
        r['code_only'] = C.code_only(u, register)[0]              # current code-only arm
        fail = any(c['q17'] == 'fail' for c in recs if c['qid'] in ('Q2', 'Q7', 'Q9'))
        outcome, reason = C.q16(r['q14'], fail, r['q2'], r['q7'], r['q8'], r['q9'], register, r['property'])
        if (outcome, reason) != (r['outcome'], r['reason']):
            r['outcome_logged'], r['reason_logged'] = r['outcome'], r['reason']
            moved += 1
        r.update(q17_fail=fail, outcome=outcome, reason=reason)
    with open(out / 'calls.jsonl', 'w') as f:
        for c in calls:
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    (out / 'outcomes.json').write_text(json.dumps(res, indent=1, ensure_ascii=False) + '\n')
    meta.update(arm=meta['arm'] + '+rescore', rescored_from=str(run), rescore_rule='q17 negative_needs_quote=%s; q8 widened; q16 code_model_conflict row' % neg,
                q17_changed=changed, outcomes_moved=moved)
    (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(f'q17 changed on {changed} calls; outcomes moved on {moved} lines -> {out}')


if __name__ == '__main__':
    main()
