#!/usr/bin/env python3
"""Independent check of a step 6 case spec: every money-error label recomputed from the reference data.

  check_spec_m.py <case_spec_m.json> [--smoke]
Recomputes, per line and with the reference in force on the service date: wrong_decimal, wrong_rate,
nonconsent_property, afe_overrun (cumulative gross per AFE in billing order), duplicate (vendor invoice number
plus gross seen earlier), date_window. Every labelled error must be true and every `none` line clean.
Also checks arithmetic, format headers, remark targets, approval-claim consistency with the register, and quotas.
Exits non-zero on any failure.
"""
import calendar, datetime as dt, json, re, sys
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jobb'))
import codelayer as C  # noqa: E402

TOKEN = re.compile(r'[A-Za-z0-9]+(?:(?:\s?[/\-~]\s?|::?|[.])[A-Za-z0-9]+)+')


def akey(tok):
    """Format-free AFE key for this checker only: digit groups as ints plus the set of letter groups,
    so format A (CE08425~K) and format B (K::08425::CE) resolve to the same register entry."""
    g = re.findall(r'[A-Za-z]+|\d+', tok)
    return (tuple(str(int(x)) for x in g if x.isdigit()), frozenset(x.upper() for x in g if x.isalpha()))


def atoks(text):
    return [t for t in TOKEN.findall(text or '') if re.search(r'\d', t)]


def cited(text, register):
    """Register entries cited in text: each entry's groups in either order, with any spacing or separators
    between them and leading zeros allowed (checker only; the runner learns formats per operator)."""
    out = []
    for r in register:
        g = re.findall(r'[A-Za-z]+|\d+', r['afe_number'])
        parts = [(re.escape(x) if x.isalpha() else '0*' + str(int(x))) for x in g]
        sep = r'[^A-Za-z0-9]{0,6}'
        pats = [sep.join(parts), sep.join(reversed(parts))]
        if any(re.search(r'(?<![A-Za-z0-9])' + p + r'(?![A-Za-z0-9])', text or '', re.I) for p in pats):
            out.append(r)
    return out


MONEY = ['wrong_decimal', 'wrong_rate', 'nonconsent_property', 'afe_overrun', 'duplicate', 'date_window']


def d(s):
    return dt.date.fromisoformat(s)


def in_force(rows, key, val, when, date_field='effective'):
    """The latest row for key==val with date_field on or before `when`."""
    cands = [r for r in rows if r[key] == val and d(r[date_field]) <= when]
    return max(cands, key=lambda r: d(r[date_field])) if cands else None


def month_end(period):
    y, m = map(int, period.split('-'))
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def cents(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def main():
    spec = json.load(open(sys.argv[1]))
    smoke = '--smoke' in sys.argv
    ref = spec['reference']
    tol = Decimal(str(ref['joa_terms']['afe_overrun_tolerance']))
    window = int(ref['joa_terms']['exception_window_months'])
    periods = {m['month']: m['billing_period'] for m in spec['months']}
    reg = {akey(r['afe_number']): r for r in ref['afe_register']}
    fails, counts = [], defaultdict(Counter)
    cum = defaultdict(Decimal)
    seen = set()
    docs = sorted(spec['documents'], key=lambda x: (x['month'], x['doc_id']))
    fa, fb = spec['formats']['A']['headers'], spec['formats']['B']['headers']
    if set(fa.values()) & set(fb.values()):
        fails.append(f'format B reuses A header labels: {sorted(set(fa.values()) & set(fb.values()))}')
    if spec['formats']['A']['column_order'] == spec['formats']['B']['column_order']:
        fails.append('format B keeps format A column order')
    for doc in docs:
        mon = doc['month']; end = month_end(periods[mon])
        nums = {l['line_no'] for l in doc['lines']}
        for r in doc.get('remarks', []):
            if r['names_line'] not in nums:
                fails.append(f"{doc['doc_id']} remark {r['remark_id']} names missing line {r['names_line']}")
        for l in sorted(doc['lines'], key=lambda x: x['line_no']):
            k = f"{doc['doc_id']}:{l['line_no']}"
            sd = d(l['service_date'])
            # arithmetic
            if cents(Decimal(str(l['gross'])) * Decimal(str(l['owner_decimal']))) != cents(l['net_amount']):
                fails.append(f'{k} net arithmetic')
            if l.get('quantity') is not None and l.get('unit_rate') is not None:
                if cents(Decimal(str(l['quantity'])) * Decimal(str(l['unit_rate']))) != cents(l['gross']):
                    fails.append(f'{k} rate arithmetic')
            # recompute each money condition
            truth = set()
            doi = in_force(ref['doi'], 'property_no', l['property_no'], sd)
            if doi is None:
                fails.append(f'{k} no division order in force')
            elif abs(Decimal(str(doi['owner_decimal'])) - Decimal(str(l['owner_decimal']))) > Decimal('0.0000005'):
                truth.add('wrong_decimal')
            if l.get('unit_rate') is not None:
                svc = [r for r in ref['contract_rates'] if r['vendor'] == l['vendor'] and d(r['effective']) <= sd]
                svc = [r for r in svc if r['service'].lower() in (l['description'] or '').lower()] or svc
                if not svc:
                    fails.append(f'{k} no contract rate in force')
                else:
                    by = defaultdict(list)
                    for r in svc:
                        by[r['service']].append(r)
                    rates = {max(v, key=lambda r: d(r['effective']))['rate'] for v in by.values()}
                    if all(abs(Decimal(str(x)) - Decimal(str(l['unit_rate']))) > Decimal('0.005') for x in rates):
                        truth.add('wrong_rate')
            el = in_force(ref['elections'], 'property_no', l['property_no'], sd)
            if el and el['election'] == 'nonconsent':
                truth.add('nonconsent_property')
            toks = cited(' '.join([l.get('claim_text') or '', l.get('reference') or '']), ref['afe_register'])
            coded = cited(' '.join([l.get('reference') or '', l.get('description') or '', l.get('claim_text') or '']
                                  + [r['text'] for r in doc.get('remarks', []) if r['names_line'] == l['line_no']]), ref['afe_register'])
            if coded and coded[0]['status'] == 'approved':   # every line coded to an approved AFE counts toward its total
                a = coded[0]
                cum[a['afe_number']] += Decimal(str(l['gross']))
                if cum[a['afe_number']] > Decimal(str(a['approved_amount'])) * (1 + tol):
                    truth.add('afe_overrun')
            key = (l['vendor'], l['invoice_no'], str(cents(l['gross'])))
            if key in seen:
                truth.add('duplicate')
            seen.add(key)
            y, m = end.year, end.month - window
            while m <= 0:
                y, m = y - 1, m + 12
            earliest = dt.date(y, m, min(end.day, calendar.monthrange(y, m)[1]))
            if sd > end or sd < earliest:
                truth.add('date_window')
            lab = l['money_error']
            if lab == 'none' and truth:
                fails.append(f'{k} labelled none but recomputes {sorted(truth)}')
            elif lab != 'none' and lab not in truth:
                fails.append(f'{k} labelled {lab} but recomputes {sorted(truth) or "clean"}')
            elif lab != 'none' and len(truth) > 1:
                fails.append(f'{k} labelled {lab} but also {sorted(truth - {lab})}')
            counts[mon][lab] += 1
            counts[mon]['outcome:' + l['outcome']] += 1
            counts[mon]['variant'] += l['property_print'] == 'variant'
            counts[mon]['hard'] += l['difficulty'] == 'hard'
            # approval-claim consistency (job B rules)
            if l['outcome'] in ('supported', 'contradicted') or l['property_match'] == 'mismatch':
                if not toks:
                    fails.append(f"{k} {l['outcome']} cites no register AFE")
                else:
                    a = toks[0]
                    want = 'declined' if l['outcome'] == 'contradicted' else 'approved'
                    if a['status'] != want:
                        fails.append(f'{k} register status {a["status"]} != {want}')
                    if l['outcome'] == 'supported' and a['property_no'] != l['property_no']:
                        fails.append(f'{k} supported but AFE property differs')
            hold = l['money_error'] != 'none' or l['outcome'] in ('unsupported', 'contradicted', 'other_authority')
            if l['disposition'] != ('hold' if hold else 'post'):
                fails.append(f"{k} disposition {l['disposition']} != {'hold' if hold else 'post'}")
    tot = sum((counts[m] for m in counts), Counter())
    if smoke:
        for c in MONEY:
            if tot[c] < 1:
                fails.append(f'smoke: no {c} line')
    print(json.dumps({str(m): {k: v for k, v in sorted(c.items()) if v} for m, c in sorted(counts.items())}, indent=1))
    print('FAILURES:' if fails else 'ALL PASS', *fails[:40], sep='\n')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
