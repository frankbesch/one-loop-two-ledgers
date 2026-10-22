#!/usr/bin/env python3
"""Job B build gate: source checks plus pdftotext bounding-box verification.

No browser is launched. G5 is skipped only when clean/ contains no PDFs.
PDF cells are reconstructed independently within geometric column/row bounds.
"""
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
LABELS = {
    'claim_type': {'claims_afe', 'claims_other', 'no_claim'},
    'reference_kind': {'exact', 'reformatted', 'reworded', 'placeholder', 'unknown_number', 'no_number', 'none'},
    'placeholder_style': {'literal', 'paraphrased', 'n_a'},
    'property_match': {'match', 'mismatch', 'n_a'},
    'authority_kind': {'emergency', 'service_contract', 'operating_agreement_clause', 'prior_election', 'verbal_or_informal', 'operator_policy', 'other', 'n_a'},
    'outcome': {'supported', 'unsupported', 'contradicted', 'other_authority', 'no_claim'},
    'difficulty': {'plain', 'hard'},
}
HEADERS = ['Line', 'Property', 'Description', 'Reference', 'Vendor', 'Gross', 'Decimal', 'Net']
MINIMUMS = {'supported_exact':20, 'supported_reformatted_or_reworded':20, 'supported_reworded':10, 'unsupported_placeholder':20, 'unsupported_placeholder_paraphrased':10, 'unsupported_unknown_number':20, 'unsupported_no_number':15, 'unsupported_wrong_property':15, 'contradicted':15, 'other_authority':15, 'other_authority_kinds':5, 'no_claim_ordinary':30, 'no_claim_bait':15, 'hard':15, 'remarks_no_claim':15, 'value_over_code':20}
AFE = re.compile(r'\bR[\s\-]*W[\s\-]*M\s*[/\-]\s*0*(\d+)\s*[/\-]\s*O[\s\-]*C\b', re.I)  # rescored fix: letter groups may carry dashes
LITERALS = {'N/A', 'TBD', 'Pending', 'To follow', '-'}


def strict_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f'Duplicate JSON key: {k}')
        result[k] = v
    return result


def load(path):
    return json.loads(path.read_text(), object_pairs_hook=strict_object)


def normalized(text):
    # rescored fix: a line wrap after an in-word hyphen ("R-W-" / "M/58261/OC") is not a space
    return re.sub(r'(?<=\w-) (?=\w)', '', ' '.join(text.split()))


def numbers(text):
    return {f'RWM/{int(m.group(1))}/OC' for m in AFE.finditer(text or '')}


def money(value):
    return f'{Decimal(str(value)):,.2f}'


def expected_cells(l):
    return [str(l['line_no']), l['property_no'], l['description'], l['reference'], l['vendor'], money(l['gross']), f"{l['owner_decimal']:.6f}", money(l['net_amount'])]


def quota_counts(lines, remarks):
    counts = Counter()
    kinds = Counter()
    for l in lines:
        o, r = l['outcome'], l['reference_kind']
        counts['supported_exact'] += o == 'supported' and r == 'exact'
        counts['supported_reformatted_or_reworded'] += o == 'supported' and r in {'reformatted', 'reworded'}
        counts['supported_reworded'] += o == 'supported' and r == 'reworded'
        for kind in ['placeholder', 'unknown_number', 'no_number']:
            counts['unsupported_' + kind] += o == 'unsupported' and r == kind
        counts['unsupported_placeholder_paraphrased'] += o == 'unsupported' and r == 'placeholder' and l['placeholder_style'] == 'paraphrased'
        counts['unsupported_wrong_property'] += o == 'unsupported' and l['property_match'] == 'mismatch'
        counts['contradicted'] += o == 'contradicted'
        counts['other_authority'] += o == 'other_authority'
        if o == 'other_authority':
            kinds[l['authority_kind']] += 1
        bait = bool(re.search(r'\b(?:approved|AFE)\b', l['description'] + ' ' + (l.get('reference') or ''), re.I))  # rescored fix: bait may sit in either column
        counts['no_claim_bait'] += o == 'no_claim' and bait
        counts['no_claim_ordinary'] += o == 'no_claim' and not bait
        counts['hard'] += l['difficulty'] == 'hard'
        counts['value_over_code'] += l['placeholder_style'] == 'paraphrased' or r == 'reworded' or l['difficulty'] == 'hard'
    counts['other_authority_kinds'] = len(kinds)
    counts['remarks_no_claim'] = sum(r['remark_role'] == 'no_claim' for r in remarks)
    counts.update({'authority_kind_' + k: v for k, v in kinds.items()})
    return dict(counts), kinds


def word_lines(words, tolerance=1.5):
    """Group baselines before sorting horizontally; XML order is not reading order."""
    groups = []
    for w in sorted(words, key=lambda w: (w['y0'], w['x0'])):
        if not groups or abs(groups[-1][0]['y0'] - w['y0']) > tolerance:
            groups.append([w])
        else:
            groups[-1].append(w)
    return [sorted(group, key=lambda w: w['x0']) for group in groups]


def read_words(words):
    return normalized(' '.join(w['text'] for row in word_lines(words) for w in row))


def extract_page(page):
    """Require the entire header row on one baseline, never a 'Line N:' remark."""
    words = [dict(text=''.join(w.itertext()), x0=float(w.attrib['xMin']), x1=float(w.attrib['xMax']), y0=float(w.attrib['yMin']), y1=float(w.attrib['yMax'])) for w in page.iter() if w.tag.rsplit('}', 1)[-1] == 'word']
    baselines = word_lines(words)
    headers = [row for row in baselines if [w['text'] for w in row] == HEADERS]
    if len(headers) != 1:
        raise ValueError(f'Expected one full table header baseline, found {len(headers)}')
    header = headers[0]
    starts = [w['x0'] - 2.25 for w in header]  # CSS cell padding: 3px = 2.25pt.
    ends = starts[1:] + [float(page.attrib['width']) - starts[0]]
    total_rows = [row for row in baselines if len(row) >= 2 and [w['text'] for w in row[:2]] == ['Page', 'totals'] and row[0]['y0'] > header[0]['y0']]
    if len(total_rows) != 1:
        raise ValueError('Missing or duplicate Page totals baseline')
    bottom = total_rows[0][0]['y0'] - .5
    anchors = sorted([w for w in words if starts[0] <= w['x0'] < ends[0] and w['text'].isdigit() and header[0]['y1'] < w['y0'] < bottom], key=lambda w:w['y0'])
    rows = []
    for i, anchor in enumerate(anchors):
        top = anchor['y0'] - .5
        limit = anchors[i + 1]['y0'] - .5 if i + 1 < len(anchors) else bottom
        values = [read_words([w for w in words if left <= w['x0'] < right and top <= w['y0'] < limit]) for left, right in zip(starts, ends)]
        rows.append((int(anchor['text']), values))
    footer = [row for row in baselines if row and row[0]['text'] == 'SYNTHETIC']
    if len(footer) != 1:
        raise ValueError('Missing or duplicate page footer')
    footer_y = footer[0][0]['y0']
    remarks_start = [row for row in baselines if len(row) >= 2 and row[0]['text'] == 'Line' and re.fullmatch(r'\d+:', row[1]['text']) and row[0]['y0'] > bottom]
    remarks = []
    for i, row in enumerate(remarks_start):
        top = row[0]['y0'] - .5
        end = remarks_start[i + 1][0]['y0'] - .5 if i + 1 < len(remarks_start) else footer_y - .5
        remarks.append(read_words([w for w in words if top <= w['y0'] < end]))
    totals = {}
    for row in baselines:
        if len(row) >= 2 and row[0]['text'] in {'Page', 'Document'} and row[1]['text'] == 'totals':
            totals[row[0]['text']] = read_words(row)
    if any(w['y1'] >= footer_y - 5 for w in words if w not in footer[0] and w['y0'] > header[0]['y0']):
        raise ValueError('Body content reaches or crosses footer')
    return rows, remarks, totals


class Gate:
    def __init__(self):
        self.errors = {f'G{i}': [] for i in range(1, 10)}
        self.counts = {}
        self.pdf_state = 'UNVERIFIED'
        self.deviations = []

    def require(self, gate, condition, message):
        if not condition:
            self.errors[gate].append(message)

    def run(self):
        spec = load(ROOT / 'case_spec_b.json')
        truth = load(ROOT / 'truth_b.json')
        register = load(ROOT / 'reference/afe_register.json')
        doi = load(ROOT / 'reference/doi.json')
        manifest = load(ROOT / 'manifest_b.json')
        docs = spec['documents']
        lines, remarks = truth['lines'], truth['remarks']
        expected_lines = [dict(split=d['split'], doc_id=d['doc_id'], property=l['property_no'], **l) for d in docs for l in d['lines']]
        expected_remarks = [dict(split=d['split'], doc_id=d['doc_id'], **r) for d in docs for r in d['remarks']]
        for name, actual, expected, gate in [('truth lines', lines, expected_lines, 'G2'), ('truth remarks', remarks, expected_remarks, 'G8'), ('AFE register', register, spec['afe_register'], 'G3')]:
            self.require(gate, actual == expected, f'{name} deviates from spec')
            if actual != expected:
                self.deviations.append(f'{name} deviates from spec.')
        self.require('G2', manifest['spec_sha256'] == hashlib.sha256((ROOT/'case_spec_b.json').read_bytes()).hexdigest(), 'Manifest spec hash mismatch')
        self.require('G2', [d['doc_id'] for d in manifest['documents']] == [d['doc_id'] for d in docs], 'Manifest document inventory mismatch')
        md_labels = (ROOT / 'rekey_fields_b.md').read_text()
        for label, values in LABELS.items():
            row = next((r for r in md_labels.splitlines() if r.startswith(f'| `{label}` |')), '')
            self.require('G2', set(re.findall(r'`([^`]+)`', row.split('|')[2])) == values if row else False, f'Label contract mismatch: {label}')
        line_ids = [(l['doc_id'], l['line_no']) for l in lines]
        self.require('G2', len(set(line_ids)) == len(line_ids), 'Duplicate line records')
        line_lookup = {(l['doc_id'], l['line_no']):l for l in lines}
        for l in lines:
            ident = f"{l['doc_id']} line {l['line_no']}"
            for label, values in LABELS.items():
                self.require('G2', isinstance(l.get(label), str) and l[label] in values, f'{ident}: missing, multiple, or invalid {label}')
            self.require('G2', l['claim_text'] is None if l['claim_type'] == 'no_claim' else isinstance(l['claim_text'], str) and bool(l['claim_text']), f'{ident}: invalid claim text')
        splits = sorted({d['split'] for d in docs})
        for split in splits:
            counts, kinds = quota_counts([l for l in lines if l['split'] == split], [r for r in remarks if r['split'] == split])
            self.counts[split] = counts
            for k, minimum in MINIMUMS.items():
                self.require('G1', counts.get(k, 0) >= minimum, f'{split}: {k}={counts.get(k, 0)} < {minimum}')
            self.require('G1', all(v >= 2 for v in kinds.values()) and {'verbal_or_informal', 'prior_election'} <= kinds.keys(), f'{split}: authority kind coverage failed')
            self.require('G1', counts == spec['quota_check'][split], f'{split}: recomputed quota counts differ from spec')
        regs = {r['afe_number']:r for r in register}
        self.require('G3', len(regs) == len(register), 'Duplicate register AFE')
        properties = {p['property_no'] for p in spec['entities']['properties']}
        for r in register:
            self.require('G7', r.get('property_no') in properties, f'Register property missing or invalid: {r}')
        for l in lines:
            ident = f"{l['doc_id']} line {l['line_no']}"
            self.require('G7', l.get('property') == l.get('property_no') and l.get('property_no') in properties, f'{ident}: missing/invalid property')
            ns = numbers(l['claim_text'])
            numbered = l['reference_kind'] in {'exact', 'reformatted', 'reworded', 'unknown_number'}
            self.require('G3', len(ns) == 1 if numbered else not ns, f'{ident}: unexpected number count')
            if ns:
                for n in ns:
                    r = regs.get(n)
                    if l['reference_kind'] == 'unknown_number':
                        self.require('G3', r is None and l['outcome'] == 'unsupported', f'{ident}: unknown number exists in register')
                    else:
                        self.require('G3', r is not None, f'{ident}: missing register entry')
                        if r:
                            match = r['property_no'] == l['property_no']
                            outcome = 'contradicted' if r['status'] == 'declined' else 'supported' if match else 'unsupported'
                            pm = 'n_a' if r['status'] == 'declined' else 'match' if match else 'mismatch'
                            self.require('G3', r['split'] == l['split'] and l['outcome'] == outcome and l['property_match'] == pm, f'{ident}: register disagrees')
                            if l['property_match'] == 'mismatch':
                                self.require('G7', r['property_no'] != l['property_no'], f'{ident}: wrong-property AFE matches line')
            expected_net = (Decimal(str(l['gross'])) * Decimal(str(l['owner_decimal']))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            self.require('G4', expected_net == Decimal(str(l['net_amount'])), f'{ident}: net arithmetic mismatch')
            if l['reference_kind'] == 'placeholder':
                claim = l['claim_text'] or ''
                value = claim.rsplit(':', 1)[-1].strip()  # rescored fix: any label, per rekey_fields_b.md
                valid = value in LITERALS if l['placeholder_style'] == 'literal' else l['placeholder_style'] == 'paraphrased' and value not in LITERALS and not re.search(r'(?<!\w)(?:N/A|TBD|Pending|To follow)(?!\w)|(?<!\w)[-–—](?!\w)', value, re.I)
                self.require('G9', valid, f'{ident}: placeholder spelling/style mismatch')
            else:
                self.require('G9', l['placeholder_style'] == 'n_a', f'{ident}: unexpected placeholder style')
            claim = l['claim_text']
            if claim:
                location = l['claim_location']
                printed = [r['text'] for r in remarks if r['doc_id'] == l['doc_id'] and r['names_line'] == l['line_no'] and r['remark_role'] == 'claim'] if location == 'remark' else [l.get(location, '')]
                self.require('G2', any(claim in t for t in printed), f'{ident}: claim absent from stated location')
                self.require('G2', (l['difficulty'] == 'hard') == (location == 'remark'), f'{ident}: difficulty/location mismatch')
                if l['difficulty'] == 'hard':
                    self.require('G2', claim not in l['description'] and claim not in l['reference'], f'{ident}: hard claim appears in table')
        expected_doi = [dict(**p, owner=spec['entities']['owner'], owner_decimal=next(l['owner_decimal'] for l in expected_lines if l['property_no'] == p['property_no'])) for p in spec['entities']['properties']]
        self.require('G4', doi == expected_doi, 'DOI reference differs from spec')
        for l in lines:
            self.require('G4', any(r['property_no'] == l['property_no'] and r['owner_decimal'] == l['owner_decimal'] for r in doi), f"DOI mismatch: {l['doc_id']}:{l['line_no']}")
        seen_docs, seen_afes = set(), set()
        for split in splits:
            ids = [d['doc_id'] for d in docs if d['split'] == split]
            ns = set().union(*(numbers(l['description'] + ' ' + l['reference'] + ' ' + (l['claim_text'] or '')) for l in lines if l['split'] == split), *(numbers(r['text']) for r in remarks if r['split'] == split), *(numbers(r['afe_number']) for r in register if r['split'] == split))
            self.require('G6', len(ids) == len(set(ids)) and not seen_docs.intersection(ids), f'{split}: overlapping or duplicate document IDs')
            self.require('G6', not seen_afes.intersection(ns), f'{split}: overlapping AFE numbers')
            seen_docs.update(ids)
            seen_afes.update(ns)
        self.require('G8', len({(r['doc_id'], r['remark_id']) for r in remarks}) == len(remarks), 'Duplicate remark records')
        for r in remarks:
            target = line_lookup.get((r['doc_id'], r['names_line']))
            self.require('G8', target is not None and target['page'] == r['page'] and r['text'].startswith(f"Line {r['names_line']}: "), f"Invalid remark target: {r['doc_id']} remark {r['remark_id']}")
            self.require('G2', r['remark_role'] in {'claim', 'no_claim'}, 'Invalid remark role')
        expected_sources = {d['doc_id'] + '.html' for d in docs}
        self.require('G2', {p.name for p in (ROOT/'sources').glob('*.html')} == expected_sources, 'Source document inventory mismatch')
        for d in docs:
            self.check_source(d, manifest)
        pdfs = list((ROOT/'clean').glob('*.pdf'))
        if not pdfs:
            self.pdf_state = 'SKIP: clean/ is empty; render PDFs to verify G5 and rendered G4/G8.'
        else:
            self.pdf_state = 'CHECKED'
            self.require('G5', {p.stem for p in pdfs} == {d['doc_id'] for d in docs}, 'Clean PDF inventory incomplete or unexpected')
            for d in docs:
                path = ROOT/'clean'/f"{d['doc_id']}.pdf"
                if not path.exists():
                    continue
                try:
                    cp = subprocess.run(['pdftotext', '-bbox-layout', '-enc', 'UTF-8', str(path), '-'], capture_output=True, text=True, timeout=60)
                    if cp.returncode:
                        raise ValueError(cp.stderr)
                    xml = ET.fromstring(cp.stdout)
                    pages = [e for e in xml.iter() if e.tag.rsplit('}', 1)[-1] == 'page']
                    self.require('G8', len(pages) == d['pages'], f"{d['doc_id']}: rendered page count mismatch")
                    for page_no, page in enumerate(pages, 1):
                        rows, pdf_remarks, pdf_totals = extract_page(page)
                        expected = [l for l in d['lines'] if l['page'] == page_no]
                        self.require('G8', [n for n, _ in rows] == [l['line_no'] for l in expected], f"{d['doc_id']} page {page_no}: missing, extra, duplicate, or split rows")
                        row_map = dict(rows)
                        for l in expected:
                            n = l['line_no']
                            if n not in row_map:
                                self.require('G5', not l['claim_text'], f"{d['doc_id']}:{n}: PDF claim row missing")
                                continue
                            values = row_map[n]
                            self.require('G2', values == [normalized(v) for v in expected_cells(l)], f"{d['doc_id']}:{n}: PDF cell mismatch: {values}")
                            self.require('G4', values[5:] == expected_cells(l)[5:], f"{d['doc_id']}:{n}: PDF amount mismatch")
                            if l['claim_text'] and l['claim_location'] != 'remark':
                                index = {'description':2, 'reference':3}[l['claim_location']]
                                self.require('G5', normalized(l['claim_text']) in values[index], f"{d['doc_id']}:{n}: PDF claim missing")
                        expected_remarks = [r for r in d['remarks'] if r['page'] == page_no]
                        self.require('G5', pdf_remarks == [normalized(r['text']) for r in expected_remarks], f"{d['doc_id']} page {page_no}: PDF remarks differ")
                        for l in expected:
                            if l['claim_location'] == 'remark':
                                self.require('G5', any(t.startswith(f"Line {l['line_no']}: ") and normalized(l['claim_text']) in t for t in pdf_remarks), f"{d['doc_id']}:{l['line_no']}: PDF remark claim missing")
                        for label, subset in [('Page', expected)] + ([('Document', d['lines'])] if page_no == d['pages'] else []):
                            self.require('G4', pdf_totals.get(label) == self.total_text(label, subset), f"{d['doc_id']} page {page_no}: PDF {label} totals mismatch")
                except Exception as exc:
                    self.require('G5', False, f"{d['doc_id']}: PDF verification failed: {exc}")
                    self.require('G8', False, f"{d['doc_id']}: rendered geometry unverified")

    @staticmethod
    def total_text(label, lines):
        sums = [money(sum((Decimal(str(l[k])) for l in lines), Decimal(0))) for k in ['gross', 'net_amount']]
        return f'{label} totals Gross: {sums[0]} Net: {sums[1]}'

    def check_source(self, doc, manifest):
        ident = doc['doc_id']
        path = ROOT/'sources'/f'{ident}.html'
        source = path.read_text()
        record = next((r for r in manifest['documents'] if r['doc_id'] == ident), {})
        self.require('G2', record.get('source_sha256') == hashlib.sha256(path.read_bytes()).hexdigest(), f'{ident}: source hash mismatch')
        self.require('G2', all(record.get(k) == doc[k] for k in ['split', 'type', 'pages']), f'{ident}: manifest metadata mismatch')
        self.require('G2', record.get('line_count') == len(doc['lines']) and record.get('remark_count') == len(doc['remarks']), f'{ident}: manifest counts mismatch')
        self.require('G4', record.get('totals') == {k:money(sum((Decimal(str(l[k])) for l in doc['lines']), Decimal(0))) for k in ['gross', 'net_amount']}, f'{ident}: manifest totals mismatch')
        root = ET.fromstring(re.sub(r'<!doctype[^>]*>', '', source, flags=re.I))
        pages = root.findall('./body/section')
        self.require('G8', len(pages) == doc['pages'], f'{ident}: source page count mismatch')
        for p, section in enumerate(pages, 1):
            self.require('G8', section.attrib.get('data-page') == str(p), f'{ident}: source page identity mismatch')
            rows = section.findall('./table/tbody/tr')
            expected = [l for l in doc['lines'] if l['page'] == p]
            self.require('G8', [r.attrib.get('data-line') for r in rows] == [str(l['line_no']) for l in expected], f'{ident}: source row/page assignment mismatch')
            self.require('G2', [h.text for h in section.findall('./table/thead/tr/th')] == HEADERS, f'{ident}: source headers mismatch')
            for row, l in zip(rows, expected):
                values = [''.join(c.itertext()) for c in row.findall('td')]
                self.require('G2', values == expected_cells(l), f"{ident}:{l['line_no']}: source cell mismatch")
                self.require('G4', values[5:] == expected_cells(l)[5:], f"{ident}:{l['line_no']}: source amount mismatch")
            actual_remarks = section.findall('./div[@class="note"]/p')
            expected_remarks = [r for r in doc['remarks'] if r['page'] == p]
            self.require('G8', [(r.attrib.get('data-remark'), ''.join(r.itertext())) for r in actual_remarks] == [(str(r['remark_id']), r['text']) for r in expected_remarks], f'{ident}: source remark mismatch')
            for label, cls, subset in [('Page', 'page-totals', expected)] + ([('Document', 'document-totals', doc['lines'])] if p == doc['pages'] else []):
                elem = section.find(f'./div[@class="totals {cls}"]')
                self.require('G4', elem is not None and ' '.join(''.join(c.itertext()) for c in elem) == self.total_text(label, subset), f'{ident}: source {label} totals mismatch')
        style = root.find('./head/style').text
        self.require('G8', 'break-inside:avoid' in style and 'break-after:page' in style, f'{ident}: missing row/page break constraints')

    def report(self):
        lines = ['# Source report', '', 'Deviations from case_spec_b.json: ' + ('None detected.' if not self.deviations else ' '.join(self.deviations)), '', '## Build gate', '']
        for g, errors in self.errors.items():
            status = 'FAIL' if errors else self.pdf_state if g == 'G5' and self.pdf_state.startswith('SKIP') else 'PASS'
            suffix = ' (source checks; rendered checks UNVERIFIED)' if g in {'G4', 'G8'} and self.pdf_state.startswith('SKIP') else ''
            lines.append(f'- {g}: {status}{suffix}.')
            lines.extend(f'  - {e}' for e in errors)
            print(f'{g}: {status}{suffix}')
        lines += ['', '## Quotas per split', '', '| Quota | Minimum | Calibration | Scored |', '|---|---:|---:|---:|']
        for k, minimum in MINIMUMS.items():
            lines.append(f"| {k} | {minimum} | {self.counts.get('calibration', {}).get(k, 'UNVERIFIED')} | {self.counts.get('scored', {}).get(k, 'UNVERIFIED')} |")
        for split, counts in self.counts.items():
            kinds = ', '.join(f'{k.removeprefix("authority_kind_")}={v}' for k, v in sorted(counts.items()) if k.startswith('authority_kind_'))
            lines += ['', f'{split} authority kinds: {kinds}.']
        lines += ['', '## Verification limits', '', '- Amounts round half-up to cents per line; totals sum rounded line amounts.', '- Sources use the reference page style, with wrapped cells and explicit spec page boundaries.', '- No scan set was generated (D-286).', '- PDF visual appearance remains UNVERIFIED; this gate checks text and geometry, not visual rendering.']
        if self.pdf_state.startswith('SKIP'):
            lines += ['- Chrome was not run. PDF text, clipping, and actual pagination remain UNVERIFIED.', '- Next action: `python3 build_b.py --render-only`; it automatically runs `check_b.py` after rendering.']
        elif any(self.errors.values()):
            lines += ['- Next action: resolve gate failures and rerun `python3 check_b.py`.']
        (ROOT/'SOURCE-REPORT.md').write_text('\n'.join(lines) + '\n')
        (ROOT/'gate_results_b.json').write_text(json.dumps({'gates': self.errors, 'pdf_status':self.pdf_state, 'quota_counts':self.counts, 'passed':not any(self.errors.values()), 'full_validation_complete':not any(self.errors.values()) and self.pdf_state == 'CHECKED'}, indent=2) + '\n')
        return int(any(self.errors.values()))


def main():
    gate = Gate()
    try:
        gate.run()
    except Exception as exc:
        # Malformed or missing inputs cannot turn a partially executed gate green.
        for g in gate.errors:
            gate.errors[g].append(f'Gate aborted: {type(exc).__name__}: {exc}')
    return gate.report()


if __name__ == '__main__':
    sys.exit(main())
