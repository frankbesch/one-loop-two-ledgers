#!/usr/bin/env python3
"""Job B units from rendered PDFs: one bill line with its cells and every remark that names it.

Cells come from word bounding boxes (`pdftotext -bbox-layout`), bounded by the page's own column headers,
because plain text interleaves wrapped cells (smoke finding 5). A line wrap after an in-word hyphen is
rejoined without a space ("R-W-" / "M/58261/OC"). Remarks are joined to lines by the number they name,
never by remark order.

  units.py --corpus synth-jobb [--split calibration] [--check]   (--check compares every cell with truth_b.json)
"""
import argparse, json, re, subprocess, sys, xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

COLS = ['line_no', 'property', 'description', 'reference', 'vendor', 'gross', 'decimal', 'net']
TOL = 2.0
HEADER_NAMES = {'line': 'line_no', 'property': 'property', 'description': 'description', 'reference': 'reference',
                'vendor': 'vendor', 'gross': 'gross', 'decimal': 'decimal', 'net': 'net'}


def page_words(pdf):
    out = subprocess.run(['pdftotext', '-bbox-layout', str(pdf), '-'], capture_output=True, text=True, check=True, timeout=60).stdout
    pages = []
    for page in ET.fromstring(out).findall('.//{*}page'):
        pages.append([(float(w.get('xMin')), float(w.get('yMin')), float(w.get('xMax')), float(w.get('yMax')), w.text or '')
                      for w in page.findall('.//{*}word')])
    return pages


def visual_lines(words):
    """Group words into visual lines by baseline (yMax within 2 pt), each sorted by x."""
    lines = []
    for w in sorted(words, key=lambda w: (w[3], w[0])):
        if lines and abs(lines[-1][0] - w[3]) < 2.0:
            lines[-1][1].append(w)
        else:
            lines.append([w[3], [w]])
    return [sorted(ws, key=lambda w: w[0]) for _, ws in lines]


def join_lines(lines):
    """Words in reading order; a visual line that ends in an in-word hyphen joins the next without a space."""
    text = ''
    for ws in lines:
        part = ' '.join(w[4] for w in ws)
        if text and re.search(r'\w-$', text):
            text += part
        else:
            text += (' ' if text else '') + part
    return text.strip()


def parse_page(words):
    """-> (rows {line_no: {col: text}}, remark lines [(y, text)])."""
    head = [w for w in words if w[4] == 'Line' and any(v[4] == 'Property' and abs(v[3] - w[3]) < 2 for v in words)]
    if len(head) != 1:
        raise ValueError(f'table header found {len(head)} times')
    hy = head[0][3]
    header = sorted([w for w in words if abs(w[3] - hy) < 2], key=lambda w: w[0])
    if len(header) < len(COLS):
        raise ValueError(f'header has {len(header)} labels, need {len(COLS)}')
    names = [HEADER_NAMES.get(w[4].lower()) for w in header]
    if set(COLS) - set(names):
        raise ValueError(f'header labels {[w[4] for w in header]} miss {sorted(set(COLS) - set(names))}')
    starts = [w[0] - TOL for w in header]
    spans = dict(zip(names, zip(starts, starts[1:] + [10_000])))
    bounds = [spans[c] for c in COLS]   # in COLS order, whatever the printed column order
    first_x = min(starts) + 3 * TOL + 40
    end = min([w[1] for w in words if w[1] > hy and w[4] in ('Page', 'Gross') and w[0] < first_x] or [10_000])
    if end == 10_000:   # totals line not in the first columns: take the first 'total' word below the header
        end = min([w[1] for w in words if w[1] > hy and w[4].lower().startswith('total')] or [10_000])
    body = [w for w in words if hy + 1 < w[1] < end - 1]
    starts_y = sorted((w[1], int(w[4])) for w in body if bounds[0][0] <= w[0] < bounds[0][1] and w[4].isdigit())
    rows = {}
    for i, (y, n) in enumerate(starts_y):
        y_next = starts_y[i + 1][0] if i + 1 < len(starts_y) else end
        cell_words = defaultdict(list)
        for w in body:
            if y - 2 <= w[1] < y_next - 2:
                for c, (a, b) in zip(COLS, bounds):
                    if a <= w[0] < b:
                        cell_words[c].append(w); break
        rows[n] = {c: join_lines(visual_lines(cell_words[c])) for c in COLS}
    below = [w for w in words if w[1] > end + 4 and not w[4].startswith('SYNTHETIC')]
    foot = min([w[1] for w in words if w[4] == 'SYNTHETIC'] or [10_000])
    below = [w for w in below if w[1] < foot - 1]
    remark_lines = [(ws[0][1], ws) for ws in visual_lines(below)]
    return rows, remark_lines


def split_remarks(remark_lines):
    """Visual lines -> remarks; a remark starts at 'Line N:' and runs until the next one."""
    remarks, cur = [], None
    for _, ws in remark_lines:
        first = ' '.join(w[4] for w in ws[:2])
        m = re.match(r'Line (\d+):', first)
        if m:
            cur = {'names_line': int(m.group(1)), 'lines': [ws]}
            remarks.append(cur)
        elif cur:
            cur['lines'].append(ws)
    return [{'names_line': r['names_line'], 'text': join_lines(r['lines'])} for r in remarks]


def doc_units(pdf, doc_id):
    units, remarks = {}, []
    for p, words in enumerate(page_words(pdf), 1):
        rows, rlines = parse_page(words)
        for n, cells in rows.items():
            if n in units:
                raise ValueError(f'{doc_id}: line {n} appears twice')
            prop = (cells['property'].split() or [''])[0]
            units[n] = dict(doc_id=doc_id, line_no=n, page=p, property=prop, description=cells['description'],
                            reference=cells['reference'], vendor=cells['vendor'], remarks=[])
        for r in split_remarks(rlines):
            remarks.append(dict(r, page=p))
    unmatched = []
    for r in remarks:
        if r['names_line'] in units:
            units[r['names_line']]['remarks'].append(r)
        else:
            unmatched.append(r)
    for u in units.values():
        u['unmatched_remarks'] = unmatched   # Q14: a remark naming a missing line makes every unit incomplete
    return [units[n] for n in sorted(units)]


def load_units(corpus, split=None):
    corpus = Path(corpus)
    truth = json.loads((corpus / 'truth_b.json').read_text())
    split_of = {l['doc_id']: l['split'] for l in truth['lines']}
    out = []
    for pdf in sorted((corpus / 'clean').glob('*.pdf')):
        d = pdf.stem
        if split and split_of.get(d) != split:
            continue
        for u in doc_units(pdf, d):
            u['split'] = split_of.get(d)
            out.append(u)
    return out


def squash(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def check(units, truth):
    """Every extracted cell and remark equals the key's printed text."""
    tl = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
    tr = defaultdict(list)
    for r in truth['remarks']:
        tr[(r['doc_id'], r['names_line'])].append(squash(r['text']))
    bad, seen = [], set()
    for u in units:
        k = (u['doc_id'], u['line_no']); seen.add(k)
        t = tl.get(k)
        if not t:
            bad.append((k, 'extra line')); continue
        for f, tf in (('description', 'description'), ('reference', 'reference'), ('property', 'property_no')):
            if squash(u[f]) != squash(t.get(tf)):
                bad.append((k, f, u[f], t.get(tf)))
        if sorted(squash(r['text']) for r in u['remarks']) != sorted(tr.get(k, [])):
            bad.append((k, 'remarks', [r['text'] for r in u['remarks']], tr.get(k, [])))
        if u['unmatched_remarks']:
            bad.append((k, 'unmatched remarks'))
    want = {k for k in tl if k[0] in {u['doc_id'] for u in units}}
    bad += [(k, 'missing line') for k in sorted(want - seen)]
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--split')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    units = load_units(a.corpus, a.split)
    if a.out:
        Path(a.out).write_text(json.dumps(units, indent=1, ensure_ascii=False) + '\n')
    print(f'units: {len(units)} lines, {sum(len(u["remarks"]) for u in units)} remarks')
    if a.check:
        bad = check(units, json.loads((Path(a.corpus) / 'truth_b.json').read_text()))
        print('UNIT CHECK:', 'PASS' if not bad else f'FAIL ({len(bad)})')
        for b in bad[:20]:
            print(' ', b)
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
