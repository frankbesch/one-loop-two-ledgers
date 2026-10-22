#!/usr/bin/env python3
"""Offline quarterly certificate sources and separately invoked Chrome rendering."""
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
QUARTER_END = {1:'2025-03-31',2:'2025-06-30',3:'2025-09-30',4:'2025-12-31'}
HEADINGS = ['Quarterly Compliance Certificate', 'Schedule 1: Consolidated EBITDA (last four quarters)', 'Addbacks', 'Adjusted EBITDA', 'Schedule 2: Financial covenants']
CSS = '''@page { size: Letter portrait; margin: 0.6in; }
* { box-sizing: border-box; } body { font-family: Arial, sans-serif; color: #202830; font-size: 10pt; line-height: 1.35; margin: 0; }
h1 { font-size: 19pt; margin: 0 0 18pt; } h2 { font-size: 12pt; margin: 18pt 0 10pt; border-bottom: 1pt solid #647080; padding-bottom: 5pt; }
h3 { font-size: 11pt; margin: 14pt 0 7pt; } p { margin: 5pt 0; } ol { padding-left: 20pt; margin-top: 20pt; } li { padding-left: 3pt; margin-bottom: 13pt; }
.page { break-after: page; } .page:last-child { break-after: auto; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9pt; table-layout: fixed; }
th { background: #edf0f2; text-align: left; font-weight: bold; } th, td { padding: 7pt 5pt; border-bottom: 0.5pt solid #c8ced3; vertical-align: top; }
tr { break-inside: avoid; } thead { display: table-header-group; } .money, .date { white-space: nowrap; } .money { text-align: right; }
.summary { width: 70%; font-size: 10pt; } .summary td { padding: 5pt; } .summary td:last-child { text-align: right; }
.total { font-weight: bold; margin-top: 12pt; } .certification { margin-top: 13pt; } .signature { margin-top: 22pt; break-inside: avoid; }
'''

def read_spec():
    return json.loads((ROOT/'case_spec_q.json').read_text())

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def esc(v):
    return html.escape(str(v), quote=True)

def money(v):
    d=Decimal(str(v))
    if d != d.to_integral_value():
        raise ValueError(f'Non-whole dollar value: {v}')
    return f'${int(d):,}'

def ratio(v):
    return f'{Decimal(str(v)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP):.2f}x'

def statements(c):
    return [f'The financial statements of the Borrower for the fiscal quarter ended {QUARTER_END[c["quarter"]]} required by the reporting section of the Credit Agreement have been delivered to the Administrative Agent.',
    'Those financial statements fairly present the financial condition and results of operations of the Borrower under GAAP, subject to normal year-end audit adjustments.',
    "The undersigned has reviewed the Credit Agreement and has made, or caused to be made under the undersigned's supervision, a review of the transactions and condition of the Borrower during the quarter.",
    'To the knowledge of the undersigned, no Default has occurred and is continuing.' if c['statement_4']=='no_default' else 'The following Default has occurred and is continuing: '+c['defaults_text']]

def certificate_html(s,c):
    a=next(a for a in s['agreements'] if a['borrower_id']==c['borrower_id'])
    out=['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>'+esc(c['cert_id'])+'</title><style>'+CSS+'</style></head><body><section class="page">', '<h1>'+HEADINGS[0]+'</h1>']
    for text in [f'To: {s["bank"]["name"]}, as Administrative Agent', f'Borrower: {a["borrower"]}', f'Credit Agreement dated: {a["agreement_date"]}', f'Fiscal quarter ended: {QUARTER_END[c["quarter"]]}',f'Date delivered: {c["delivery_date"]}']:
        out.append('<p>'+esc(text)+'</p>')
    out.append('<ol>'+''.join('<li>'+esc(t)+'</li>' for t in statements(c))+'</ol>')
    out.append('<h2>'+HEADINGS[1]+'</h2><table class="summary"><tbody>')
    for label,key in [('Net income','net_income'),('Interest expense','interest_expense'),('Income taxes','income_taxes'),('Depreciation and amortization','d_and_a'),('Unadjusted EBITDA','unadjusted')]:
        out.append(f'<tr><td>{label}</td><td class="money">{money(c["ebitda"][key])}</td></tr>')
    out.append('</tbody></table></section><section class="page"><h3>Addbacks</h3><table><colgroup><col style="width:5%"><col style="width:40%"><col style="width:20%"><col style="width:17%"><col style="width:18%"></colgroup><thead><tr>')
    out.append(''.join('<th>'+t+'</th>' for t in ['No.','Description','Category','Amount','Action date'])+'</tr></thead><tbody>')
    for row in c['addbacks']:
        vals=[row['addback_no'],row['description'],row['category_printed'],money(row['amount']),row['action_date']]
        out.append('<tr>'+''.join(f'<td class="{("money" if i==3 else "date" if i==4 else "")}">{esc(v)}</td>' for i,v in enumerate(vals))+'</tr>')
    out.append('</tbody></table>')
    if c['cure']:
        out.extend(['<p>Equity cure contribution: '+money(c['cure']['amount'])+'</p>', '<p>Date received: '+esc(c['cure']['date'])+'</p>', '<p>Applied to Consolidated EBITDA for the quarter.</p>'])
    out.append('<p class="total">Adjusted EBITDA '+money(c['adjusted_ebitda_printed'])+'</p>')
    if c['certification']['present']:
        out.append('<p class="certification">Officer certification of cost savings: '+esc(c['certification']['text'])+'</p>')
    out.append('<h2>'+HEADINGS[4]+'</h2><table><colgroup><col style="width:19%"><col style="width:18%"><col style="width:18%"><col style="width:10%"><col style="width:24%"><col style="width:11%"></colgroup><thead><tr>')
    out.append(''.join('<th>'+t+'</th>' for t in ['Covenant','Input','Adjusted EBITDA','Ratio','Threshold','Status'])+'</tr></thead><tbody>')
    for cov in c['covenants']:
        lev=cov['covenant']=='leverage'
        vals=['Total leverage' if lev else 'Interest coverage',money(cov['input']),money(c['adjusted_ebitda_printed']),ratio(cov['ratio_printed']),('Maximum ' if lev else 'Minimum ')+ratio(cov['threshold_printed']),cov['status_printed'].capitalize()]
        out.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in vals)+'</tr>')
    out.append('</tbody></table><div class="signature">')
    for label,key in [('Name','signer_name'),('Title','signer_title'),('Date','delivery_date')]:
        out.append('<p>'+label+': '+esc(c[key])+'</p>')
    return ''.join(out)+'</div></section></body></html>\n'

def prior_cures(s,k):
    # The spec also caches 2025 cures here; derive these once from printed certificates.
    return [dict(r) for r in s['prior_cures'] if int(r['quarter_label'][:4])<2025]+[dict(borrower_id=c['borrower_id'],quarter_label=f'2025-Q{c["quarter"]}',amount=c['cure']['amount']) for c in s['certificates'] if c['quarter']<k and c['cure']]

def source_only():
    s=read_spec()
    for name in ['sources','clean','reference']:
        (ROOT/name).mkdir(exist_ok=True)
    manifest={'spec_sha256':digest((ROOT/'case_spec_q.json').read_bytes()), 'certificates':[]}
    for c in s['certificates']:
        source=f'sources/{c["cert_id"]}.html'
        content=certificate_html(s,c)
        (ROOT/source).write_text(content,encoding='utf-8')
        manifest['certificates'].append(dict(cert_id=c['cert_id'],quarter=c['quarter'],borrower_id=c['borrower_id'],source=source,pdf=f'clean/{c["cert_id"]}.pdf',pages=2,source_sha256=digest(content.encode())))
    dump(ROOT/'truth_q.json',{'units':[u for c in s['certificates'] for u in c['units']]})
    dump(ROOT/'reference/agreements.json',s['agreements'])
    dump(ROOT/'reference/categories.json',s['categories'])
    for k in range(1,5):
        dump(ROOT/f'reference/prior_cures_q{k}.json',prior_cures(s,k))
    dump(ROOT/'manifest_q.json',manifest)
    print(f'SOURCE ONLY: {len(s["certificates"])} certificates; Chrome was not started.')

def render_only():
    m=json.loads((ROOT/'manifest_q.json').read_text())
    if m['spec_sha256']!=digest((ROOT/'case_spec_q.json').read_bytes()):
        raise RuntimeError('Spec changed since source generation')
    (ROOT/'clean').mkdir(exist_ok=True)
    profile=ROOT/'chrome-profile-q'
    for c in m['certificates']:
        source=ROOT/c['source']; output=ROOT/c['pdf']
        if digest(source.read_bytes())!=c['source_sha256']:
            raise RuntimeError(f'Source changed: {source}')
        if output.exists():
            output.unlink()
        args=[CHROME,'--headless','--disable-gpu','--no-sandbox','--no-pdf-header-footer','--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check',f'--user-data-dir={profile}',f'--print-to-pdf={output}',source.as_uri()]
        with (ROOT/'chrome_q.log').open('a') as log:
            proc=subprocess.Popen(args,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+90
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
                        proc.kill(); proc.wait()
        print(f'Rendered {output.name}',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source-only',action='store_true')
    mode.add_argument('--render-only',action='store_true')
    args=p.parse_args()
    source_only() if args.source_only else render_only()
