#!/usr/bin/env python3
"""Claim-wording overlap between the calibration and scored splits (numbers masked).

  check_overlap.py <truth_b.json or case_spec_b.json> [--max-share 0.10]
Exits non-zero when the share of scored claim lines whose masked wording appears in calibration exceeds
--max-share. Literal placeholders (fixed values by definition) are left out.
"""
import collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import q_replay as q

LIT = re.compile(r'^([^:]*:\s*)?(N/A|TBD|Pending|To follow|-|–|—)$', re.I)


def mask(t):
    return re.sub(r'\s+', ' ', q.TOKEN.sub(lambda m: '<NUM>' if re.search(r'\d', m.group()) else m.group(), t)).strip().lower()


def lines(obj):
    if 'documents' in obj:
        for d in obj['documents']:
            for l in d['lines']:
                yield dict(l, split=d['split'])
    else:
        yield from obj['lines']


def main():
    obj = json.load(open(sys.argv[1]))
    cap = float(sys.argv[sys.argv.index('--max-share') + 1]) if '--max-share' in sys.argv else 0.10
    w = {s: collections.Counter() for s in ('calibration', 'scored')}
    for l in lines(obj):
        t = l.get('claim_text')
        if t and not LIT.match(t.strip()):
            w[l['split']][mask(t)] += 1
    shared = set(w['calibration']) & set(w['scored'])
    hit = sum(v for k, v in w['scored'].items() if k in shared)
    tot = sum(w['scored'].values())
    share = hit / tot if tot else 0.0
    print(json.dumps(dict(distinct_calibration=len(w['calibration']), distinct_scored=len(w['scored']),
                          shared_wordings=sorted(shared), scored_lines_reusing=hit, scored_claim_lines=tot,
                          share=round(share, 3), cap=cap), indent=1))
    sys.exit(0 if share <= cap else 1)


if __name__ == '__main__':
    main()
