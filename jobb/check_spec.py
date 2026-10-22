#!/usr/bin/env python3
"""Brain-side check of a job B case spec, independent of the designer's own quota_check.

  check_spec.py <case_spec_b.json> [--smoke]
Exits non-zero on any failure.
"""
import collections, json, re, sys

FULL = {  # quotas-b.md, per split
    'supported_exact': 20, 'supported_reformatted_or_reworded': 20, 'supported_reworded': 10,
    'placeholder': 20, 'placeholder_paraphrased': 10, 'unknown_number': 20, 'no_number': 15,
    'wrong_property': 15, 'contradicted': 15, 'other_authority': 15, 'no_claim_ordinary': 30,
    'no_claim_bait': 15, 'hard': 15, 'remark_no_claim': 15,
}
TOK = r'[A-Za-z0-9]+(?:(?:\s?[/\-]\s?|[:.])[A-Za-z0-9]+)+|[A-Za-z]*\d[A-Za-z0-9]*'
LITERAL = {'n/a', 'tbd', 'pending', 'to follow', '-', '\u2013', '\u2014'}


def norm(tok):
    out = []
    for g in re.findall(r'[A-Za-z]+|\d+', tok):   # adjacent letter groups merge (R-W-M = RWM); digit groups stay bounded
        if g.isalpha() and out and out[-1].isalpha():
            out[-1] += g.upper()
        else:
            out.append(g.upper() if g.isalpha() else str(int(g)))
    return tuple(out)


def main():
    spec = json.load(open(sys.argv[1]))
    reg = {norm(r['afe_number']): r for r in spec['afe_register']}
    fails, counts, kinds = [], collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    words = collections.defaultdict(collections.Counter)
    ids, afes = collections.defaultdict(set), collections.defaultdict(set)
    for r in spec['afe_register']:
        afes[r['split']].add(norm(r['afe_number']))
    for d in spec['documents']:
        sp = d['split']; ids[sp].add(d['doc_id']); c = counts[sp]
        line_nos = {l['line_no'] for l in d['lines']}
        for r in d.get('remarks', []):
            if r['names_line'] not in line_nos:
                fails.append(f"{d['doc_id']} remark {r['remark_id']} names missing line {r['names_line']}")
            if r['remark_role'] == 'no_claim':
                c['remark_no_claim'] += 1
        for l in d['lines']:
            o, k, ps = l['outcome'], l['reference_kind'], l['placeholder_style']
            text = ' '.join([l.get('reference') or '', l.get('description') or ''])
            if re.search(r'\bAFE\b', text): words[sp]['AFE'] += 1
            if re.search(r'approv', text, re.I): words[sp]['approv'] += 1
            if o == 'supported' and k == 'exact': c['supported_exact'] += 1
            if o == 'supported' and k in ('reformatted', 'reworded'): c['supported_reformatted_or_reworded'] += 1
            if o == 'supported' and k == 'reworded': c['supported_reworded'] += 1
            if o == 'unsupported' and k == 'placeholder': c['placeholder'] += 1
            if o == 'unsupported' and ps == 'paraphrased': c['placeholder_paraphrased'] += 1
            if o == 'unsupported' and k == 'unknown_number': c['unknown_number'] += 1
            if o == 'unsupported' and k == 'no_number': c['no_number'] += 1
            if o == 'unsupported' and l['property_match'] == 'mismatch': c['wrong_property'] += 1
            if o == 'contradicted': c['contradicted'] += 1
            if o == 'other_authority': c['other_authority'] += 1; kinds[sp][l['authority_kind']] += 1
            if o == 'no_claim':
                bait = re.search(r'\bAFE\b|approv|authoriz', text, re.I)
                c['no_claim_bait' if bait else 'no_claim_ordinary'] += 1
            if l['difficulty'] == 'hard': c['hard'] += 1
            vals = [v.rsplit(':', 1)[-1].strip().lower() for v in re.split(r';', ' ; '.join([l.get('reference') or '', l.get('claim_text') or '']))]
            if ps == 'literal' and not any(v in LITERAL for v in vals):
                fails.append(f"{d['doc_id']}:{l['line_no']} literal placeholder not on the list: {l.get('reference')!r}")
            # register consistency
            claim_tok = [t for t in re.findall(TOK, ' '.join([l.get('claim_text') or '', l.get('reference') or ''])) if norm(t) in reg]
            if o in ('supported', 'contradicted') or l['property_match'] == 'mismatch':
                if not claim_tok:
                    fails.append(f"{d['doc_id']}:{l['line_no']} {o} cites no register AFE"); continue
                r = reg[norm(claim_tok[0])]
                want = 'declined' if o == 'contradicted' else 'approved'
                if r['status'] != want: fails.append(f"{d['doc_id']}:{l['line_no']} register status {r['status']} != {want}")
                same = r['property_no'] == l['property_no']
                if o == 'supported' and not same: fails.append(f"{d['doc_id']}:{l['line_no']} supported but property differs")
                if l['property_match'] == 'mismatch' and same: fails.append(f"{d['doc_id']}:{l['line_no']} mismatch but same property")
            if k == 'unknown_number' and claim_tok:
                fails.append(f"{d['doc_id']}:{l['line_no']} unknown_number is in the register")
    splits = sorted(counts)
    if len(splits) > 1:
        a, b = splits[:2]
        if ids[a] & ids[b]: fails.append('splits share document ids')
        if afes[a] & afes[b]: fails.append('splits share AFE numbers')
    if '--smoke' not in sys.argv:
        for sp in splits:
            for q, n in FULL.items():
                if counts[sp][q] < n: fails.append(f'{sp}: {q} {counts[sp][q]} < {n}')
            ok_kinds = [k for k, n in kinds[sp].items() if n >= 2]
            if len(ok_kinds) < 5 or not {'verbal_or_informal', 'prior_election'} <= set(ok_kinds):
                fails.append(f'{sp}: authority kinds {dict(kinds[sp])}')
            if words[sp]['AFE'] < 20: fails.append(f"{sp}: only {words[sp]['AFE']} lines print 'AFE' (word-ban regression)")
    out = {sp: dict(lines=sum(len(d['lines']) for d in spec['documents'] if d['split'] == sp), docs=len(ids[sp]),
                    counts=dict(counts[sp]), authority_kinds=dict(kinds[sp]), words=dict(words[sp])) for sp in splits}
    print(json.dumps(out, indent=1))
    print('FAILURES:' if fails else 'ALL PASS', *fails[:40], sep='\n')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
