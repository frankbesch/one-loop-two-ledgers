#!/usr/bin/env python3
"""Job B build gate. Exit 1 for failures; empty clean/ explicitly skips G5."""
import argparse
from collections import Counter
from decimal import Decimal
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import build_b as b

ROOT = b.ROOT
AFE = re.compile(r'\b([A-Za-z]+)\s*[:\- ]\s*(\d+)\s*[:\- ]\s*(\d+)\b')
LITERALS = {'N/A', 'TBD', 'Pending', 'To follow', '-'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def norm(text):
    return ' '.join(text.split())


def numbers(text):
    return {(a.upper(), int(c), int(d)) for a, c, d in AFE.findall(text)}


def key(row):
    return row['doc_id'], row['line_no']


def bait(row):
    return row['claim_type'] == 'no_claim' and bool(re.search(r'\b(authorized|approved|budget|AFE)\b', row['description'], re.I))


class Gate:
    def __init__(self, sources_only=False):
        self.sources_only = sources_only
        self.spec = b.read_json(ROOT / 'case_spec_b.json')
        self.truth = b.read_json(ROOT / 'truth_b.json')
        self.manifest = b.read_json(ROOT / 'manifest_b.json')
        self.register = b.read_json(ROOT / 'reference/afe_register.json')
        self.lines = self.truth['lines']
        self.remarks = self.truth['remarks']
        self.docs = {d['doc_id']: d for d in self.spec['documents']}
        self.pdfs = list((ROOT / 'clean').glob('*.pdf'))
        self.pdf_cache = {}
        self.results = {}
        self.details = []

    def pdf(self, doc_id):
        if doc_id not in self.pdf_cache:
            path = ROOT / 'clean' / (doc_id + '.pdf')
            require(path.is_file(), f'Missing PDF: {path.name}')
            result = subprocess.run(['pdftotext', '-bbox-layout', str(path), '-'],
                                    capture_output=True, text=True, check=True, timeout=30)
            tree = ET.fromstring(result.stdout)
            pages = []
            for page in tree.findall('.//{*}page'):
                words = [(float(w.attrib['xMin']), float(w.attrib['yMin']),
                          float(w.attrib['xMax']), float(w.attrib['yMax']), w.text or '')
                         for w in page.findall('.//{*}word')]
                pages.append(words)
            self.pdf_cache[doc_id] = pages
        return self.pdf_cache[doc_id]

    @staticmethod
    def words_text(words):
        return norm(' '.join(w[4] for w in sorted(words, key=lambda w: (round(w[1], 1), w[0]))))

    def pdf_rows(self, doc):
        pages = self.pdf(doc['doc_id'])
        require(len(pages) == doc['pages'], f'{doc["doc_id"]}: PDF page count differs')
        result = {}
        # Letter paper, 0.55-inch margins, and the authored percentage columns.
        bounds = [39.6]
        for percentage in (4, 9, 9, 25, 25, 10, 8, 10):
            bounds.append(bounds[-1] + 532.8 * percentage / 100)
        fields = ('line_no', 'property_no', 'vendor', 'description', 'reference', 'gross', 'owner_decimal', 'net')
        for p, words in enumerate(pages, 1):
            header = [w for w in words if w[4] == 'Line' and bounds[0] <= w[0] < bounds[1] and any(v[4] == 'Property' and abs(v[1] - w[1]) < 2 for v in words)]  # smoke fix: remark text 'Line 4: ...' is not a header
            require(len(header) == 1, f'{doc["doc_id"]} page {p}: missing or repeated table header')
            rows = [r for r in doc['lines'] if r['page'] == p]
            anchors = [w for w in words if w[1] > header[0][1] and bounds[0] <= w[0] < bounds[1] and w[4].isdigit()]
            anchors.sort(key=lambda w: w[1])
            require([w[4] for w in anchors] == [str(r['line_no']) for r in rows], f'{doc["doc_id"]}: PDF line identities differ')
            for i, (row, anchor) in enumerate(zip(rows, anchors)):
                end = anchors[i + 1][1] - .5 if i + 1 < len(anchors) else min(
                    [w[1] for w in words if w[1] > anchor[1] and w[4] in ('Gross', 'Line', 'SYNTHETIC')] + [744.0]) - .5
                cells = {}
                for j, field in enumerate(fields):
                    cells[field] = self.words_text([w for w in words if bounds[j] <= w[0] < bounds[j + 1]
                                                   and anchor[1] - .5 <= w[1] < end])
                result[row['line_no']] = cells
        return result

    def g1(self):
        quotas = {}
        for name, count in re.findall(r'^\| ([^|]+?) \| (\d+) (?:line|remark)', (ROOT / 'quotas-b.md').read_text(), re.M):
            quotas[name.strip()] = int(count)
        require(len(quotas) == 13, 'Quota table must contain all 13 specified cases')
        for split in sorted({d['split'] for d in self.spec['documents']}):
            counts = Counter()
            rows = [r for r in self.lines if r['split'] == split]
            for r in rows:
                outcome, ref = r['outcome'], r['reference_kind']
                if outcome == 'supported':
                    counts['supported, exact' if ref == 'exact' else 'supported, reformatted or reworded'] += 1
                if outcome == 'unsupported':
                    names = {'unknown_number': 'unknown number', 'no_number': 'no number'}
                    if ref == 'placeholder':
                        counts[f'unsupported, placeholder ({r["placeholder_style"]})'] += 1
                    elif ref in names:
                        counts['unsupported, ' + names[ref]] += 1
                    if r['property_match'] == 'mismatch':
                        counts['unsupported, wrong property'] += 1
                if outcome in ('contradicted', 'other_authority'):
                    counts[outcome] += 1
                if outcome == 'no_claim':
                    counts['no_claim, bait' if bait(r) else 'no_claim, ordinary'] += 1
                if r['difficulty'] == 'hard' and r['claim_location'] == 'remark':
                    counts['hard (claim only in a remark)'] += 1
            counts['remarks that name a line and claim nothing'] = sum(r['split'] == split and r['remark_role'] == 'no_claim' for r in self.remarks)
            for name, minimum in quotas.items():
                require(counts[name] >= minimum, f'{split}: {name}: {counts[name]} < {minimum}')
                self.details.append(f'{split}: {name}: {counts[name]} / minimum {minimum}')
            require(len({r['authority_kind'] for r in rows if r['outcome'] == 'other_authority'}) >= 2, f'{split}: need two other-authority kinds')
            require(dict(counts) == self.spec['quota_check'][split], f'{split}: counts differ from fixed spec')

    def g2(self):
        require(self.truth == b.truth(self.spec), 'Truth differs from fixed spec, or lines/remarks were added or dropped')
        require(len({key(r) for r in self.lines}) == len(self.lines), 'Duplicate truth line')
        for row in self.lines:
            for label, options in b.LABELS.items():
                require(isinstance(row.get(label), str) and row[label] in options, f'{key(row)}: invalid {label}')
        for r in self.remarks:
            require(r['remark_role'] in {'claim', 'no_claim'}, 'Invalid remark role')
        expected_ids = set(self.docs)
        require({p.stem for p in (ROOT / 'src').glob('*.html')} == expected_ids, 'Source document inventory differs')
        require(self.manifest['spec_sha256'] == b.sha(ROOT / 'case_spec_b.json'), 'Spec hash mismatch')
        require([d['doc_id'] for d in self.manifest['documents']] == list(self.docs), 'Manifest inventory differs')
        for doc, entry in zip(self.spec['documents'], self.manifest['documents']):
            path = ROOT / 'src' / (doc['doc_id'] + '.html')
            require(path.read_text() == b.page_source(self.spec, doc), f'{doc["doc_id"]}: printed source differs from spec/style')
            require(entry['source_sha256'] == b.sha(path), f'{doc["doc_id"]}: source hash differs')
            for name in ('split', 'type', 'pages'):
                require(entry[name] == doc[name], f'{doc["doc_id"]}: manifest {name} differs')
            require(entry['source'] == f'src/{doc["doc_id"]}.html' and entry['clean'] == f'clean/{doc["doc_id"]}.pdf', 'Manifest path mismatch')
            require(entry['line_count'] == len(doc['lines']) and entry['remark_count'] == len(doc['remarks']), 'Manifest counts differ')

    def g3(self):
        require(self.register == self.spec['afe_register'], 'Register differs from spec')
        index = {}
        for entry in self.register:
            found = numbers(entry['afe_number'])
            require(len(found) == 1, 'Invalid register AFE')
            number = next(iter(found))
            require(number not in index, 'Duplicate canonical AFE in register')
            index[number] = entry
        for row in self.lines:
            found = numbers(' '.join([row['reference'], row['claim_text'] or '']))
            if row['claim_type'] != 'claims_afe':
                require(row['reference_kind'] == 'none' and row['property_match'] == 'n_a', f'{key(row)}: non-AFE labels')
                continue
            ref = row['reference_kind']
            if ref in {'exact', 'reformatted', 'reworded', 'unknown_number'}:
                require(len(found) == 1, f'{key(row)}: expected one AFE number')
                entry = index.get(next(iter(found)))
                if ref == 'unknown_number':
                    require(entry is None and row['outcome'] == 'unsupported' and row['property_match'] == 'n_a', f'{key(row)}: unknown number exists in register')
                    continue
                require(entry is not None and entry['split'] == row['split'], f'{key(row)}: AFE missing or in other split')
                if ref == 'exact':
                    require(row['reference'] == entry['afe_number'], f'{key(row)}: reference not exact')
                elif ref == 'reformatted':
                    require(row['reference'] != entry['afe_number'] and numbers(row['reference']) == numbers(entry['afe_number']), f'{key(row)}: invalid reformat')
                elif ref == 'reworded':
                    require(numbers(row['claim_text'] or '') == numbers(entry['afe_number']), f'{key(row)}: number missing from claim sentence')
                if entry['status'] == 'declined':
                    expected = ('contradicted', 'n_a')
                else:
                    require(entry['status'] == 'approved', 'Unknown register status')
                    expected = ('supported', 'match') if entry['property_no'] == row['property'] else ('unsupported', 'mismatch')
                require((row['outcome'], row['property_match']) == expected, f'{key(row)}: register disagrees')
            else:
                require(not found and row['outcome'] == 'unsupported' and row['property_match'] == 'n_a', f'{key(row)}: unnumbered labels disagree')

    def g4(self):
        require(b.read_json(ROOT / 'reference/doi.json') == b.doi(self.spec), 'DOI differs from owner decimals')
        for doc, entry in zip(self.spec['documents'], self.manifest['documents']):
            for row in [r for r in self.lines if r['doc_id'] == doc['doc_id']]:
                require(b.cents(b.decimal(row['gross']) * b.decimal(row['owner_decimal'])) == b.decimal(row['net']), f'{key(row)}: net arithmetic fails')
                require(row['owner_decimal'] == doc['owner_decimal'], f'{key(row)}: owner decimal differs')
            require(all(entry[k] == v for k, v in b.totals(doc).items()), f'{doc["doc_id"]}: totals differ')
            if self.pdfs and not self.sources_only:
                cells = self.pdf_rows(doc)
                for row in doc['lines']:
                    for field in ('gross', 'net', 'owner_decimal'):
                        require(Decimal(cells[row['line_no']][field].replace(',', '')) == b.decimal(row[field]), f'{doc["doc_id"]}: PDF amount differs')
                text = self.words_text(self.pdf(doc['doc_id'])[-1])
                for field, value in b.totals(doc).items():
                    require(f'{field.replace("_", " ").capitalize()}: {b.money(value)}' in text, f'{doc["doc_id"]}: PDF total differs')

    def g5(self):
        if self.sources_only or not self.pdfs:
            return 'SKIP — clean/ has no PDFs; rendered text UNVERIFIED.' if not self.pdfs else 'SKIP — explicit source preflight; PDF checks run after rendering.'
        require({p.stem for p in self.pdfs} == set(self.docs), 'Clean PDF inventory differs from spec')
        for doc in self.spec['documents']:
            cells = self.pdf_rows(doc)
            pages = self.pdf(doc['doc_id'])
            for row in [r for r in self.lines if r['doc_id'] == doc['doc_id']]:
                if row['claim_text'] is not None:
                    location = row['claim_location']
                    haystack = self.words_text(pages[row['page'] - 1]) if location == 'remark' else cells[row['line_no']][location]
                    require(norm(row['claim_text']) in haystack, f'{key(row)}: PDF claim text missing')
            for remark in [r for r in self.remarks if r['doc_id'] == doc['doc_id']]:
                require(norm(remark['text']) in self.words_text(pages[remark['page'] - 1]), f'{doc["doc_id"]}: remark {remark["remark_id"]} missing')

    def g6(self):
        owners = {}
        ids = set()
        for doc in self.spec['documents']:
            require(doc['doc_id'] not in ids, 'Document ID shared or duplicated')
            ids.add(doc['doc_id'])
        for entry in self.register:
            for number in numbers(entry['afe_number']):
                require(number not in owners or owners[number] == entry['split'], 'AFE shared across splits')
                owners[number] = entry['split']
        for row in self.lines:
            for number in numbers(' '.join([row['reference'], row['description'], row['claim_text'] or ''])):
                require(number not in owners or owners[number] == row['split'], 'AFE shared across splits')
                owners[number] = row['split']
        for remark in self.remarks:
            for number in numbers(remark['text']):
                require(number not in owners or owners[number] == remark['split'], 'Remark AFE shared across splits')
                owners[number] = remark['split']

    def g7(self):
        properties = {p['property_no'] for p in self.spec['entities']['properties']}
        for entry in self.register:
            require(entry.get('property_no') in properties, 'Register property missing or invalid')
        for row in self.lines:
            require(row.get('property') in properties and row['property'] == row.get('property_no'), f'{key(row)}: property missing or invalid')
            if row['property_match'] == 'mismatch':
                found = numbers(row['reference'] + ' ' + (row['claim_text'] or ''))
                entries = [e for e in self.register if numbers(e['afe_number']) == found]
                require(len(entries) == 1 and entries[0]['property_no'] != row['property'], f'{key(row)}: wrong-property case matches')

    def g8(self):
        index = {key(row): row for row in self.lines}
        for remark in self.remarks:
            target = (remark['doc_id'], remark['names_line'])
            require(target in index, f'{target}: remark targets absent line')
            require(remark['page'] == index[target]['page'], f'{target}: remark page differs')
            require(re.match(r'Line ' + str(remark['names_line']) + r':', remark['text']), f'{target}: remark does not print target line')
        for row in self.lines:
            require(1 <= row['page'] <= self.docs[row['doc_id']]['pages'], f'{key(row)}: page outside document')
            if row['claim_type'] == 'no_claim':
                require(row['claim_text'] is None and row['claim_location'] is None, f'{key(row)}: unexpected claim')
            else:
                location = row['claim_location']
                require(location in {'description', 'reference', 'remark'} and bool(row['claim_text']), f'{key(row)}: claim location missing')
                if location == 'remark':
                    require(row['difficulty'] == 'hard', f'{key(row)}: remark claim not hard')
                    matches = [r for r in self.remarks if r['doc_id'] == row['doc_id'] and r['names_line'] == row['line_no'] and r['remark_role'] == 'claim' and row['claim_text'] in r['text']]
                    require(len(matches) == 1, f'{key(row)}: remark claim missing or repeated')
                    require(all(row['claim_text'] not in row[f] for f in ('description', 'reference')), f'{key(row)}: hard claim also on line')
                else:
                    require(row['difficulty'] == 'plain' and row['claim_text'] in row[location], f'{key(row)}: printed claim location differs')
        if self.pdfs and not self.sources_only:
            props = {p['property_no']: p['name'] for p in self.spec['entities']['properties']}
            for doc in self.spec['documents']:
                cells = self.pdf_rows(doc)
                for row in doc['lines']:
                    for field in ('line_no', 'property_no', 'vendor', 'description', 'reference'):
                        expected = str(row[field]) + (' ' + props[row[field]] if field == 'property_no' else '')
                        require(cells[row['line_no']][field] == norm(expected), f'{doc["doc_id"]} line {row["line_no"]}: PDF {field} truncated, split, or changed')
            return 'PASS — remark targets and rendered row containment verified.'
        return 'PASS (source) — remark targets and indivisible rows; rendered page containment UNVERIFIED.'

    def g9(self):
        for row in self.lines:
            style = row['placeholder_style']
            if row['reference_kind'] != 'placeholder':
                require(style == 'n_a', f'{key(row)}: placeholder style without placeholder')
                continue
            require(style in {'literal', 'paraphrased'}, f'{key(row)}: placeholder needs style')
            printed = row['reference'] if row['reference'] else row['claim_text']
            if style == 'literal':
                require(printed in LITERALS, f'{key(row)}: nonliteral stand-in')
            else:
                require(not re.search(r'(?<!\w)(?:N/A|TBD|Pending|To follow)(?!\w)|[-–—]', printed), f'{key(row)}: literal token in paraphrased stand-in')

    def run(self):
        for number in range(1, 10):
            name = f'G{number}'
            try:
                self.results[name] = getattr(self, name.lower())() or 'PASS'
            except Exception as exc:
                self.results[name] = f'FAIL — {type(exc).__name__}: {exc}'
            print(name + ': ' + self.results[name])
        failed = any(v.startswith('FAIL') for v in self.results.values())
        report = ['# Source report', '', 'Deviations from case_spec_b.json: ' + ('gate failures require resolution; see below.' if failed else 'none.'), '',
                  f'Built {len(self.docs)} documents, {len(self.lines)} lines, and {len(self.remarks)} remarks.',
                  'Amounts use decimal multiplication, ROUND_HALF_EVEN to cents, and sums of printed line amounts.',
                  'Page style derives from the run-1 HTML template; no run-1 entity names are copied.',
                  'No scan set was created (D-286).', '', '## Gate results', '']
        report += [f'- {name}: {value}' for name, value in self.results.items()]
        report += ['', '## Quotas by split', ''] + ['- ' + d for d in self.details]
        report += ['', '## UNVERIFIED', '']
        if not self.pdfs or self.sources_only:
            report += ['Chrome rendering was not run by this source check.',
                       'PDF claim/remark text, actual page count, printed PDF amounts, and rendered row containment remain UNVERIFIED.']
        report += ['Visual appearance remains UNVERIFIED; text extraction does not replace visual inspection.', '',
                   'Next action: run `python3 build_b.py --render-only`; it runs `check_b.py` after rendering.', '']
        (ROOT / 'SOURCE-REPORT.md').write_text('\n'.join(report))
        return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only', action='store_true', help='Preflight existing HTML before rendering')
    args = parser.parse_args()
    try:
        return Gate(args.sources_only).run()
    except Exception as exc:
        message = f'BUILD GATE FAIL: {type(exc).__name__}: {exc}'
        print(message, file=sys.stderr)
        (ROOT / 'SOURCE-REPORT.md').write_text('# Source report\n\n' + message + '\n\nG1–G9 UNVERIFIED: required input could not be loaded.\n')
        return 1


if __name__ == '__main__':
    sys.exit(main())
