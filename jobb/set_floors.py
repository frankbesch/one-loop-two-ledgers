#!/usr/bin/env python3
"""Step 3: choose per-question floors for one backend from its logged calibration answers. No model call.

  set_floors.py <calibration run dir (rescored)> --out floors-<backend>.json

What-if sweep over Q2, Q7, Q9 floors in 0.40..0.95 (step 0.05). Q6 is a note to the person and never
changes an outcome, so it keeps the 0.60 prior. Per candidate, every logged answer is re-decided at the
floor, Q17 and Q16 are re-applied, and the line outcomes are compared with the key.
Policy, fixed before the sweep (Frank, 10-08, "set the floors and freeze"):
  1. fewest errors: final outcome wrong and not needs_review;
  2. then fewest lines at needs_review;
  3. then the highest floors (the most conservative point of the tie).
A line whose claim changes to `afe` under a lower Q2 floor, where the run never asked Q7 or Q9, cannot be
simulated: it counts as needs_review (conservative), and the count is reported.
"""
import argparse, itertools, json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import codelayer as C  # noqa: E402
import questions as Q  # noqa: E402
import units as U  # noqa: E402

GRID = [round(0.40 + 0.05 * i, 2) for i in range(12)]


def redecide(c, floor):
    """The value this logged answer takes at `floor` (same rule as questions.decide)."""
    if c['error'] or not c.get('answer'):
        return C.NEEDS_REVIEW
    p = c['answer']['probabilities']
    top = max(p, key=p.get)
    if top == C.NEEDS_REVIEW or p[top] < floor or c['answer'].get('answer') not in (None, top):
        return C.NEEDS_REVIEW
    if c['qid'] == 'Q9' and top.startswith('t') and top[1:].isdigit():
        return c['tokens'][int(top[1:]) - 1]
    return top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run = Path(a.run)
    meta = json.loads((run / 'meta.json').read_text())
    corpus = Path(meta['corpus'])
    truth = {(l['doc_id'], l['line_no']): l for l in json.loads((corpus / 'truth_b.json').read_text())['lines']}
    register = json.loads((corpus / 'reference' / 'afe_register.json').read_text())
    units = {(u['doc_id'], u['line_no']): u for u in U.load_units(corpus, meta['split'])}
    labels = Q.VOCAB[meta['vocab']]
    neg = meta['backend'] != 'jev'
    calls = defaultdict(list)
    for x in open(run / 'calls.jsonl'):
        c = json.loads(x)
        calls[(c['doc_id'], c['line_no'])].append(c)
    # attach each call's unit text, in the runner's order: line, remarks in order, then unit-level questions
    for k, cs in calls.items():
        u, ri = units[k], 0
        for c in cs:
            if c['qid'] == 'Q2' and c['target'] == 'line':
                c['_text'] = C.line_text(u, labels)
            elif c['qid'] == 'Q2':
                c['_text'] = C.remark_text(u['remarks'][ri], labels); ri += 1
            else:
                c['_text'] = C.unit_text(u, labels)

    def evaluate(f2, f7, f9):
        fl = {'Q2': f2, 'Q6': 0.60, 'Q7': f7, 'Q9': f9}
        err = rev = unsim = 0
        for k, cs in calls.items():
            u = units[k]
            vals = {}
            for c in cs:
                v = redecide(c, fl[c['qid']])
                tok = v if c['qid'] == 'Q9' and v not in ('none_of_these', C.NEEDS_REVIEW) else None
                q17 = C.q17(v, c['answer'].get('evidence', '') if c.get('answer') else '', c['_text'], tok, negative_needs_quote=neg) if not c['error'] else 'fail'
                vals.setdefault(c['qid'], []).append((v, q17))
            q2 = [v for v, _ in vals.get('Q2', [])]
            claim = C.combined_claim(q2)
            q8v = C.q8(u['reference'], u['description'])
            asked7, asked9 = 'Q7' in vals, 'Q9' in vals
            q7 = vals['Q7'][0][0] if asked7 else None
            if asked9:
                q9 = vals['Q9'][0][0]
            else:
                q9 = 'none_of_these' if not C.tokens(C.unit_text(u, labels)) else None
            if claim == 'afe' and ((not asked7 and q8v != 'placeholder') or q9 is None):
                unsim += 1; rev += 1
                continue
            fail = any(q17 == 'fail' for qid in ('Q2', 'Q7', 'Q9') for _, q17 in vals.get(qid, []))
            out, _ = C.q16(C.q14(u), fail, q2, q7, q8v, q9, register, u['property'])
            if out == C.NEEDS_REVIEW:
                rev += 1
            elif out != truth[k]['outcome']:
                err += 1
        return err, rev, unsim

    rows = []
    for f2, f7, f9 in itertools.product(GRID, GRID, GRID):
        e, r, s = evaluate(f2, f7, f9)
        rows.append((e, r, -f2, -f7, -f9, s))
    rows.sort()
    e, r, f2, f7, f9, s = rows[0]
    base = evaluate(0.60, 0.60, 0.60)
    pick = {'Q2': -f2, 'Q6': 0.60, 'Q7': -f7, 'Q9': -f9}
    # how wide is the zero-cost band around the pick: the floors with the same (errors, reviews)
    band = [x for x in rows if x[:2] == (e, r)]
    res = dict(backend=meta['backend'], model=meta.get('model'), from_run=meta['arm'], split=meta['split'],
               policy='min errors, then min needs_review, then highest floors', floors=pick,
               at_floors=dict(errors=e, needs_review=r, unsimulated=s),
               at_prior_060=dict(errors=base[0], needs_review=base[1], unsimulated=base[2]),
               tie_band={q: [min(-x[i] for x in band), max(-x[i] for x in band)] for q, i in (('Q2', 2), ('Q7', 3), ('Q9', 4))},
               grid=GRID)
    Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
