#!/usr/bin/env python3
"""Replay the job B question set (publishing one-loop-two-ledgers/02-question-set.md) on a built corpus.

No model is called. The code questions (Q8, Q10, Q11, Q16) run for real on the printed text. The model
questions (Q2, Q7, Q9) get perfect answers derived from the answer key, so a mismatch is a defect in the
code layer, the decision rows, or the data, never in a model. A code-only arm (no model questions) shows
which lines need a model at all.

  q_replay.py --truth truth_b.json --register afe_register.json [--out replay.json]
"""
import argparse, collections, json, re

PLACEHOLDERS = {'n/a', 'tbd', 'pending', 'to follow', '-', '\u2013', '\u2014'}   # Q8 list; blank is not on it
TOKEN = re.compile(r'[A-Za-z0-9]+(?:(?:\s?[/\-]\s?|[:.])[A-Za-z0-9]+)+|[A-Za-z]*\d[A-Za-z0-9]*')


def norm(tok):
    """Q10 normalizer: case, separators, and leading zeros; group boundaries stay (bounded match)."""
    out = []
    for g in re.findall(r'[A-Za-z]+|\d+', tok):   # adjacent letter groups merge (R-W-M = RWM); digit groups stay bounded
        if g.isalpha() and out and out[-1].isalpha():
            out[-1] += g.upper()
        else:
            out.append(g.upper() if g.isalpha() else str(int(g)))
    return tuple(out)


def tokens(text):
    return [t for t in TOKEN.findall(text or '') if re.search(r'\d', t) and not re.fullmatch(r'[\d,]+(\.\d+)?', t)]


def q8(ref):
    """The reference value, after any leading label such as 'Approved AFE:', is on the fixed list."""
    val = (ref or '').rsplit(':', 1)[-1].strip().lower()
    return 'placeholder' if val in PLACEHOLDERS else 'not_listed'


def q10(tok, reg):
    hits = [r for r in reg if norm(r['afe_number']) == norm(tok)]
    if len(hits) > 1:
        return 'ambiguous', None, None
    if not hits:
        return 'not_found', None, None
    h = hits[0]
    return h['status'], h, ('exact' if h['afe_number'] == tok else 'reformatted')


def q16(line_q2, remark_q2, q7, q8v, q9, reg, prop):
    """Rows 3-16 of the Q16 table (Q14 and Q17 pass by construction in this replay)."""
    calls = [line_q2] + remark_q2
    if 'needs_review' in calls:
        return 'needs_review', 'claim_unclear'
    claim = 'afe' if 'afe' in calls else 'other_authority' if 'other_authority' in calls else 'no_claim'
    if claim == 'no_claim':
        return 'no_claim', ''
    if claim == 'other_authority':
        return 'other_authority', 'q6'
    if q9 == 'needs_review':
        return 'needs_review', 'reference_unclear'
    if q9 != 'none_of_these':
        status, hit, kind = q10(q9, reg)
        if status == 'ambiguous':
            return 'needs_review', 'register_ambiguous'
        if status == 'declined':
            return 'contradicted', 'afe_declined'
        if status == 'not_found':
            return 'unsupported', 'unknown_number'
        if not hit.get('property_no') or not prop:
            return 'needs_review', 'property_unknown'
        if hit['property_no'] != prop:
            return 'unsupported', 'afe_other_property'
        return 'supported', kind
    if q8v == 'placeholder' or q7 == 'placeholder':
        return 'unsupported', 'placeholder'
    if q7 == 'no_reference':
        return 'unsupported', 'no_number'
    return 'needs_review', 'reference_conflict'


AUTH = {'claims_afe': 'afe', 'claims_other': 'other_authority', 'no_claim': 'no_claim'}
Q7 = {'placeholder': 'placeholder', 'no_number': 'no_reference', 'none': 'no_reference'}


def oracle(line, remarks, reg):
    """Perfect model answers from the key."""
    claim = AUTH[line['claim_type']]
    own = remarks.get(line['line_no'], [])
    if line['difficulty'] == 'hard':
        line_q2 = 'no_claim'
        remark_q2 = [claim if r['remark_role'] == 'claim' else 'no_claim' for r in own]
    else:
        line_q2, remark_q2 = claim, ['no_claim' if r['remark_role'] == 'no_claim' else claim for r in own]
    q7 = Q7.get(line['reference_kind'], 'number_given')
    q9 = 'none_of_these'
    if line['reference_kind'] in ('exact', 'reformatted', 'reworded', 'unknown_number'):
        unit = ' '.join([line.get('claim_text') or '', line.get('reference') or '', line.get('description') or ''] +
                        [r['text'] for r in own])
        toks = tokens(unit)
        known = [t for t in toks if any(norm(r['afe_number']) == norm(t) for r in reg)]
        q9 = (known or toks or ['needs_review'])[0]
    return line_q2, remark_q2, q7, q9


def code_only(line, remarks, reg):
    """No model: a register token anywhere in the unit is an AFE claim; else a literal placeholder; else no claim."""
    text = ' '.join([line.get('reference') or '', line.get('description') or ''] +
                    [r['text'] for r in remarks.get(line['line_no'], [])])
    for t in tokens(text):
        st, hit, _ = q10(t, reg)
        if st in ('approved', 'declined'):
            return q16('afe', [], 'number_given', 'not_listed', t, reg, line.get('property_no') or line.get('property'))[0]
    if q8(line.get('reference')) == 'placeholder':
        return 'unsupported'
    return 'no_claim'


def lines_of(truth):
    """Accept truth_b.json (flat or per document) or case_spec_b.json."""
    docs = truth['documents'] if isinstance(truth, dict) and 'documents' in truth else None
    if docs:
        for d in docs:
            yield d['doc_id'], d['lines'], d.get('remarks', [])
        return
    rows = truth if isinstance(truth, list) else truth.get('lines', [])
    rems = truth.get('remarks', []) if isinstance(truth, dict) else []
    by = collections.defaultdict(list)
    for r in rows:
        by[r['doc_id']].append(r)
    for doc, ls in by.items():
        yield doc, ls, [r for r in rems if r['doc_id'] == doc]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--truth', required=True)
    ap.add_argument('--register', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    truth, reg = json.load(open(a.truth)), json.load(open(a.register))
    reg = reg if isinstance(reg, list) else reg.get('afes', reg.get('afe_register', reg.get('entries')))
    res, mism, by_case = [], [], collections.Counter()
    for doc, lines, rems in lines_of(truth):
        rm = collections.defaultdict(list)
        for r in rems:
            rm[r['names_line']].append(r)
        for ln in lines:
            prop = ln.get('property_no') or ln.get('property')
            l2, r2, q7, q9 = oracle(ln, rm, reg)
            out, why = q16(l2, r2, q7, q8(ln.get('reference')), q9, reg, prop)
            co = code_only(ln, rm, reg)
            ok = out == ln['outcome']
            row = dict(doc_id=doc, line_no=ln['line_no'], truth=ln['outcome'], reference_kind=ln['reference_kind'],
                       q16=out, reason=why, q16_ok=ok, code_only=co, code_only_ok=co == ln['outcome'])
            if ln['reference_kind'] in ('exact', 'reformatted') and ln['outcome'] == 'supported' and why != ln['reference_kind']:
                row['q10_kind_mismatch'] = why
            if (ln.get('placeholder_style') == 'literal') != (q8(ln.get('reference')) == 'placeholder'):
                row['q8_mismatch'] = q8(ln.get('reference'))
            res.append(row)
            by_case[(ln['outcome'], ok, co == ln['outcome'])] += 1
            if not ok or 'q10_kind_mismatch' in row or 'q8_mismatch' in row:
                mism.append(row)
    summary = dict(lines=len(res), q16_correct=sum(r['q16_ok'] for r in res),
                   code_only_correct=sum(r['code_only_ok'] for r in res),
                   lines_needing_a_model=sum(not r['code_only_ok'] for r in res),
                   defects=mism,
                   by_outcome={f'{k[0]} | rows ok={k[1]} | code-only ok={k[2]}': v for k, v in sorted(by_case.items())})
    if a.out:
        json.dump(dict(summary=summary, rows=res), open(a.out, 'w'), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
