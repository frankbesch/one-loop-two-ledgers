#!/usr/bin/env python3
"""Deterministic, offline Job B authoring. Never execute the run-1 generator."""
import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
LABELS = {
    'claim_type': {'claims_afe', 'claims_other', 'no_claim'},
    'reference_kind': {'exact', 'reformatted', 'reworded', 'placeholder', 'unknown_number', 'no_number', 'none'},
    'placeholder_style': {'literal', 'paraphrased', 'n_a'},
    'property_match': {'match', 'mismatch', 'n_a'},
    'authority_kind': {'emergency', 'service_contract', 'operating_agreement_clause', 'prior_election', 'verbal_or_informal', 'operator_policy', 'other', 'n_a'},
    'outcome': {'supported', 'unsupported', 'contradicted', 'other_authority', 'no_claim'},
    'difficulty': {'plain', 'hard'},
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def dump(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def decimal(value):
    return Decimal(str(value))


def cents(value):
    return decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)


def money(value):
    return f'{decimal(value):,.2f}'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def totals(document):
    return {key + '_total': str(sum((decimal(row[key]) for row in document['lines']), Decimal(0)).quantize(Decimal('.01')))
            for key in ('gross', 'net')}


def truth(spec):
    lines, remarks = [], []
    for doc in spec['documents']:
        by_number = {line['line_no']: line for line in doc['lines']}
        for line in doc['lines']:
            lines.append(dict(line, split=doc['split'], doc_id=doc['doc_id'], property=line['property_no']))
        for remark in doc['remarks']:
            line = by_number[remark['names_line']]
            remarks.append(dict(remark, split=doc['split'], doc_id=doc['doc_id'],
                                page=line['page'], property=line['property_no']))
    return {'synthetic': True, 'seed': spec['seed'], 'lines': lines, 'remarks': remarks}


def doi(spec):
    values = {}
    for doc in spec['documents']:
        for line in doc['lines']:
            prop = line['property_no']
            value = line['owner_decimal']
            if prop in values and values[prop] != value:
                raise ValueError(f'Conflicting owner decimals for {prop}')
            values[prop] = value
    return {'owner': spec['entities']['owner'], 'properties': [
        dict(prop, owner_decimal=values[prop['property_no']]) for prop in spec['entities']['properties']]}


def page_source(spec, doc):
    # Retain the reference's Letter stock, margins, Arial, palette, rules, and footer.
    template = (ROOT / 'ref-run1-src/templates/page.html').read_text()
    css = '''
/* Job B: preserve complete sentences and keep each billing row together. */
.page { overflow:visible; }
h1 { margin:15px 0 12px; }
.fields { display:grid; grid-template-columns:1fr 1fr; gap:0 22px; margin:12px 0; }
.field { padding:4px 0; min-height:23px; }
.label { width:120px; }
table { table-layout:fixed; margin:12px 0; font-size:10px; }
td,th { padding:7px 4px; vertical-align:top; }
td { white-space:normal; line-height:1.35; overflow-wrap:break-word; }
tr, .remark { break-inside:avoid; page-break-inside:avoid; }
.number { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.property-name { display:block; font-size:9px; color:#526269; margin-top:3px; }
.totals { display:flex; justify-content:flex-end; gap:28px; padding:10px 0; border-top:2px solid #344d59; }
.note { margin:12px 0; padding:9px 12px; }
.remark { margin:4px 0; line-height:1.45; font-size:11px; }
'''
    template = template.replace('</style>', css + '</style>')
    esc = lambda x: html.escape(str(x), quote=True)
    properties = {p['property_no']: p['name'] for p in spec['entities']['properties']}
    pages = []
    for page_no in range(1, doc['pages'] + 1):
        title = 'Joint Interest Billing' if doc['type'] == 'jib_statement' else 'Vendor invoice'
        fields = [('Document', doc['doc_id']), ('Accounting month', doc['billing_period']),
                  ('Operating company', spec['entities']['operator']), ('Interest holder', spec['entities']['owner']),
                  ('Owner decimal', f"{decimal(doc['owner_decimal']):.6f}"), ('County', spec['entities']['county'])]
        if doc['type'] == 'vendor_invoice':
            fields += [('Vendor', doc['issuer']), ('Bill To', spec['entities']['operator'])]
        content = '<div class="fields">' + ''.join(
            f'<div class="field"><span class="label">{esc(k)}:</span><span class="value">{esc(v)}</span></div>'
            for k, v in fields) + '</div>'
        content += '<table><colgroup>' + ''.join(f'<col style="width:{w}%">' for w in (4, 9, 9, 25, 25, 10, 8, 10)) + '</colgroup>'
        content += '<thead><tr>' + ''.join(f'<th>{h}</th>' for h in ('Line', 'Property', 'Vendor', 'Description', 'Reference', 'Gross', 'Decimal', 'Net')) + '</tr></thead><tbody>'
        for row in doc['lines']:
            if row['page'] != page_no:
                continue
            content += f'<tr data-line="{row["line_no"]}" data-page="{page_no}">'
            for key in ('line_no', 'property_no', 'vendor', 'description', 'reference', 'gross', 'owner_decimal', 'net'):
                val = money(row[key]) if key in ('gross', 'net') else f"{decimal(row[key]):.6f}" if key == 'owner_decimal' else row[key]
                cls = ' class="number"' if key in ('gross', 'owner_decimal', 'net') else ''
                content += f'<td data-field="{key}"{cls}>{esc(val)}'
                if key == 'property_no':
                    content += f'<span class="property-name">{esc(properties[row[key]])}</span>'
                content += '</td>'
            content += '</tr>'
        content += '</tbody></table>'
        if page_no == doc['pages']:
            content += '<div class="totals">' + ''.join(
                f'<span data-total="{k}">{k.replace("_", " ").capitalize()}: <b>{money(v)}</b></span>'
                for k, v in totals(doc).items()) + '</div>'
        page_lines = {row['line_no'] for row in doc['lines'] if row['page'] == page_no}
        remarks = [r for r in doc['remarks'] if r['names_line'] in page_lines]
        if remarks:
            content += '<div class="note">' + ''.join(f'<p class="remark" data-remark="{r["remark_id"]}">{esc(r["text"])}</p>' for r in remarks) + '</div>'
        pages.append(f'<section class="page" data-page="{page_no}"><div class="eyebrow">OPERATIONS / OWNER RECORD</div><h1>{title}</h1>{content}<footer>SYNTHETIC STUDY DOCUMENT - NOT VALID FOR PAYMENT</footer></section>')
    return template.replace('$pages', ''.join(pages))


def source_only():
    spec = read_json(ROOT / 'case_spec_b.json')
    (ROOT / 'src').mkdir(exist_ok=True)
    (ROOT / 'clean').mkdir(exist_ok=True)
    manifest = {'synthetic': True, 'seed': spec['seed'], 'spec_sha256': sha(ROOT / 'case_spec_b.json'),
                'rounding': 'Decimal ROUND_HALF_EVEN to cents per line; totals sum printed line amounts.',
                'scan': 'Not generated (D-286).', 'documents': [],
                'truth': 'truth_b.json', 'references': ['reference/afe_register.json', 'reference/doi.json']}
    for doc in spec['documents']:
        path = ROOT / 'src' / (doc['doc_id'] + '.html')
        path.write_text(page_source(spec, doc))
        manifest['documents'].append({k: doc[k] for k in ('doc_id', 'split', 'type', 'pages')} |
            {'source': str(path.relative_to(ROOT)), 'clean': f'clean/{doc["doc_id"]}.pdf',
             'source_sha256': sha(path), 'line_count': len(doc['lines']), 'remark_count': len(doc['remarks']), **totals(doc)})
    dump('truth_b.json', truth(spec))
    dump('reference/afe_register.json', spec['afe_register'])
    dump('reference/doi.json', doi(spec))
    dump('manifest_b.json', manifest)
    print(f'SOURCE ONLY: {len(spec["documents"])} HTML documents; no Chrome, PDFs, or scan set generated.')


def render_only():
    # A failed source gate must stop rendering; the post-render gate is mandatory too.
    subprocess.run([sys.executable, str(ROOT / 'check_b.py'), '--sources-only'], check=True, cwd=ROOT)
    manifest = read_json(ROOT / 'manifest_b.json')
    (ROOT / 'scratch').mkdir(exist_ok=True)
    (ROOT / 'clean').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chrome-b-', dir=ROOT / 'scratch') as tmp:
        for doc in manifest['documents']:
            output = Path(tmp) / (doc['doc_id'] + '.pdf')
            args = [CHROME, '--headless=new', '--user-data-dir=' + str(Path(tmp) / 'profile'),
                    '--no-sandbox', '--disable-gpu', '--disable-background-networking',
                    '--disable-component-update', '--disable-sync', '--disable-extensions',
                    '--no-first-run', '--no-default-browser-check', '--disable-crash-reporter',
                    '--disable-breakpad', '--metrics-recording-only', '--host-resolver-rules=MAP * ~NOTFOUND',
                    '--no-pdf-header-footer', '--print-to-pdf=' + str(output), (ROOT / doc['source']).as_uri()]
            with (ROOT / 'scratch/chrome-b.log').open('a') as log:
                env = dict(os.environ, TMPDIR=tmp, XDG_CACHE_HOME=str(Path(tmp) / 'cache'))
                proc = subprocess.Popen(args, stdout=log, stderr=log, cwd=ROOT, env=env)
                try:
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        if output.exists() and output.read_bytes().rstrip().endswith(b'%%EOF'):
                            break
                        if proc.poll() is not None:
                            raise RuntimeError(f'Chrome exited before printing {doc["doc_id"]}; see scratch/chrome-b.log')
                        time.sleep(.2)
                    else:
                        raise RuntimeError(f'Chrome timed out: {doc["doc_id"]}')
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
            output.replace(ROOT / doc['clean'])
            print('RENDERED:', doc['clean'], flush=True)
    subprocess.run([sys.executable, str(ROOT / 'check_b.py')], check=True, cwd=ROOT)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source-only', action='store_true')
    mode.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    if args.source_only:
        source_only()
    else:
        render_only()
