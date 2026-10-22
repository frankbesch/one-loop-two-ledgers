#!/usr/bin/env python3
"""Step 7 arm A, banking: an analyst reviews a random share of certificates in full (ASSUMED SAMPLING RATE:
banking publishes no review-coverage baseline, research/05 §6). Configured from month/arm_a.py.

  arm_a_bank.py --quarters 3 4 [--share 0.45] [--draws 2000]
Per quarter, round(share × 12) certificates are drawn at random. The analyst holds every unit the key holds on a
drawn certificate, with the key's owner; every unit on an undrawn certificate posts unreviewed.
Outputs: q<k>/outcomes.json ("hold" = read by the analyst, as step 6's arm A counted it), meta.json,
expected.json (mean and 5th-95th percentile over the draws).
"""
import argparse, datetime, json, random, statistics
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]


def rows_for(units, picked):
    out = []
    for u in sorted(units, key=lambda u: (u['cert_id'], u['unit_id'])):
        seen = u['cert_id'] in picked
        hold = seen and u['disposition'] == 'hold'
        out.append(dict(quarter=u['quarter'], cert_id=u['cert_id'], unit_id=u['unit_id'], reviewed=seen,
                        disposition='hold' if seen else 'post', owner=u['owner'] if hold else 'none',
                        breach=u['breach'] if hold else 'no'))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(DEMO / 'synth-bank'))
    ap.add_argument('--quarters', type=int, nargs='+', required=True)
    ap.add_argument('--share', type=float, default=0.45)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--draws', type=int, default=2000)
    ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm = f"A-bank-assumed{int(round(a.share * 100))}-q{''.join(map(str, a.quarters))}-{stamp}"
    out = Path(a.out) if a.out else DEMO / 'runs' / 'bank' / arm
    out.mkdir(parents=True, exist_ok=True)
    expected = {}
    for q in a.quarters:
        units = [u for u in truth['units'] if u['quarter'] == q]
        certs = sorted({u['cert_id'] for u in units})
        k = round(a.share * len(certs))
        picked = set(random.Random(f'{a.seed}-A-{q}').sample(certs, k))
        (out / f'q{q}').mkdir(exist_ok=True)
        (out / f'q{q}' / 'outcomes.json').write_text(json.dumps(rows_for(units, picked), indent=1) + '\n')
        sil, rev = [], []
        for i in range(a.draws):
            pk = set(random.Random(f'A-draw-{q}-{i}').sample(certs, k))
            sil.append(sum(1 for u in units if u['disposition'] == 'hold' and u['cert_id'] not in pk))
            rev.append(sum(1 for u in units if u['cert_id'] in pk))
        pct = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
        expected[q] = dict(certificates_reviewed=k, silent=dict(mean=round(statistics.mean(sil), 2), p05=pct(sil, .05), p95=pct(sil, .95)),
                           units_reviewed=dict(mean=round(statistics.mean(rev), 2)), seeded=sorted(picked))
    (out / 'expected.json').write_text(json.dumps(dict(share=a.share, label='assumed sampling rate', draws=a.draws, quarters=expected), indent=1) + '\n')
    (out / 'meta.json').write_text(json.dumps(dict(arm=arm, quarters=a.quarters, share=a.share, label='assumed sampling rate',
                                                   backend='calculation', spend_usd=0.0, started=stamp), indent=1) + '\n')
    print(json.dumps(expected, indent=1)); print(f'outputs: {out}')


if __name__ == '__main__':
    main()
