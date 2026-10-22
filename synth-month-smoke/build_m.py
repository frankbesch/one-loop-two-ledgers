#!/usr/bin/env python3
"""Fixed-spec, offline source authoring and separately invoked Chrome rendering."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess
import time
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FIELDS = {'property': 'property_printed', 'decimal': 'owner_decimal', 'net': 'net_amount'}
WIDTHS = dict(line_no=5, property=10, account=6, description=12, reference=13,
              vendor=11, invoice_no=8, service_date=8, quantity=4, unit_rate=5,
              gross=6, decimal=6, net=7)
LEDGER_FIELDS = 'doc_id line_no property_printed vendor invoice_no service_date reference gross net_amount'.split()


def read_spec():
    return json.loads((ROOT / 'case_spec_m.json').read_text())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def printed(value):
    return '' if value is None else str(value)


def esc(value):
    return html.escape(printed(value))


def total(lines, key):
    return str(sum((Decimal(str(l[key])) for l in lines), Decimal('0')))


def ledger(spec, month):
    return [{k: ({'doc_id': d['doc_id'], **l})[k] for k in LEDGER_FIELDS}
            for d in spec['documents'] if d['month'] < month for l in d['lines']]


CSS = '''
@page { size: Letter landscape; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; color: #19252a; font-family: Arial, sans-serif; font-size: 10px; }
.page { width: 11in; height: 8.5in; padding: .4in; position: relative; break-after: page; }
.page:last-child { break-after: auto; }
.eyebrow { font-size: 10px; letter-spacing: 2px; color: #526269; border-bottom: 3px solid #344d59; padding-bottom: 8px; }
h1 { font-size: 23px; font-weight: 500; margin: 12px 0; }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 5px 16px; margin-bottom: 12px; }
.field { border-bottom: 1px solid #d6dddf; padding: 3px 0; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin: 12px 0; font-size: 9px; line-height: 11px; }
th { font-size: 8px; line-height: 10px; background: #e4ebed; text-align: left; font-weight: 600; padding: 6px 4px; vertical-align: top; }
td { border-bottom: 1px solid #c1cdd1; padding: 6px 4px; vertical-align: top; overflow-wrap: normal; word-break: normal; }
tr { break-inside: avoid; page-break-inside: avoid; }
.note { border-left: 3px solid #a5b6bd; padding: 7px 10px; margin: 10px 0; background: #f1f4f4; line-height: 14px; }
.remark { margin: 3px 0; break-inside: avoid; }
.totals { text-align: right; padding-top: 5px; font-weight: 600; }
footer { position: absolute; bottom: .2in; left: .4in; right: .4in; border-top: 1px solid #abb9bf; padding-top: 6px; color: #64747b; font-size: 8px; }
'''


def source_only():
    s = read_spec()
    for name in ('sources', 'reference', 'clean'):
        (ROOT / name).mkdir(exist_ok=True)
    truth = {'lines': [], 'remarks': []}
    manifest = {'spec_sha256': hashlib.sha256((ROOT / 'case_spec_m.json').read_bytes()).hexdigest(),
                'seed': s['seed'], 'page_size_points': [792, 612], 'margin_points': 28.8,
                'column_width_percent': WIDTHS, 'documents': []}
    periods = {m['month']: m['billing_period'] for m in s['months']}
    for d in s['documents']:
        f = s['formats'][d['format']]
        order = f['column_order']
        pages = []
        for p in range(1, d['pages'] + 1):
            lines = [l for l in d['lines'] if l['page'] == p]
            remarks = [r for r in d['remarks'] if r['page'] == p]
            meta = [('Document', d['doc_id']), ('Billing period', periods[d['month']]),
                    ('Operator', s['entities']['operator']), ('Owner', s['entities']['owner'])]
            if d['vendor'] is not None:
                meta.append(('Vendor', d['vendor']))
            title = 'Joint Interest Billing' if d['type'] == 'jib_statement' else 'Vendor invoice'
            content = f'<section class="page" data-page="{p}"><div class="eyebrow">OPERATIONS / OWNER RECORD</div><h1>{title}</h1><div class="fields">'
            content += ''.join(f'<div class="field">{k}: <strong>{esc(v)}</strong></div>' for k, v in meta)
            content += '</div><table><colgroup>' + ''.join(f'<col style="width:{100 * WIDTHS[k] / sum(WIDTHS.values()):.10f}%" />' for k in order) + '</colgroup><thead><tr>'
            content += ''.join(f'<th>{esc(f["headers"][k])}</th>' for k in order) + '</tr></thead><tbody>'
            for l in lines:
                content += f'<tr data-line="{l["line_no"]}">' + ''.join(
                    f'<td data-field="{FIELDS.get(k,k)}">{esc(l[FIELDS.get(k,k)])}</td>' for k in order) + '</tr>'
            content += '</tbody></table>'
            if remarks:
                content += '<div class="note">' + ''.join(f'<p class="remark" data-remark="{r["remark_id"]}">{esc(r["text"])}</p>' for r in remarks) + '</div>'
            if p == d['pages']:
                content += f'<div class="totals" data-gross="{total(d["lines"],"gross")}" data-net="{total(d["lines"],"net_amount")}">Document total (gross): {total(d["lines"],"gross")} &#160; Document total (net): {total(d["lines"],"net_amount")}</div>'
            content += f'<footer>SYNTHETIC STUDY DOCUMENT - NOT VALID FOR PAYMENT | {esc(d["doc_id"])} | {p} / {d["pages"]}</footer></section>'
            pages.append(content)
        source = ROOT / 'sources' / (d['doc_id'] + '.html')
        source.write_text('<!DOCTYPE html><html><head><meta charset="utf-8" /><style>' + CSS + '</style></head><body>' + ''.join(pages) + '</body></html>')
        truth['lines'].extend({'month': d['month'], 'doc_id': d['doc_id'], **l} for l in d['lines'])
        truth['remarks'].extend({'month': d['month'], 'doc_id': d['doc_id'], **r} for r in d['remarks'])
        manifest['documents'].append({k: d[k] for k in ('doc_id', 'month', 'type', 'format', 'pages')} | {
            'source': str(source.relative_to(ROOT)), 'pdf': f'clean/{d["doc_id"]}.pdf',
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'gross_total': total(d['lines'], 'gross'), 'net_total': total(d['lines'], 'net_amount')})
    dump(ROOT / 'truth_m.json', truth)
    dump(ROOT / 'manifest_m.json', manifest)
    for key, value in s['reference'].items():
        dump(ROOT / 'reference' / (key + '.json'), value)
    for k in range(2, 7):
        dump(ROOT / 'reference' / f'prior_ledger_m{k}.json', ledger(s, k))
    print(f'SOURCE: {len(s["documents"])} documents, {len(truth["lines"])} lines, {len(truth["remarks"])} remarks.')


def render_only():
    manifest = json.loads((ROOT / 'manifest_m.json').read_text())
    (ROOT / 'clean').mkdir(exist_ok=True)
    (ROOT / 'scratch').mkdir(exist_ok=True)
    for d in manifest['documents']:
        source, output = ROOT / d['source'], ROOT / d['pdf']
        if hashlib.sha256(source.read_bytes()).hexdigest() != d['source_sha256']:
            raise RuntimeError(f'Source hash changed: {source}')
        output.unlink(missing_ok=True)
        with (ROOT / 'scratch' / 'chrome.log').open('a') as log:
            proc = subprocess.Popen([CHROME, '--headless', '--disable-gpu', '--no-sandbox',
                '--no-pdf-header-footer', '--disable-background-networking', '--disable-component-update',
                '--disable-sync', '--no-first-run', '--no-default-browser-check',
                '--user-data-dir=' + str(ROOT / 'scratch' / 'chrome-profile'),
                '--print-to-pdf=' + str(output), source.as_uri()], stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 90
                while True:
                    if output.exists() and output.read_bytes().rstrip().endswith(b'%%EOF'):
                        break
                    if proc.poll() is not None:
                        raise RuntimeError(f'Chrome exited before complete PDF: {d["doc_id"]}')
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f'Chrome PDF timeout: {d["doc_id"]}')
                    time.sleep(.2)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
        print('RENDERED:', output.relative_to(ROOT))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--source-only', action='store_true')
    modes.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    source_only() if args.source_only else render_only()
