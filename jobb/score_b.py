#!/usr/bin/env python3
"""Score a job B run against the key: the three marks, per-question accuracy, review load, cost.

  score_b.py <run dir> [--compare <run dir>]     --compare: D-295 label-swap reading against another arm

Marks (01-brief.md §5; at least 15 targets each, else INCONCLUSIVE, declared before any run):
  M1 silent misses: unsupported or contradicted lines that end supported or no_claim; at most 2 per set
  M2 false alarms: supported lines that end anything but supported (needs_review counts); at most 10%
  M3 value over code: of the lines code alone gets wrong, model plus code gets at least 80% right
Label swap (D-295): escalation = a model answer at needs_review (top below the floor or top needs_review).
  Revisit trigger: any question's escalation moves 20 points or more between the two vocabularies.
"""
import argparse, json, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codelayer as C  # noqa: E402

MIN_TARGETS = 15
AUTH = {'claims_afe': 'afe', 'claims_other': 'other_authority', 'no_claim': 'no_claim'}
Q7_TRUTH = {'placeholder': 'placeholder', 'no_number': 'no_reference', 'none': 'no_reference'}


def load(run):
    run = Path(run)
    meta = json.loads((run / 'meta.json').read_text())
    res = json.loads((run / 'outcomes.json').read_text())
    calls = [json.loads(x) for x in open(run / 'calls.jsonl')]
    truth = json.loads((Path(meta['corpus']) / 'truth_b.json').read_text())
    return meta, res, calls, truth


def mark(name, n_targets, value, ok, rule):
    if n_targets < MIN_TARGETS:
        verdict = 'INCONCLUSIVE'
    else:
        verdict = 'PASS' if ok else 'FAIL'
    return dict(mark=name, targets=n_targets, value=value, rule=rule, verdict=verdict)


def score(meta, res, calls, truth):
    tl = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
    rows = [(r, tl[(r['doc_id'], r['line_no'])]) for r in res]
    unsup = [(r, t) for r, t in rows if t['outcome'] in ('unsupported', 'contradicted')]
    m1 = sum(1 for r, t in unsup if r['outcome'] in ('supported', 'no_claim'))
    sup = [(r, t) for r, t in rows if t['outcome'] == 'supported']
    m2 = sum(1 for r, t in sup if r['outcome'] != 'supported')
    tgt = [(r, t) for r, t in rows if r['code_only'] != t['outcome']]
    m3 = sum(1 for r, t in tgt if r['outcome'] == t['outcome'])
    m3_routed = sum(1 for r, t in tgt if r['outcome'] in (t['outcome'], C.NEEDS_REVIEW))
    marks = [
        mark('M1 silent misses', len(unsup), m1, m1 <= 2, '<= 2'),
        mark('M2 false alarms on supported', len(sup), f'{m2}/{len(sup)}' + (f' = {m2 / len(sup):.1%}' if sup else ''),
             bool(sup) and m2 / len(sup) <= 0.10, '<= 10%'),
        mark('M3 value over code', len(tgt), f'{m3}/{len(tgt)}' + (f' = {m3 / len(tgt):.1%}' if tgt else '') + f' (right or routed: {m3_routed})',
             bool(tgt) and m3 / len(tgt) >= 0.80, '>= 80% right'),
    ]
    # per question, against the key
    perq = defaultdict(Counter)
    for c in calls:
        t = tl[(c['doc_id'], c['line_no'])]
        if c['qid'] == 'Q2' and c['target'] == 'line':
            want = 'no_claim' if t['difficulty'] == 'hard' else AUTH[t['claim_type']]
        elif c['qid'] == 'Q2':
            continue   # remark roles are scored through the line outcome
        elif c['qid'] == 'Q6':
            want = t['authority_kind']
        elif c['qid'] == 'Q7':
            want = Q7_TRUTH.get(t['reference_kind'], 'number_given')
        else:
            want = None
        k = perq[c['qid']]
        k['asked'] += 1
        k['needs_review'] += c['value'] == C.NEEDS_REVIEW
        k['errors'] += bool(c['error'])
        k['q17_fail'] += c['q17'] == 'fail'
        if want is not None and c['value'] != C.NEEDS_REVIEW:
            k['answered'] += 1
            k['right'] += c['value'] == want
    outcomes = Counter((t['outcome'], r['outcome']) for r, t in rows)
    review = sum(1 for r, _ in rows if r['outcome'] != 'no_claim' and r['outcome'] != 'supported')
    return dict(arm=meta['arm'], backend=meta['backend'], mode=meta['mode'], vocab=meta['vocab'], lines=len(rows),
                correct=sum(1 for r, t in rows if r['outcome'] == t['outcome']),
                needs_review=sum(1 for r, _ in rows if r['outcome'] == C.NEEDS_REVIEW),
                sent_to_person=review, marks=marks, per_question={q: dict(v) for q, v in sorted(perq.items())},
                confusion={f'{a} -> {b}': n for (a, b), n in sorted(outcomes.items())},
                cost={k: meta.get(k) for k in ('requests', 'live_calls', 'spend_usd', 'spend_bound_usd', 'wall_s',
                                               'claude_version', 'claude_auth_method', 'model')})


def escalation(calls):
    e = defaultdict(Counter)
    for c in calls:
        e[c['qid']]['asked'] += 1
        e[c['qid']]['escalated'] += c['value'] == C.NEEDS_REVIEW
    return {q: v['escalated'] / v['asked'] for q, v in e.items() if v['asked']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--compare')
    a = ap.parse_args()
    meta, res, calls, truth = load(a.run)
    rep = score(meta, res, calls, truth)
    if a.compare:
        m2, _, c2, _ = load(a.compare)
        e1, e2 = escalation(calls), escalation(c2)
        moves = {q: round(100 * (e2.get(q, 0) - e1.get(q, 0)), 1) for q in sorted(set(e1) | set(e2))}
        rep['label_swap'] = dict(base=meta['arm'], other=m2['arm'], escalation_base=e1, escalation_other=e2,
                                 points_moved=moves, revisit=any(abs(v) >= 20 for v in moves.values()))
    Path(a.run, 'score.json').write_text(json.dumps(rep, indent=1) + '\n')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
