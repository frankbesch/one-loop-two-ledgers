#!/usr/bin/env python3
"""Offline deterministic certificate sources and separately invoked Chrome rendering."""
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
ENDS = {1: '2025-03-31', 2: '2025-06-30', 3: '2025-09-30', 4: '2025-12-31'}
HEADINGS = ['Quarterly Compliance Certificate', 'Schedule 1: Consolidated EBITDA (last four quarters)', 'Addbacks', 'Adjusted EBITDA', 'Schedule 2: Financial covenants']
CSS = '''@page { size: Letter portrait; margin: 0.55in; }
* { box-sizing: border-box; } body { margin:0; font-family:Arial,sans-serif; font-size:10pt; line-height:1.35; color:#202a32; }
.page { break-after:page; } .page:last-child { break-after:auto; }
h1 { font-size:20pt; margin:0 0 18px; border-bottom:2px solid #344957; padding-bottom:12px; }
h2 { font-size:13pt; margin:20px 0 10px; } h3 { font-size:11pt; margin:0 0 10px; }
p { margin:7px 0; } .header p { margin:4px 0; } ol { padding-left:22px; margin:20px 0; } li { padding-left:4px; margin-bottom:12px; }
table { width:100%; border-collapse:collapse; margin:8px 0 14px; table-layout:fixed; }
th { text-align:left; background:#edf0f2; font-weight:600; } td,th { padding:7px 5px; border-bottom:1px solid #c9cfd4; vertical-align:top; }
tr { break-inside:avoid; } .num { text-align:right; white-space:nowrap; } .addbacks { font-size:8.5pt; line-height:1.3; }
.covenants { font-size:8.5pt; } .covenants th { font-size:8pt; } .date { white-space:nowrap; } .certification { margin:12px 0; }
.signature { margin-top:20px; border-top:1px solid #8e9aa3; padding-top:8px; break-inside:avoid; } .signature p { margin:3px 0; }
'''

def read_spec():
    return json.loads((ROOT/'case_spec_q.json').read_text())

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')

def esc(value):
    return html.escape(str(value), quote=True)

def money(value):
    value = Decimal(str(value))
    if value != value.to_integral_value():
        raise ValueError('Spec money is not whole dollars')
    return f'${int(value):,}'

def ratio(value):
    return f'{Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP):.2f}x'

def statements(c):
    return [f'The financial statements of the Borrower for the fiscal quarter ended {ENDS[c["quarter"]]} required by the reporting section of the Credit Agreement have been delivered to the Administrative Agent.',
            'Those financial statements fairly present the financial condition and results of operations of the Borrower under GAAP, subject to normal year-end audit adjustments.',
            "The undersigned has reviewed the Credit Agreement and has made, or caused to be made under the undersigned's supervision, a review of the transactions and condition of the Borrower during the quarter.",
            'To the knowledge of the undersigned, no Default has occurred and is continuing.' if c['statement_4']=='no_default' else 'The following Default has occurred and is continuing: '+c['defaults_text']]

def certificate_html(s, c):
    a = next(a for a in s['agreements'] if a['borrower_id']==c['borrower_id'])
    out = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>'+esc(c['cert_id'])+'</title><style>'+CSS+'</style></head><body><section class="page">'
    out += '<h1>'+HEADINGS[0]+'</h1><div class="header">'
    for value in [f'To: {s["bank"]["name"]}, as Administrative Agent', f'Borrower: {a["borrower"]}', f'Credit Agreement dated: {a["agreement_date"]}', f'Fiscal quarter ended: {ENDS[c["quarter"]]}', f'Date delivered: {c["delivery_date"]}']:
        out += '<p>'+esc(value)+'</p>'
    out += '</div><ol>'+''.join('<li>'+esc(t)+'</li>' for t in statements(c))+'</ol>'
    out += '<h2>'+HEADINGS[1]+'</h2><table><tbody>'
    for label,key in [('Net income','net_income'),('Interest expense','interest_expense'),('Income taxes','income_taxes'),('Depreciation and amortization','d_and_a'),('Unadjusted EBITDA','unadjusted')]:
        out += f'<tr><td>{label}</td><td class="num">{money(c["ebitda"][key])}</td></tr>'
    out += '</tbody></table></section><section class="page"><h3>Addbacks</h3><table class="addbacks"><colgroup>'
    out += ''.join(f'<col style="width:{w}%">' for w in [5,43,19,16,17])+'</colgroup><thead><tr>'
    out += ''.join('<th>'+h+'</th>' for h in ['No.','Description','Category','Amount','Action date'])+'</tr></thead><tbody>'
    for row in c['addbacks']:
        out += '<tr>'+''.join(f'<td class="{cls}">{esc(value)}</td>' for value,cls in [(row['addback_no'],''),(row['description'],''),(row['category_printed'],''),(money(row['amount']),'num'),(row['action_date'],'date')])+'</tr>'
    out += '</tbody></table>'
    if c['cure']:
        out += '<p>Equity cure contribution: '+money(c['cure']['amount'])+'</p><p>Date received: '+esc(c['cure']['date'])+'</p><p>Applied to Consolidated EBITDA for the quarter.</p>'
    out += '<h3>Adjusted EBITDA</h3><p>'+money(c['adjusted_ebitda_printed'])+'</p>'
    if c['certification']['present']:
        out += '<p class="certification">Officer certification of cost savings: '+esc(c['certification']['text'])+'</p>'
    out += '<h2>'+HEADINGS[4]+'</h2><table class="covenants"><colgroup>'+''.join(f'<col style="width:{w}%">' for w in [19,19,19,10,22,11])+'</colgroup><thead><tr>'
    out += ''.join('<th>'+h+'</th>' for h in ['Covenant','Input','Adjusted EBITDA','Ratio','Threshold','Status'])+'</tr></thead><tbody>'
    for row in c['covenants']:
        lev = row['covenant']=='leverage'
        values = ['Total leverage' if lev else 'Interest coverage',money(row['input']),money(c['adjusted_ebitda_printed']),ratio(row['ratio_printed']),('Maximum ' if lev else 'Minimum ')+ratio(row['threshold_printed']),row['status_printed'].title()]
        out += '<tr>'+''.join('<td>'+esc(v)+'</td>' for v in values)+'</tr>'
    out += '</tbody></table><div class="signature">'
    for k,v in [('Name',c['signer_name']),('Title',c['signer_title']),('Date',c['delivery_date'])]:
        out += '<p>'+esc(k+': '+v)+'</p>'
    return out+'</div></section></body></html>\n'

def history(s, k):
    return [dict(r) for r in s['prior_cures']]+[{'borrower_id':c['borrower_id'],'quarter_label':f'2025-Q{c["quarter"]}','amount':c['cure']['amount']} for c in s['certificates'] if c['quarter']<k and c['cure']]

def source_only():
    s = read_spec()
    (ROOT/'sources').mkdir(exist_ok=True)
    (ROOT/'clean').mkdir(exist_ok=True)
    manifest = {'spec_sha256':hashlib.sha256((ROOT/'case_spec_q.json').read_bytes()).hexdigest(),'certificates':[]}
    for c in s['certificates']:
        content = certificate_html(s,c)
        name = f'sources/{c["cert_id"]}.html'
        (ROOT/name).write_text(content)
        manifest['certificates'].append({'cert_id':c['cert_id'],'quarter':c['quarter'],'borrower_id':c['borrower_id'],'split':c['split'],'pages':2,'source':name,'pdf':f'clean/{c["cert_id"]}.pdf','source_sha256':hashlib.sha256(content.encode()).hexdigest()})
    dump(ROOT/'truth_q.json',{'units':[dict(u,quarter=c['quarter'],cert_id=c['cert_id'],borrower_id=c['borrower_id']) for c in s['certificates'] for u in c['units']]})
    dump(ROOT/'reference/agreements.json',s['agreements'])
    dump(ROOT/'reference/categories.json',s['categories'])
    for k in range(1,5):
        dump(ROOT/f'reference/prior_cures_q{k}.json',history(s,k))
    dump(ROOT/'manifest_q.json',manifest)
    print(f'SOURCE ONLY: {len(s["certificates"])} certificates. Chrome was not started.')

def render_only():
    manifest = json.loads((ROOT/'manifest_q.json').read_text())
    if hashlib.sha256((ROOT/'case_spec_q.json').read_bytes()).hexdigest()!=manifest['spec_sha256']:
        raise RuntimeError('Spec changed; rebuild sources first')
    (ROOT/'clean').mkdir(exist_ok=True)
    profile = ROOT/'chrome-profile-q'
    for c in manifest['certificates']:
        source, output = ROOT/c['source'], ROOT/c['pdf']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:
            raise RuntimeError(f'Source changed: {source}')
        if output.exists():
            output.unlink()
        args = [CHROME,'--headless','--disable-gpu','--no-sandbox','--no-pdf-header-footer','--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check',f'--user-data-dir={profile}',f'--print-to-pdf={output}',source.as_uri()]
        with (ROOT/'chrome_q.log').open('a') as log:
            proc = subprocess.Popen(args,stdout=log,stderr=log)
            try:
                deadline = time.monotonic()+90
                while True:
                    if output.exists() and output.read_bytes().rstrip().endswith(b'%%EOF'):
                        break
                    if proc.poll() is not None:
                        raise RuntimeError(f'Chrome exited before completing {output.name}; see chrome_q.log')
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
        print(f'Rendered {output.name}',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source-only',action='store_true')
    mode.add_argument('--render-only',action='store_true')
    args=parser.parse_args()
    source_only() if args.source_only else render_only()
