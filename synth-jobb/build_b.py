#!/usr/bin/env python3
"""Deterministic, offline Job B authoring. Never executes reference code."""
import argparse
import hashlib
import html
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
HEADERS = ['Line', 'Property', 'Description', 'Reference', 'Vendor', 'Gross', 'Decimal', 'Net']
WIDTHS = [27, 59, 174, 154, 104, 66, 60, 66]
LABELS = ['claim_type', 'reference_kind', 'placeholder_style', 'property_match', 'authority_kind', 'outcome', 'difficulty']
CSS = '''
@page { size: Letter; margin: 0; }
* { box-sizing: border-box; }
body { margin:0; color:#19252a; font-family:Arial,sans-serif; font-size:12px; }
.page { width:8.5in; height:11in; padding:.55in .55in .5in; position:relative; break-after:page; }
.page:last-child { break-after:auto; }
.eyebrow { font-size:10px; letter-spacing:2px; color:#526269; border-bottom:3px solid #344d59; padding-bottom:10px; }
h1 { font-size:25px; margin:16px 0 12px; font-weight:500; }
.fields { margin:10px 0; }
.field { display:flex; padding:3px 0; border-bottom:1px solid #d6dddf; min-height:20px; }
.label { width:130px; flex-shrink:0; color:#42545b; }
.value { font-weight:600; }
table { width:100%; table-layout:fixed; border-collapse:collapse; margin:14px 0 10px; font-size:10px; line-height:1.3; }
th { background:#e4ebed; text-align:left; font-weight:600; padding:8px 3px; white-space:nowrap; }
td { padding:6px 3px; border-bottom:1px solid #c1cdd1; vertical-align:top; white-space:normal; overflow-wrap:normal; }
tr { break-inside:avoid; page-break-inside:avoid; }
td.money, td.decimal { text-align:right; white-space:nowrap; }
.totals { font-size:11px; margin:8px 0; display:flex; justify-content:space-between; }
.note { border-left:3px solid #a5b6bd; padding:8px 10px; margin:12px 0; background:#f1f4f4; font-size:10px; line-height:1.4; }
.note p { margin:0 0 5px; break-inside:avoid; }
.note p:last-child { margin-bottom:0; }
footer { position:absolute; bottom:.33in; left:.55in; right:.55in; border-top:1px solid #abb9bf; padding-top:8px; color:#64747b; font-size:9px; }
'''

def load_spec():
    return json.loads((ROOT / 'case_spec_b.json').read_text())

def money(value):
    return f'{Decimal(str(value)):,.2f}'

def net(line):
    return (Decimal(str(line['gross'])) * Decimal(str(line['owner_decimal']))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def totals(lines):
    return {k: money(sum((Decimal(str(l[k])) for l in lines), Decimal(0))) for k in ['gross', 'net_amount']}

def cells(line):
    return [str(line['line_no']), line['property_no'], line['description'], line['reference'], line['vendor'], money(line['gross']), f"{line['owner_decimal']:.6f}", money(line['net_amount'])]

def truth(spec):
    return {'seed': spec['seed'], 'lines': [dict(split=d['split'], doc_id=d['doc_id'], property=l['property_no'], **l) for d in spec['documents'] for l in d['lines']], 'remarks': [dict(split=d['split'], doc_id=d['doc_id'], **r) for d in spec['documents'] for r in d['remarks']]}

def doi(spec):
    result = []
    for prop in spec['entities']['properties']:
        decimals = {l['owner_decimal'] for d in spec['documents'] for l in d['lines'] if l['property_no'] == prop['property_no']}
        if len(decimals) != 1:
            raise ValueError(f'Nonunique owner decimal for {prop}')
        result.append(dict(**prop, owner=spec['entities']['owner'], owner_decimal=decimals.pop()))
    return result

def document_html(doc, spec):
    esc = html.escape
    pages = []
    for p in range(1, doc['pages'] + 1):
        lines = [l for l in doc['lines'] if l['page'] == p]
        title = 'Joint Interest Billing' if doc['type'] == 'jib_statement' else 'Vendor invoice'
        fields = [('Document', doc['doc_id']), ('Billing period', doc['billing_period']), ('Operator', spec['entities']['operator']), ('Owner', spec['entities']['owner'])]
        if doc['vendor']:
            fields.append(('Vendor', doc['vendor']))
        content = '<div class="fields">' + ''.join(f'<div class="field"><span class="label">{esc(k)}:</span><span class="value">{esc(v)}</span></div>' for k, v in fields) + '</div>'
        content += '<table><colgroup>' + ''.join(f'<col style="width:{w / sum(WIDTHS) * 100:.6f}%" />' for w in WIDTHS) + '</colgroup><thead><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS) + '</tr></thead><tbody>'
        for l in lines:
            content += f'<tr data-line="{l["line_no"]}">' + ''.join(f'<td class="{("money" if i in (5, 7) else "decimal" if i == 6 else "text")}">{esc(v)}</td>' for i, v in enumerate(cells(l))) + '</tr>'
        content += '</tbody></table>'
        for title_total, rows, cls in [('Page totals', lines, 'page-totals')] + ([('Document totals', doc['lines'], 'document-totals')] if p == doc['pages'] else []):
            t = totals(rows)
            content += f'<div class="totals {cls}"><span>{title_total}</span><span>Gross: {t["gross"]}</span><span>Net: {t["net_amount"]}</span></div>'
        remarks = [r for r in doc['remarks'] if r['page'] == p]
        if remarks:
            content += '<div class="note">' + ''.join(f'<p data-remark="{r["remark_id"]}">{esc(r["text"])}</p>' for r in remarks) + '</div>'
        pages.append(f'<section class="page" data-page="{p}"><div class="eyebrow">OPERATIONS / OWNER RECORD</div><h1>{title}</h1>{content}<footer>SYNTHETIC STUDY DOCUMENT - NOT VALID FOR PAYMENT | {esc(doc["doc_id"])} | Page {p} of {doc["pages"]}</footer></section>')
    return '<!doctype html><html><head><meta charset="utf-8" /><title>' + esc(doc['doc_id']) + '</title><style>' + CSS + '</style></head><body>' + ''.join(pages) + '</body></html>\n'

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_only():
    spec = load_spec()
    for d in spec['documents']:
        for l in d['lines']:
            if net(l) != Decimal(str(l['net_amount'])):
                raise ValueError(f"Spec arithmetic mismatch: {d['doc_id']}:{l['line_no']}")
    (ROOT / 'sources').mkdir(exist_ok=True)
    (ROOT / 'clean').mkdir(exist_ok=True)
    for d in spec['documents']:
        (ROOT / 'sources' / (d['doc_id'] + '.html')).write_text(document_html(d, spec))
    dump(ROOT / 'truth_b.json', truth(spec))
    dump(ROOT / 'reference/afe_register.json', spec['afe_register'])
    dump(ROOT / 'reference/doi.json', doi(spec))
    manifest = {'seed': spec['seed'], 'spec_sha256': sha(ROOT / 'case_spec_b.json'), 'rounding': 'ROUND_HALF_UP to cents per line; totals sum rounded line amounts', 'scan_status': 'Not generated (D-286)', 'documents': [dict(doc_id=d['doc_id'], split=d['split'], type=d['type'], pages=d['pages'], line_count=len(d['lines']), remark_count=len(d['remarks']), source=f"sources/{d['doc_id']}.html", pdf=f"clean/{d['doc_id']}.pdf", source_sha256=sha(ROOT / 'sources' / (d['doc_id'] + '.html')), totals=totals(d['lines'])) for d in spec['documents']]}
    dump(ROOT / 'manifest_b.json', manifest)
    print(f"Wrote {len(spec['documents'])} HTML documents, truth, references, and manifest.")

def chrome_print(args, timeout=90, **_ignored):
    """Brain-side fix (full build 2026-10-08): Chrome writes the PDF but may not exit. Poll for a complete
    PDF, then stop Chrome, as the run 1 generator does."""
    import time, types
    out = Path(next(a.split('=', 1)[1] for a in args if a.startswith('--print-to-pdf=')))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if out.exists() and out.read_bytes().rstrip().endswith(b'%%EOF'):
            time.sleep(0.3)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
            return types.SimpleNamespace(returncode=0, stderr='')
        if proc.poll() is not None and not out.exists():
            return types.SimpleNamespace(returncode=proc.returncode or 1, stderr=proc.stderr.read())
        time.sleep(0.2)
    proc.kill(); proc.wait()
    return types.SimpleNamespace(returncode=1, stderr='Chrome PDF timeout')

def render_only():
    manifest = json.loads((ROOT / 'manifest_b.json').read_text())
    if sha(ROOT / 'case_spec_b.json') != manifest['spec_sha256']:
        raise ValueError('Spec changed; rebuild sources before rendering.')
    (ROOT / 'clean').mkdir(exist_ok=True)
    for d in manifest['documents']:
        source = ROOT / d['source']
        if sha(source) != d['source_sha256']:
            raise ValueError(f'Source changed: {source}')
        # An isolated local profile avoids using or changing the browser session.
        with tempfile.TemporaryDirectory(prefix='chrome-b-', dir=ROOT) as profile:
            temporary_pdf = Path(profile) / 'output.pdf'
            result = chrome_print([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--metrics-recording-only', '--host-resolver-rules=MAP * ~NOTFOUND', f'--user-data-dir={profile}', '--no-pdf-header-footer', '--print-to-pdf-no-header', f'--print-to-pdf={temporary_pdf}', source.as_uri()], capture_output=True, text=True, timeout=90)
            if result.returncode or not temporary_pdf.exists() or not temporary_pdf.read_bytes().rstrip().endswith(b'%%EOF'):
                raise RuntimeError(f"Chrome failed for {d['doc_id']}: {result.stderr[-1500:]}")
            temporary_pdf.replace(ROOT / d['pdf'])
        print(f"Rendered {d['pdf']}", flush=True)
    # Rendering is not complete until the build gate passes.
    return subprocess.run([sys.executable, str(ROOT / 'check_b.py')], cwd=ROOT).returncode

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source-only', action='store_true')
    group.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    if args.source_only:
        source_only()
    else:
        sys.exit(render_only())
