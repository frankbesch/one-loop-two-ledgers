#!/usr/bin/env python3
"""Deterministic, offline corpus authoring. Never runs the reference builder."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess
import time
from decimal import Decimal, ROUND_HALF_UP

ROOT = Path(__file__).resolve().parent
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FIELD = {'property': 'property_printed', 'decimal': 'owner_decimal', 'net': 'net_amount'}
WEIGHTS = dict(zip(['line_no','property','account','description','reference','vendor','invoice_no','service_date','quantity','unit_rate','gross','decimal','net'], [3,9,5,12,14,10,8,7,4,6,7,7,8]))
LEDGER = ['doc_id','line_no','property_printed','vendor','invoice_no','service_date','reference','gross','net_amount']
CSS = '''@page { size:17in 11in; margin:0; }
* { box-sizing:border-box; } body { margin:0; color:#19252a; font-family:Arial,sans-serif; font-size:12px; }
.page { width:17in; height:11in; padding:0.42in 0.55in 0.55in; position:relative; break-after:page; }
.page:last-child { break-after:auto; }
.eyebrow { font-size:10px; letter-spacing:2px; color:#526269; border-bottom:3px solid #344d59; padding-bottom:10px; }
h1 { font-size:25px; margin:14px 0 10px; font-weight:500; }
.fields { display:flex; flex-wrap:wrap; gap:6px 28px; margin:8px 0 12px; }
.field { border-bottom:1px solid #d6dddf; padding:3px 0; } .label { color:#42545b; } .value { font-weight:600; }
table { width:100%; border-collapse:collapse; table-layout:fixed; font-size:11px; margin:12px 0; }
th { background:#e4ebed; text-align:left; font-weight:600; padding:9px 5px; vertical-align:top; line-height:14px; }
td { padding:9px 5px; border-bottom:1px solid #c1cdd1; vertical-align:top; line-height:14px; }
tr, td, th { break-inside:avoid; } .number { white-space:nowrap; }
.totals { display:flex; gap:32px; justify-content:flex-end; font-size:12px; margin:10px 0; }
.note { border-left:3px solid #a5b6bd; padding:8px 12px; margin:8px 0; background:#f1f4f4; line-height:16px; }
footer { position:absolute; bottom:0.25in; left:0.55in; right:0.55in; border-top:1px solid #abb9bf; padding-top:8px; color:#64747b; font-size:9px; }
'''

def read_spec():
    return json.loads((ROOT/'case_spec_m.json').read_text())

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')

def money(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

def printed(key, value):
    if value is None:
        return ''
    return money(value) if key in ('gross','net','unit_rate') else str(value)

def esc(value):
    return html.escape(str(value), quote=True)

def totals(lines):
    return {k: money(sum((Decimal(str(l[k])) for l in lines), Decimal(0))) for k in ('gross','net_amount')}

def page_html(spec, doc, page):
    fmt = spec['formats'][doc['format']]
    lines = [l for l in doc['lines'] if l['page']==page]
    month = next(m for m in spec['months'] if m['month']==doc['month'])
    title = 'Joint interest billing statement' if doc['type']=='jib_statement' else 'Vendor invoice'
    fields = [('Document',doc['doc_id']),('Billing period',month['billing_period']),('Operator',spec['entities']['operator']),('Owner',spec['entities']['owner'])]
    if doc['vendor'] is not None:
        fields.append(('Vendor',doc['vendor']))
    out = f'<section class="page" data-page="{page}"><div class="eyebrow">OPERATIONS / OWNER RECORD</div><h1>{title}</h1><div class="fields">'
    out += ''.join(f'<div class="field"><span class="label">{esc(k)}: </span><span class="value">{esc(v)}</span></div>' for k,v in fields)+'</div>'
    order=fmt['column_order']
    out += '<table><colgroup>'+''.join(f'<col style="width:{WEIGHTS[k]/sum(WEIGHTS.values())*100:.8f}%" />' for k in order)+'</colgroup><thead><tr>'
    out += ''.join(f'<th>{esc(fmt["headers"][k])}</th>' for k in order)+'</tr></thead><tbody>'
    for l in lines:
        out += f'<tr data-line="{l["line_no"]}">'
        for k in order:
            cls='number' if k in ('line_no','quantity','unit_rate','gross','decimal','net','service_date') else 'text'
            out += f'<td class="{cls}">{esc(printed(k,l[FIELD.get(k,k)]))}</td>'
        out += '</tr>'
    out += '</tbody></table>'
    for kind, rows in [('Page subtotal',lines)]+([('Document total',doc['lines'])] if page==doc['pages'] else []):
        t=totals(rows)
        out += f'<div class="totals" data-kind="{kind}" data-gross="{t["gross"]}" data-net="{t["net_amount"]}"><strong>{kind}</strong><span>Gross: {t["gross"]}</span><span>Net: {t["net_amount"]}</span></div>'
    for r in doc['remarks']:
        if r['page']==page:
            out += f'<div class="note" data-remark="{r["remark_id"]}">{esc(r["text"])}</div>'
    return out+f'<footer>{esc(doc["doc_id"])} · Page {page} of {doc["pages"]} · SYNTHETIC STUDY DOCUMENT — NOT VALID FOR PAYMENT</footer></section>'

def source_only():
    s=read_spec()
    (ROOT/'sources').mkdir(exist_ok=True)
    (ROOT/'clean').mkdir(exist_ok=True)
    truth={'lines':[], 'remarks':[]}
    manifest={'spec_sha256':hashlib.sha256((ROOT/'case_spec_m.json').read_bytes()).hexdigest(), 'documents':[]}
    for d in s['documents']:
        name=f'sources/{d["doc_id"]}.html'
        content='<!DOCTYPE html><html><head><meta charset="utf-8" /><title>'+esc(d['doc_id'])+'</title><style>'+CSS+'</style></head><body>'
        content+=''.join(page_html(s,d,p) for p in range(1,d['pages']+1))+'</body></html>\n'
        (ROOT/name).write_text(content)
        truth['lines'].extend(dict(month=d['month'], doc_id=d['doc_id'], **l) for l in d['lines'])
        truth['remarks'].extend(dict(month=d['month'], doc_id=d['doc_id'], **r) for r in d['remarks'])
        manifest['documents'].append(dict(doc_id=d['doc_id'], month=d['month'], type=d['type'], format=d['format'], pages=d['pages'], source=name, pdf=f'clean/{d["doc_id"]}.pdf', source_sha256=hashlib.sha256(content.encode()).hexdigest(), totals=totals(d['lines'])))
    dump(ROOT/'truth_m.json',truth)
    for k,v in s['reference'].items():
        dump(ROOT/'reference'/f'{k}.json',v)
    dump(ROOT/'reference/properties.json',[{k:p[k] for k in ('property_no','name')} for p in s['entities']['properties']])
    for k in range(2,7):
        dump(ROOT/'reference'/f'prior_ledger_m{k}.json',[{f:l[f] for f in LEDGER} for l in truth['lines'] if l['month']<k])
    dump(ROOT/'manifest_m.json',manifest)
    print(f'SOURCE ONLY: {len(s["documents"])} documents, {len(truth["lines"])} lines, {len(truth["remarks"])} remarks. Chrome was not started.')

def render_only():
    manifest=json.loads((ROOT/'manifest_m.json').read_text())
    (ROOT/'clean').mkdir(exist_ok=True)
    profile=ROOT/'chrome-profile-m'
    for d in manifest['documents']:
        source=ROOT/d['source']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=d['source_sha256']:
            raise RuntimeError(f'Source changed: {source}')
        output=ROOT/d['pdf']
        if output.exists():
            output.unlink()
        args=[CHROME,'--headless','--disable-gpu','--no-sandbox','--no-pdf-header-footer','--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check',f'--user-data-dir={profile}',f'--print-to-pdf={output}',source.as_uri()]
        with (ROOT/'chrome_m.log').open('a') as log:
            proc=subprocess.Popen(args,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+90
                while True:
                    if output.exists() and output.read_bytes().rstrip().endswith(b'%%EOF'):
                        break
                    if proc.poll() is not None:
                        raise RuntimeError(f'Chrome exited before completing {output.name}; see chrome_m.log')
                    if time.monotonic()>deadline:
                        raise RuntimeError(f'Chrome timeout for {output.name}')
                    time.sleep(.2)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
        print(f'Rendered {output.name}', flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source-only',action='store_true')
    mode.add_argument('--render-only',action='store_true')
    args=parser.parse_args()
    source_only() if args.source_only else render_only()
