#!/usr/bin/env python3
"""Score a step 6 arm-D run per month against the key (marks in publishing 03-full-month-brief.md §6).

  score_month.py <run dir>
Per month: lines, to a person (held), silent (posted but the key holds it: wrong and nobody reviews),
false holds (held but the key posts it), planted money errors caught (count and dollars), the right money
reason, the audit sample's estimate against the true silent count, and drift events.
Marks for months 3-6 (at least 15 targets each, else INCONCLUSIVE):
  silent at most 2 per month; planted dollars caught at least 90%; recovery within one month after the map.
"""
import json, sys
from collections import Counter
from pathlib import Path


def month_dirs(run):
    out = {}
    for d in sorted(Path(run).glob('m*')):
        if d.is_dir() and (d / 'outcomes.json').exists():
            out[d.name] = d
    return out


def main():
    run = Path(sys.argv[1])
    meta = json.loads((run / 'meta.json').read_text())
    truth = json.loads((Path(meta['corpus']) / 'truth_m.json').read_text())
    tl = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
    rep = {'arm': meta['arm'], 'backend': meta['backend'], 'mode': meta['mode'], 'months': {}}
    for tag, d in month_dirs(run).items():
        res = json.loads((d / 'outcomes.json').read_text())
        c = Counter()
        caught_d = total_d = 0.0
        for r in res:
            t = tl[(r['doc_id'], r['line_no'])]
            c['lines'] += 1
            c['held'] += r['disposition'] == 'hold'
            c['silent'] += r['disposition'] == 'post' and t['disposition'] == 'hold'
            c['false_hold'] += r['disposition'] == 'hold' and t['disposition'] == 'post'
            if t['money_error'] != 'none':
                c['money_targets'] += 1
                total_d += t['error_dollars']
                if r['disposition'] == 'hold':
                    c['money_caught'] += 1; caught_d += t['error_dollars']
                    c['money_right_reason'] += t['money_error'] in (r.get('money') or [])
            if t['outcome'] in ('unsupported', 'contradicted', 'other_authority'):
                c['claim_targets'] += 1
                c['claim_held'] += r['disposition'] == 'hold'
            if t['outcome'] == 'supported' and t['money_error'] == 'none':
                c['supported_clean'] += 1
                c['supported_clean_held'] += r['disposition'] == 'hold'
            c['drift_held'] += any(x.startswith('drift:') for x in r.get('reasons', []))
            c['right'] += r['disposition'] == t['disposition']
        close = json.loads((d / 'close.json').read_text()) if (d / 'close.json').exists() else {}
        rep['months'][tag] = dict(c, money_dollars_caught=round(caught_d, 2), money_dollars_total=round(total_d, 2),
                                  dollars_caught_share=round(caught_d / total_d, 4) if total_d else None,
                                  audit_n=close.get('audit_n'), audit_estimate_silent=close.get('audit_estimate_silent'))
    (run / 'score.json').write_text(json.dumps(rep, indent=1) + '\n')
    hdr = f"{'month':<10}{'lines':>6}{'held':>6}{'silent':>7}{'f.hold':>7}{'money':>9}{'$share':>8}{'reason':>8}{'drift':>7}{'audit est':>10}"
    print(rep['arm']); print(hdr)
    for tag, x in rep['months'].items():
        print(f"{tag:<10}{x['lines']:>6}{x['held']:>6}{x['silent']:>7}{x['false_hold']:>7}"
              f"{str(x.get('money_caught', 0)) + '/' + str(x.get('money_targets', 0)):>9}{str(x['dollars_caught_share']):>8}"
              f"{x.get('money_right_reason', 0):>8}{x['drift_held']:>7}{str(x['audit_estimate_silent']):>10}")


if __name__ == '__main__':
    main()
