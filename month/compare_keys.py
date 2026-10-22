#!/usr/bin/env python3
"""Compare the generator key with the blind key(s), line by line and label by label (step 6 data)."""
import collections, glob, json, sys
gen, blind_glob = sys.argv[1], sys.argv[2]
t = json.load(open(gen))
L = ['money_error', 'error_dollars', 'property_no', 'property_print', 'claim_type', 'reference_kind', 'placeholder_style',
     'property_match', 'authority_kind', 'outcome', 'difficulty', 'disposition']
tl = {(l['doc_id'], l['line_no']): l for l in t['lines']}
diff, rows, seen, per_month = collections.Counter(), [], set(), collections.Counter()
for f in glob.glob(blind_glob):
    if f.endswith('REPORT.md'):
        continue
    b = json.load(open(f))
    for l in b['lines']:
        k = (b['doc_id'], l['line_no']); g = tl.get(k); seen.add(k)
        if not g:
            rows.append((k, 'extra')); continue
        bad = False
        for x in L:
            gv, bv = g.get(x), l.get(x)
            if x == 'error_dollars' and isinstance(gv, (int, float)) and isinstance(bv, (int, float)) and abs(gv - bv) < 0.011:
                continue
            if gv != bv:
                diff[x] += 1; rows.append((k, x, gv, bv)); bad = True
        per_month[g['month']] += bad
months = {l['month'] for l in t['lines'] if (l['doc_id'], l['line_no']) in seen}
missing = [k for k, l in tl.items() if l['month'] in months and k not in seen]
print(json.dumps({'lines_compared': len(seen), 'missing': len(missing), 'label_diffs': dict(diff),
                  'lines_differing_per_month': dict(per_month)}, indent=1))
for r in rows[:25]:
    print(r)
