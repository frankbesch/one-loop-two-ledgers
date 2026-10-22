#!/usr/bin/env python3
"""Independent gate checks; PDF checks exclusively use pdftotext word boxes."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from build_m import ROOT, FIELDS, WIDTHS, LEDGER_FIELDS, printed

D = lambda x: Decimal(str(x))
MONEY = 'wrong_decimal wrong_rate nonconsent_property afe_overrun duplicate date_window'.split()
OUTCOMES = 'supported unsupported contradicted other_authority no_claim'.split()
LABELS = 'money_error error_dollars claim_type reference_kind placeholder_style property_match authority_kind outcome difficulty property_print disposition'.split()
RESULTS = {f'G{i}': [] for i in range(1, 9)}
NOTES = []
RECOUNTS = {}


def require(g, ok, message):
    if not ok:
        RESULTS[g].append(message)


def unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f'Duplicate JSON field: {k}')
        result[k] = v
    return result


def read(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def cents(value):
    return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def effective(rows, day, **matches):
    rows = [r for r in rows if all(r.get(k) == v for k, v in matches.items()) and r['effective'] <= day]
    if not rows:
        raise ValueError(f'No effective reference for {matches} on {day}')
    return max(rows, key=lambda r: r['effective'])


def afe_id(text):
    m = re.search(r'CE\s*0*(\d+)\s*~\s*K|K::0*(\d+)::CE', text, re.I)
    return int(m.group(1) or m.group(2)) if m else None


def text_of(el):
    return ''.join(el.itertext())


def source_checks(s, truth, manifest):
    expected = {'lines': [{'month': d['month'], 'doc_id': d['doc_id'], **l} for d in s['documents'] for l in d['lines']],
                'remarks': [{'month': d['month'], 'doc_id': d['doc_id'], **r} for d in s['documents'] for r in d['remarks']]}
    require('G2', truth == expected, 'Truth fields, values, labels, order, or entry counts differ from spec.')
    require('G2', manifest['spec_sha256'] == hashlib.sha256((ROOT / 'case_spec_m.json').read_bytes()).hexdigest(), 'Spec hash mismatch.')
    for l in truth['lines']:
        require('G2', all(k in l and not isinstance(l[k], (list, dict)) and l[k] is not None for k in LABELS), f'{l["doc_id"]}/{l["line_no"]}: label cardinality.')
    docs = {d['doc_id']: d for d in manifest['documents']}
    require('G2', len(docs) == len(manifest['documents']) == len(s['documents']), 'Manifest document count mismatch.')
    for d in s['documents']:
        md = docs[d['doc_id']]
        root = ET.fromstring((ROOT / md['source']).read_text())
        require('G2', md['source_sha256'] == hashlib.sha256((ROOT / md['source']).read_bytes()).hexdigest(), f'{d["doc_id"]}: source hash mismatch.')
        pages = root.findall('.//section')
        require('G7', len(pages) == d['pages'], f'{d["doc_id"]}: source page count.')
        seen = []
        for p, page in enumerate(pages, 1):
            f = s['formats'][d['format']]
            require('G2', [text_of(th) for th in page.findall('.//th')] == [f['headers'][k] for k in f['column_order']], f'{d["doc_id"]}/{p}: source headers.')
            for row in page.findall('.//tbody/tr'):
                n = int(row.attrib['data-line'])
                line = next(l for l in d['lines'] if l['line_no'] == n)
                seen.append(n)
                require('G7', line['page'] == p, f'{d["doc_id"]}/{n}: wrong source page.')
                cells = row.findall('td')
                require('G2', [c.attrib['data-field'] for c in cells] == [FIELDS.get(k, k) for k in f['column_order']], f'{d["doc_id"]}/{n}: printed field names/order.')
                require('G2', [text_of(c) for c in cells] == [printed(line[FIELDS.get(k,k)]) for k in f['column_order']], f'{d["doc_id"]}/{n}: printed source values.')
            rr = [text_of(r) for r in page.findall('.//p[@class="remark"]')]
            require('G2', rr == [r['text'] for r in d['remarks'] if r['page'] == p], f'{d["doc_id"]}/{p}: source remarks.')
        require('G7', seen == [l['line_no'] for l in d['lines']] and len(seen) == len(set(seen)), f'{d["doc_id"]}: missing/duplicate source rows.')
        for r in d['remarks']:
            require('G7', r['names_line'] in seen and r['text'].startswith(f'Line {r["names_line"]}:'), f'{d["doc_id"]}: remark target.')
        totals = root.findall('.//div[@class="totals"]')
        require('G4', len(totals) == 1, f'{d["doc_id"]}: totals cardinality.')
        for field, attr in [('gross', 'gross'), ('net_amount', 'net')]:
            amount = sum((D(l[field]) for l in d['lines']), D(0))
            require('G4', D(md[attr + '_total']) == amount and D(totals[0].attrib['data-' + attr]) == amount, f'{d["doc_id"]}: {field} total.')
            require('G4', f'Document total ({attr}): {amount}' in text_of(totals[0]), f'{d["doc_id"]}: printed {field} total.')
        for l in d['lines']:
            require('G4', cents(D(l['gross']) * D(l['owner_decimal'])) == D(l['net_amount']), f'{d["doc_id"]}/{l["line_no"]}: net arithmetic.')
            if l['quantity'] is not None or l['unit_rate'] is not None:
                require('G4', l['quantity'] is not None and l['unit_rate'] is not None and D(l['quantity']) * D(l['unit_rate']) == D(l['gross']), f'{d["doc_id"]}/{l["line_no"]}: rate arithmetic.')
    for name, value in s['reference'].items():
        require('G3', read(ROOT / 'reference' / (name + '.json')) == value, f'Reference {name} differs from spec.')
    for k in range(2, 7):
        expected_ledger = [{field: ({'doc_id': d['doc_id'], **l})[field] for field in LEDGER_FIELDS}
                           for d in s['documents'] if d['month'] < k for l in d['lines']]
        require('G3', read(ROOT / 'reference' / f'prior_ledger_m{k}.json') == expected_ledger, f'Prior ledger month {k} differs from printed facts.')


def quotas(s):
    counts = {}
    for m in s['months']:
        docs = [d for d in s['documents'] if d['month'] == m['month']]
        lines = [l for d in docs for l in d['lines']]
        count = {v: sum(l['money_error'] == v for l in lines) for v in MONEY}
        count.update({v: sum(l['outcome'] == v for l in lines) for v in OUTCOMES})
        count.update(hard=sum(l['difficulty'] == 'hard' for l in lines),
                     name_variant_property=sum(l['property_print'] == 'variant' for l in lines),
                     format_B_document=sum(d['format'] == 'B' for d in docs))
        changes = []
        for name, keys in [('doi', ['property_no']), ('elections', ['property_no']), ('contract_rates', ['vendor', 'service'])]:
            rows = s['reference'][name]
            for r in rows:
                if r['effective'].startswith(m['billing_period']) and any(all(old[k] == r[k] for k in keys) and old['effective'] < r['effective'] for old in rows):
                    changes.append((name, r))
        count['dated_reference_change'] = len(changes)
        for name, r in changes:
            affected = any(l['service_date'] >= r['effective'] and (
                l['property_no'] == r['property_no'] if 'property_no' in r else
                l['vendor'] == r['vendor'] and l['description'] == r['service']) for d in s['documents'] for l in d['lines'])
            require('G1', affected, f'Month {m["month"]}: reference change has no later affected line ({name}).')
        counts[str(m['month'])] = count
        missing = [key for key, value in count.items() if value < 1]
        require('G1', not missing, f'Month {m["month"]}: unmet monthly quotas: {", ".join(missing)}.')
        require('G1', count == s['quota_check'].get(str(m['month'])), f'Month {m["month"]}: independent recount differs from quota_check.')
    RECOUNTS.update(counts)
    (ROOT / 'quota_recount_m.json').write_text(json.dumps(counts, indent=2) + '\n')


def references(s):
    ref = s['reference']
    register = {afe_id(r['afe_number']): r for r in ref['afe_register']}
    spent, seen = defaultdict(lambda: D(0)), set()
    periods = {m['month']: date.fromisoformat(m['billing_period'] + '-01') for m in s['months']}
    for d in s['documents']:
        for l in d['lines']:
            tag = f'{d["doc_id"]}/{l["line_no"]}'
            day, prop = l['service_date'], l['property_no']
            dec = D(effective(ref['doi'], day, property_no=prop)['owner_decimal'])
            election = effective(ref['elections'], day, property_no=prop)['election']
            anomalies = {}
            if D(l['owner_decimal']) != dec:
                anomalies['wrong_decimal'] = D(l['net_amount']) - cents(D(l['gross']) * dec)
            if l['quantity'] is not None:
                rate = D(effective(ref['contract_rates'], day, vendor=l['vendor'], service=l['description'])['rate'])
                if D(l['unit_rate']) != rate:
                    anomalies['wrong_rate'] = D(l['net_amount']) - cents(D(l['quantity']) * rate * dec)
            if election == 'nonconsent':
                anomalies['nonconsent_property'] = D(l['net_amount'])
            identity = tuple(l[k] for k in ('property_no', 'vendor', 'invoice_no', 'service_date', 'reference', 'gross', 'net_amount'))
            if identity in seen:
                anomalies['duplicate'] = D(l['net_amount'])
            seen.add(identity)
            period = periods[d['month']]
            index = period.year * 12 + period.month - 1 - ref['joa_terms']['exception_window_months']
            cutoff = date(index // 12, index % 12 + 1, 1)
            if date.fromisoformat(day) < cutoff:
                anomalies['date_window'] = D(l['net_amount'])
            claim = l['claim_text'] or ''
            entry = register.get(afe_id(claim))
            if entry and entry['approved_on'] > day:
                entry = None
            if entry and entry['status'] == 'approved' and entry['property_no'] == prop:
                key = entry['afe_number']
                limit = D(entry['approved_amount']) * (1 + D(ref['joa_terms']['afe_overrun_tolerance']))
                excess = max(D(0), spent[key] + D(l['gross']) - limit) - max(D(0), spent[key] - limit)
                if excess > 0:
                    anomalies['afe_overrun'] = cents(excess * dec)
                spent[key] += D(l['gross'])
            require('G3', set(anomalies) == (set() if l['money_error'] == 'none' else {l['money_error']}), f'{tag}: money label {l["money_error"]}, derived {list(anomalies)}.')
            require('G3', D(l['error_dollars']) == anomalies.get(l['money_error'], D(0)), f'{tag}: error dollars mismatch.')
            if l['claim_type'] == 'claims_afe':
                outcome = 'contradicted' if entry and entry['status'] == 'declined' else 'supported' if entry and entry['property_no'] == prop else 'unsupported'
                match = ('match' if entry['property_no'] == prop else 'mismatch') if entry and entry['status'] == 'approved' else 'n_a'
                if afe_id(claim) is not None:
                    kind = 'unknown_number' if entry is None else 'exact' if claim == entry['afe_number'] else 'reformatted' if re.fullmatch(r'(?:CE\s*\d+\s*~\s*K|K::\d+::CE)', claim, re.I) else 'reworded'
                    style = 'n_a'
                elif claim in ('N/A', 'TBD', 'Pending', 'To follow', '-', '—'):
                    kind, style = 'placeholder', 'literal'
                elif re.search(r'will (?:supply|arrive|append)|awaits transfer', claim):
                    kind, style = 'placeholder', 'paraphrased'
                else:
                    kind, style = 'no_number', 'n_a'
                authority = 'n_a'
            else:
                outcome = 'other_authority' if l['claim_type'] == 'claims_other' else 'no_claim'
                match, kind, style = 'n_a', 'none', 'n_a'
                authority = ('emergency' if 'Emergency authority' in claim else 'service_contract' if 'service contract' in claim else 'operating_agreement_clause' if 'operating agreement clause' in claim else 'other') if l['claim_type'] == 'claims_other' else 'n_a'
            for field, value in [('outcome', outcome), ('property_match', match), ('reference_kind', kind), ('placeholder_style', style), ('authority_kind', authority)]:
                require('G3', l[field] == value, f'{tag}: {field} expected {value}.')
            require('G3', l['disposition'] == ('hold' if anomalies or outcome in ('unsupported', 'contradicted', 'other_authority') else 'post'), f'{tag}: disposition mismatch.')
            property_info = next(p for p in s['entities']['properties'] if p['property_no'] == prop)
            require('G3', l['property_printed'] in [prop, property_info['name'], *property_info['name_variants']], f'{tag}: unresolved property.')
            require('G3', l['property_print'] == ('exact' if l['property_printed'] in (prop, property_info['name']) else 'variant'), f'{tag}: property print label.')
            require('G3', l['difficulty'] == ('hard' if l['claim_location'] == 'remark' else 'plain'), f'{tag}: difficulty label.')
            if l['claim_text']:
                location = ' '.join(r['text'] for r in d['remarks'] if r['names_line'] == l['line_no']) if l['claim_location'] == 'remark' else l.get(l['claim_location'], '')
                require('G3', claim in location, f'{tag}: claim location mismatch.')
            else:
                require('G3', l['claim_type'] == 'no_claim' and not l['reference'], f'{tag}: missing claim.')


def dates(s):
    periods = []
    def walk(value, path='spec'):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('effective', 'service_date', 'approved_on'):
                    try:
                        require('G8', date.fromisoformat(v).isoformat() == v, f'{path}/{k}: invalid date.')
                    except (ValueError, TypeError):
                        require('G8', False, f'{path}/{k}: invalid date {v}.')
                walk(v, path + '/' + k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, path + '/' + str(i))
    walk(s['documents'], 'documents')
    walk(s['reference'], 'reference')
    for m in s['months']:
        try:
            p = date.fromisoformat(m['billing_period'] + '-01')
            periods.append(p.year * 12 + p.month)
        except ValueError:
            require('G8', False, f'Invalid billing period {m["billing_period"]}.')
    require('G8', all(b == a + 1 for a, b in zip(periods, periods[1:])), 'Billing periods are not consecutive.')
    require('G8', [m['month'] for m in s['months']] == list(range(1, len(s['months']) + 1)), 'Month indices are not consecutive.')


def box_text(words):
    """Reconstruct reading order within a geometric cell or paragraph.

    Preserve literal hyphens; a wrap after an in-word hyphen adds no space.
    """
    rows = []
    for w in sorted(words, key=lambda w: (w['y0'], w['x0'])):
        if not rows or abs(w['y0'] - rows[-1][0]['y0']) > 2:
            rows.append([w])
        else:
            rows[-1].append(w)
    output = ''
    for row in rows:
        segment = ' '.join(w['text'] for w in sorted(row, key=lambda w: w['x0']))
        joiner = '' if not output or (re.search(r'\w-$', output) and re.match(r'\w', segment)) else ' '
        output += joiner + segment
    return output


def pdf_checks(s, truth, manifest):
    pdfs = list((ROOT / 'clean').glob('*.pdf'))
    if not pdfs:
        NOTES.extend(['G5: SKIP — clean/ is empty; PDF claim and remark text is UNVERIFIED.',
                      'G6: SKIP — clean/ is empty; PDF header labels and order are UNVERIFIED.',
                      'G7: Source structure passed; rendered page boundaries are UNVERIFIED.'])
        return
    require('G5', {p.stem for p in pdfs} == {d['doc_id'] for d in s['documents']}, 'PDF document set differs from spec.')
    scratch = ROOT / 'scratch'
    scratch.mkdir(exist_ok=True)
    for d in s['documents']:
        pdf = ROOT / 'clean' / (d['doc_id'] + '.pdf')
        if not pdf.exists():
            require('G5', False, f'Missing PDF {d["doc_id"]}.')
            require('G6', False, f'Missing PDF {d["doc_id"]}.')
            require('G7', False, f'Missing PDF {d["doc_id"]}.')
            continue
        require('G5', pdf.read_bytes().rstrip().endswith(b'%%EOF'), f'{d["doc_id"]}: incomplete PDF.')
        bbox = scratch / (d['doc_id'] + '.bbox.html')
        cp = subprocess.run(['pdftotext', '-bbox-layout', str(pdf), str(bbox)], capture_output=True, text=True)
        if cp.returncode:
            raise RuntimeError(f'pdftotext failed: {cp.stderr}')
        tree = ET.parse(bbox)
        page_nodes = tree.findall('.//{*}page')
        require('G7', len(page_nodes) == d['pages'], f'{d["doc_id"]}: rendered page count differs.')
        f = s['formats'][d['format']]
        order = f['column_order']
        left, regions = 28.8, {}
        for key in order:
            right = left + 734.4 * WIDTHS[key] / sum(WIDTHS.values())
            regions[key] = (left, right)
            left = right
        for p, node in enumerate(page_nodes, 1):
            tag = f'{d["doc_id"]}/page {p}'
            require('G7', abs(float(node.attrib['width']) - 792) < 1 and abs(float(node.attrib['height']) - 612) < 1, tag + ': page size differs.')
            words = [{'text': text_of(w), 'x0': float(w.attrib['xMin']), 'x1': float(w.attrib['xMax']),
                      'y0': float(w.attrib['yMin']), 'y1': float(w.attrib['yMax'])} for w in node.findall('.//{*}word')]
            def column(key, y0=0, y1=580):
                a, b = regions[key]
                return [w for w in words if a <= (w['x0'] + w['x1']) / 2 < b and y0 <= w['y0'] < y1]
            # Locate the shared header row using BOTH identifying labels, never "Line N:" remarks.
            anchors = []
            for a in column('line_no'):
                if a['text'] != f['headers']['line_no'].split()[0]:
                    continue
                for b in column('property'):
                    if b['text'] == f['headers']['property'].split()[0] and abs(a['y0'] - b['y0']) < 2:
                        anchors.append(a['y0'])
            require('G6', len(anchors) == 1, tag + ': header row must hold line-number and property labels.')
            if len(anchors) != 1:
                continue
            header_y = anchors[0]
            row_anchors = sorted([w for w in column('line_no', header_y + 3) if re.fullmatch(r'\d+', w['text'])], key=lambda w: w['y0'])
            expected_rows = [l for l in d['lines'] if l['page'] == p]
            require('G7', [int(w['text']) for w in row_anchors] == [l['line_no'] for l in expected_rows], tag + ': rendered row presence/order differs.')
            if not row_anchors:
                continue
            header_bottom = row_anchors[0]['y0'] - 3
            headers = [box_text(column(key, header_y - .5, header_bottom)) for key in order]
            require('G6', headers == [f['headers'][key] for key in order], tag + ': header labels/order differ: ' + repr(headers))
            if d['format'] == 'B':
                # Search geometric text lines as well as cells for forbidden A labels.
                streams = [box_text(words)] + [box_text(column(k)) for k in order]
                require('G6', not any(label in stream for label in s['formats']['A']['headers'].values() for stream in streams), tag + ': contains format A header label.')
            markers = [w['y0'] for w in words if w['y0'] > row_anchors[-1]['y0'] and w['text'] in ('Line', 'Document')]
            table_end = min(markers) - 3 if markers else 580
            rendered = {}
            for i, anchor in enumerate(row_anchors):
                n = int(anchor['text'])
                end = row_anchors[i + 1]['y0'] - 3 if i + 1 < len(row_anchors) else table_end
                cells = {key: box_text(column(key, anchor['y0'] - .5, end)) for key in order}
                rendered[n] = cells
                line = next((l for l in expected_rows if l['line_no'] == n), None)
                if line is None:
                    continue
                for key in order:
                    require('G7', cells[key] == printed(line[FIELDS.get(key, key)]), f'{tag}/line {n}: {key} not fully on assigned page: {cells[key]!r}.')
            remark_words = [w for w in words if table_end <= w['y0'] < 580]
            remark_text = box_text(remark_words)
            for remark in truth['remarks']:
                if remark['doc_id'] == d['doc_id'] and remark['page'] == p:
                    require('G5', remark['text'] in remark_text, tag + ': missing remark ' + str(remark['remark_id']))
            for line in truth['lines']:
                if line['doc_id'] != d['doc_id'] or line['page'] != p or not line['claim_text']:
                    continue
                location = line['claim_location']
                stream = remark_text if location == 'remark' else rendered.get(line['line_no'], {}).get(location, '')
                require('G5', line['claim_text'] in stream, tag + ': missing claim on line ' + str(line['line_no']))
            if p == d['pages']:
                tail = box_text(remark_words)
                for field, label in [('gross', 'gross'), ('net_amount', 'net')]:
                    amount = sum((D(l[field]) for l in d['lines']), D(0))
                    require('G4', f'Document total ({label}): {amount}' in tail, tag + ': PDF total mismatch.')


def main():
    try:
        spec = read(ROOT / 'case_spec_m.json')
        truth = read(ROOT / 'truth_m.json')
        manifest = read(ROOT / 'manifest_m.json')
        for gate, fn in [('G2', lambda: source_checks(spec, truth, manifest)),
                         ('G1', lambda: quotas(spec)), ('G8', lambda: dates(spec)),
                         ('G3', lambda: references(spec)), ('G5', lambda: pdf_checks(spec, truth, manifest))]:
            try:
                fn()
            except Exception as exc:
                RESULTS[gate].append(f'{type(exc).__name__}: {exc}')
    except Exception as exc:
        RESULTS['G2'].append(f'{type(exc).__name__}: {exc}')
    summary = []
    for gate, errors in RESULTS.items():
        skipped = any(n.startswith(gate + ': SKIP') for n in NOTES)
        status = 'FAIL' if errors else 'SKIP' if skipped else 'PASS'
        line = f'{gate}: {status}'
        if gate == 'G7' and not list((ROOT / 'clean').glob('*.pdf')):
            line += ' (source structure only; rendered boundaries UNVERIFIED)'
        summary.append(line)
        print(line)
        for error in errors:
            print('  ' + error)
    for note in NOTES:
        print(note)
    failures = [f'{g}: {e}' for g, errors in RESULTS.items() for e in errors]
    report = ['# Source report', '', 'No lines, remarks, values, entities, or page assignments were changed from case_spec_m.json.',
              'Sources use landscape Letter pages and the local reference page style.',
              'No scan set was generated. Chrome rendering was not run during source authoring.', '',
              '## Gate results', '', *['- ' + x for x in summary], '', '## Deviations and conflicts', '',
              'Corpus content deviations: none.',
              'The current instruction requires quotas in every month. quotas-m.md:3 instead applies them across the smoke corpus; that line is set aside.',
              'The checker follows the current instruction and recounts spec labels independently of quota_check.',
              'Corpus-wide smoke quotas: ' + ('PASS' if RECOUNTS and all(sum(c[k] for c in RECOUNTS.values()) >= 1 for k in next(iter(RECOUNTS.values()))) else 'FAIL') + '; monthly results appear above.',
              'AFE spending accumulates in spec billing order, using the reference effective on each service date.',
              'Prior ledgers 5 and 6 contain all specified lines because the spec ends at month 4.', '',
              *['- ' + x for x in failures], '', '## UNVERIFIED', '',
              *(['- ' + x for x in NOTES] if NOTES else ['See failed PDF checks above, if any.']), '',
              'Next action: run python3 build_m.py --render-only, then python3 check_m.py.',
              'Resolve the monthly quota conflict before treating the full gate as passed.', '']
    (ROOT / 'SOURCE-REPORT.md').write_text('\n'.join(report))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
