"""Step 7: code reads one compliance certificate (the template's fixed labels; 01-bank-data-brief.md, generator prompt).

Reused unchanged from step 6: jobb/units.py (page_words, visual_lines, join_lines: word boxes from local text).
Scalars come from the labelled lines; the addback table is cut into columns by its header words, as step 6 cut a
bill's columns, and a wrapped description is rejoined. Raises on anything it cannot read, so the runner fails closed.
"""
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jobb'))
import units as U  # noqa: E402

DATE = r'(\d{4}-\d{2}-\d{2})'
NUM = r'\(?-?\$?\s?[\d,]+\)?'
HEAD = ['No.', 'Description', 'Category', 'Amount', 'Action']


def money(s):
    s = s.replace('$', '').replace(',', '').replace(' ', '').strip()
    neg = s.startswith('(') or s.startswith('-')
    return -int(s.strip('()-')) if neg else int(s.strip('()-'))


def lines_text(pages):
    out = []
    for p, words in enumerate(pages):
        for ws in U.visual_lines(words):
            out.append((p, ws[0][3], ' '.join(w[4] for w in ws), ws))
    return out


def find(lines, pat, what):
    for _, _, t, _ in lines:
        m = re.search(pat, t)
        if m:
            return m
    raise ValueError(f'{what} not found')


def addback_table(pages, lines):
    hdr = [(p, y, ws) for p, y, t, ws in lines if all(h in t.split() or h in t for h in HEAD) and t.strip().startswith('No.')]
    if not hdr:
        hdr = [(p, y, ws) for p, y, t, ws in lines if all(h in t for h in HEAD)]
    if not hdr:
        return []
    p0, y0, hws = hdr[0]
    xs = {}
    for h in HEAD:
        w = next(w for w in hws if w[4] == h or w[4].startswith(h))
        xs[h] = w[0] - 2.0
    order = sorted(xs, key=xs.get)
    span = {h: (xs[h], xs[order[i + 1]] if i + 1 < len(order) else 10_000) for i, h in enumerate(order)}
    rows, cur = [], None
    stop = re.compile(r'^(Adjusted EBITDA|Equity cure|Officer certification|Schedule 2|Date received|Applied to)')
    for p, y, t, ws in lines:
        if (p, y) <= (p0, y0):
            continue
        if stop.search(t.strip()):
            break
        first = ws[0]
        if span['No.'][0] <= first[0] < span['No.'][1] and first[4].isdigit():
            cur = {'no': int(first[4]), 'words': [w for w in ws[1:]]}
            rows.append(cur)
        elif cur is not None:
            cur['words'] += ws
    out = []
    for r in rows:
        # step 7d: a right-aligned Amount (or a date) can start left of its header word. Right of the description, a
        # money token belongs to Amount and a date token to Action, wherever it starts; category labels hold neither.
        right = span['Category'][0]
        moved = {id(w): h for w in r['words'] if w[0] >= right for h, pat in (('Amount', r'^\$?[\d,]{3,}$'), ('Action', DATE + '$'))
                 if re.match(pat, w[4])}
        cells = {h: [w for w in r['words'] if (moved.get(id(w)) == h) or (id(w) not in moved and span[h][0] <= w[0] < span[h][1])]
                 for h in HEAD if h != 'No.'}
        txt = {h: U.join_lines(U.visual_lines(cells[h])) for h in cells}
        amt = re.search(r'[\d,]{3,}', txt['Amount'])
        dte = re.search(DATE, txt['Action'])
        if not (amt and dte):
            raise ValueError(f'addback {r["no"]}: amount or date unreadable')
        out.append(dict(addback_no=r['no'], description=txt['Description'], category_printed=txt['Category'],
                        amount=money(amt.group(0)), action_date=dte.group(1)))
    return out


def read_certificate(pdf, quarter):
    pages = U.page_words(pdf)
    lines = lines_text(pages)
    full = '\n'.join(t for _, _, t, _ in lines)
    cert = dict(cert_id=Path(pdf).stem, quarter=quarter)
    cert['borrower'] = find(lines, r'^Borrower:\s*(.+?)\s*$', 'borrower').group(1).strip()
    cert['delivery_date'] = find(lines, r'Date delivered:\s*' + DATE, 'delivery date').group(1)
    cert['signer_title'] = find(lines, r'^Title:\s*(.+?)\s*$', 'signer title').group(1).strip()
    cert['ebitda'] = {'unadjusted': money(find(lines, r'^Unadjusted EBITDA\s+(' + NUM + ')', 'unadjusted EBITDA').group(1))}
    m = re.search(r'(?m)^\s*Adjusted EBITDA\s*\n?\s*(' + NUM + ')', full)
    if not m:
        raise ValueError('adjusted EBITDA not found')
    cert['adjusted_ebitda_printed'] = money(m.group(1))
    cert['addbacks'] = addback_table(pages, lines)
    m = re.search(r'Equity cure contribution:\s*(' + NUM + ')', full)
    cert['cure'] = None
    if m:
        d = re.search(r'Date received:\s*' + DATE, full)
        cert['cure'] = dict(amount=money(m.group(1)), date=d.group(1) if d else None)
    m = re.search(r'Officer certification of cost savings:(.*?)(?:\n\s*\n|\nSchedule 2|\nName:|$)', full, re.S)
    cert['certification_text'] = re.sub(r'\s+', ' ', m.group(1)).strip() if m else None
    covs = []
    for lab, kind, word in (('Total leverage', 'leverage', 'Maximum'), ('Interest coverage', 'interest_coverage', 'Minimum')):
        m = find(lines, lab + r'\s+(' + NUM + r')\s+(' + NUM + r')\s+([\d.]+)x\s+' + word + r'\s+([\d.]+)x\s+(Pass|Fail)', lab)
        covs.append(dict(covenant=kind, input=money(m.group(1)), adjusted=money(m.group(2)), ratio_printed=float(m.group(3)),
                         threshold_printed=float(m.group(4)), status_printed=m.group(5).lower()))
    cert['covenants'] = covs
    return cert
