#!/usr/bin/env python3
"""Step 6 units: one bill line per unit from a rendered month document, using the owner's saved format maps.

A format map (flow step 5: "column mapping saved per operator format") holds each column's header label and
the AFE display pattern. A page is read with the first known format whose every header label is printed in its
header band. A document whose header matches no known format is a drift event: its lines come back
incomplete (Q14 fails closed) with the header fingerprint for the drift monitor.

  munits.py --corpus synth-month --formats month/formats_known.json [--month 1] [--check]
"""
import argparse, hashlib, json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jobb'))
import units as U  # noqa: E402  (word boxes, visual lines, hyphen-wrap join)

FIELDS = ['line_no', 'property', 'account', 'description', 'reference', 'vendor', 'invoice_no', 'service_date',
          'quantity', 'unit_rate', 'gross', 'decimal', 'net']
END_WORDS = (('Page', 'subtotal'), ('Document', 'total'))


def header_band(words):
    """Words between the document field rows (ending in ':') and the first data row: the shaded header."""
    lines = U.visual_lines(words)
    fields_y = max([ws[0][3] for ws in lines if any(w[4] in ('Document:', 'Owner:', 'Operator:', 'Vendor:') for w in ws)] or [0])
    band = [w for w in words if fields_y + 2 < w[3] < fields_y + 60]
    return band


def fingerprint(words):
    band = header_band(words)
    toks = sorted({w[4] for w in band if not re.fullmatch(r'[\d.,/:-]+', w[4])})
    return hashlib.sha256(' '.join(toks).encode()).hexdigest()[:12], toks


def match_format(words, formats):
    band = header_band(words)
    present = {w[4] for w in band}
    for fid, f in formats.items():
        need = {t for lab in f['headers'].values() for t in lab.split()}
        if need <= present:
            return fid
    return None


def column_starts(words, fmt):
    """x start per field: each label's first word, found left to right in the format's column order."""
    band = sorted(header_band(words), key=lambda w: (w[0], w[3]))
    starts, last_x = {}, -1
    for field in fmt['column_order']:
        first = fmt['headers'][field].split()[0]
        cands = [w for w in band if w[4] == first and w[0] > last_x + 1]
        if not cands:
            raise ValueError(f'header word {first!r} for {field} not found')
        w = min(cands, key=lambda w: w[0])
        starts[field] = w[0] - 2.0
        last_x = w[0]
    return starts


def parse_page(words, fmt):
    starts = column_starts(words, fmt)
    order = sorted(starts, key=starts.get)
    spans = {f: (starts[f], starts[order[i + 1]] if i + 1 < len(order) else 10_000) for i, f in enumerate(order)}
    band = header_band(words)
    top = max(w[3] for w in band) + 1
    lines = U.visual_lines([w for w in words if w[1] > top])
    end = 10_000
    for ws in lines:
        txt = [w[4] for w in ws]
        if any(tuple(txt[i:i + 2]) in END_WORDS for i in range(len(txt))) or re.match(r'Line \d+:', ' '.join(txt[:2])):
            end = min(end, ws[0][1]); break
    body = [w for w in words if top < w[1] < end - 1]
    a, b = spans['line_no']
    row_y = sorted((w[1], int(w[4])) for w in body if a <= w[0] < b and w[4].isdigit())
    rows = {}
    for i, (y, n) in enumerate(row_y):
        y2 = row_y[i + 1][0] if i + 1 < len(row_y) else end
        cells = defaultdict(list)
        for w in body:
            if y - 2 <= w[1] < y2 - 2:
                for f, (x0, x1) in spans.items():
                    if x0 <= w[0] < x1:
                        cells[f].append(w); break
        rows[n] = {f: U.join_lines(U.visual_lines(cells[f])) for f in FIELDS}
    foot = min([w[1] for w in words if w[4].startswith('SYNTHETIC') or w[4] == '·'] or [10_000])
    rem_lines = [(ws[0][1], ws) for ws in U.visual_lines([w for w in words if end - 1 <= w[1] < foot - 1])]
    return rows, U.split_remarks(rem_lines)


def num(s):
    s = (s or '').replace(',', '').strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def doc_units(pdf, doc_id, formats):
    """-> (units, event). event is None, or {'drift': fingerprint, 'tokens': [...]} when no known format fits."""
    pages = U.page_words(pdf)
    fid = match_format(pages[0], formats)
    if fid is None:
        fp, toks = fingerprint(pages[0])
        return [], {'doc_id': doc_id, 'drift': fp, 'header_tokens': toks}
    units, remarks = {}, []
    for p, words in enumerate(pages, 1):
        rows, rems = parse_page(words, formats[fid])
        for n, c in rows.items():
            units[n] = dict(doc_id=doc_id, line_no=n, page=p, format=fid, property_printed=c['property'],
                            account=c['account'], description=c['description'], reference=c['reference'],
                            vendor=c['vendor'], invoice_no=c['invoice_no'], service_date=c['service_date'],
                            quantity=num(c['quantity']), unit_rate=num(c['unit_rate']), gross=num(c['gross']),
                            owner_decimal=num(c['decimal']), net_amount=num(c['net']), remarks=[])
        remarks += [dict(r, page=p) for r in rems]
    unmatched = []
    for r in remarks:
        (units[r['names_line']]['remarks'] if r['names_line'] in units else unmatched).append(r)
    for u in units.values():
        u['unmatched_remarks'] = unmatched
    return [units[n] for n in sorted(units)], None


def load_month(corpus, month, formats):
    corpus = Path(corpus)
    out, events = [], []
    for pdf in sorted((corpus / 'clean').glob(f'm{month}_*.pdf')):
        us, ev = doc_units(pdf, pdf.stem, formats)
        for u in us:
            u['month'] = month
        out += us
        if ev:
            ev['month'] = month; events.append(ev)
    return out, events


def check(units, truth):
    tl = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
    bad = []
    for u in units:
        t = tl.get((u['doc_id'], u['line_no']))
        if not t:
            bad.append((u['doc_id'], u['line_no'], 'extra')); continue
        for f in ('property_printed', 'description', 'reference', 'vendor', 'invoice_no', 'service_date'):
            if U.squash(str(u[f] or '')) != U.squash(str(t.get(f) or '')):
                bad.append((u['doc_id'], u['line_no'], f, u[f], t.get(f)))
        for f in ('gross', 'owner_decimal', 'net_amount', 'quantity', 'unit_rate'):
            tv = t.get(f)
            if (tv is None) != (u[f] is None) or (tv is not None and abs(float(tv) - u[f]) > 1e-6):
                bad.append((u['doc_id'], u['line_no'], f, u[f], tv))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--formats', required=True)
    ap.add_argument('--month', type=int)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    formats = json.loads(Path(a.formats).read_text())
    truth = json.loads((Path(a.corpus) / 'truth_m.json').read_text())
    months = [a.month] if a.month else sorted({l['month'] for l in truth['lines']})
    allu, allev = [], []
    for m in months:
        us, ev = load_month(a.corpus, m, formats)
        allu += us; allev += ev
        print(f'month {m}: {len(us)} lines, {sum(len(u["remarks"]) for u in us)} remarks, drift events {len(ev)}')
    if a.check:
        bad = check(allu, truth)
        want = sum(1 for l in truth['lines'] if l['month'] in months)
        print('UNIT CHECK:', 'PASS' if not bad and len(allu) == want else f'FAIL ({len(bad)} cell diffs, {len(allu)}/{want} lines)')
        for b in bad[:15]:
            print(' ', b)


if __name__ == '__main__':
    main()
