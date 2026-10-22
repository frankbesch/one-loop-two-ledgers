#!/usr/bin/env python3
"""Deterministic, offline corpus authoring for quarterly compliance certificates."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess
import time
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
SPEC = ROOT/'case_spec_q.json'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
QUARTER_END = {1: '2025-03-31', 2: '2025-06-30', 3: '2025-09-30', 4: '2025-12-31'}
COVENANT_NAME = {'leverage': 'Total leverage', 'interest_coverage': 'Interest coverage'}
THRESHOLD_WORD = {'leverage': 'Maximum', 'interest_coverage': 'Minimum'}
HEADINGS = ['Quarterly Compliance Certificate', 'Schedule 1: Consolidated EBITDA (last four quarters)',
            'Addbacks', 'Schedule 2: Financial covenants']
CSS = '''@page { size:8.5in 11in; margin:0.7in 0.75in; }
* { box-sizing:border-box; } body { margin:0; color:#1d2327; font-family:Georgia,'Times New Roman',serif; font-size:11px; line-height:1.4; background:#fff; }
h1 { font-size:19px; font-weight:600; margin:0 0 10px; padding-bottom:6px; border-bottom:2px solid #2f3b42; }
h2 { font-size:13px; font-weight:600; margin:16px 0 6px; } h3 { font-size:12px; font-weight:600; margin:12px 0 4px; }
.header p { margin:2px 0; }
ol.statements { margin:12px 0 6px; padding-left:20px; } ol.statements li { margin:0 0 5px; }
table { width:100%; border-collapse:collapse; margin:4px 0 8px; }
th { text-align:left; font-weight:600; border-bottom:1px solid #2f3b42; padding:4px 5px; vertical-align:bottom; }
td { padding:4px 5px; border-bottom:1px solid #ccd3d6; vertical-align:top; }
tr, td, th { break-inside:avoid; } .num { text-align:right; white-space:nowrap; } .nowrap { white-space:nowrap; }
table.ebitda { width:60%; } table.ebitda tr.total td { font-weight:600; border-top:1px solid #2f3b42; }
.cure p, .adjusted { margin:4px 0; } .adjusted { font-weight:600; margin-top:8px; }
.certification { margin:8px 0; } .signature { margin-top:22px; break-inside:avoid; }
.signature .line { width:3in; border-bottom:1px solid #1d2327; height:26px; margin-bottom:4px; } .signature p { margin:2px 0; }
'''


def read_spec():
    return json.loads(SPEC.read_text())


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')


def money(value):
    if not isinstance(value, int):
        raise ValueError(f'money must be whole dollars: {value!r}')
    return ('-' if value < 0 else '')+f'${abs(value):,}'


def ratio(value):
    return f'{Decimal(str(value)).quantize(Decimal(".01"))}x'


def esc(value):
    return html.escape(str(value), quote=True)


def f(name, value, tag='span', cls=None):
    c = f' class="{cls}"' if cls else ''
    return f'<{tag}{c} data-f="{name}">{esc(value)}</{tag}>'


def cert_html(spec, c, agreement):
    q_end = QUARTER_END[c['quarter']]
    e = c['ebitda']
    out = ['<!DOCTYPE html><html><head><meta charset="utf-8" /><title>'+esc(c['cert_id'])+'</title><style>'+CSS+'</style></head><body>']
    out.append(f'<h1 data-heading="1">{esc(HEADINGS[0])}</h1><div class="header">')
    out.append(f'<p>To: {f("bank", spec["bank"]["name"])}, as Administrative Agent</p>')
    out.append(f'<p>Borrower: {f("borrower", agreement["borrower"])}</p>')
    out.append(f'<p>Credit Agreement dated: {f("agreement_date", agreement["agreement_date"])}</p>')
    out.append(f'<p>Fiscal quarter ended: {f("quarter_end", q_end)}</p>')
    out.append(f'<p>Date delivered: {f("delivery_date", c["delivery_date"])}</p></div>')
    if c['statement_4'] == 'no_default':
        s4 = '<span data-f="statement_4" data-v="no_default">To the knowledge of the undersigned, no Default has occurred and is continuing.</span>'
    elif c['statement_4'] == 'defaults_listed':
        s4 = '<span data-f="statement_4" data-v="defaults_listed">The following Default has occurred and is continuing: </span>'+f('defaults_text', c['defaults_text'])
    else:
        raise ValueError(f'{c["cert_id"]}: unknown statement_4 {c["statement_4"]!r}')
    out.append('<ol class="statements">')
    out.append(f'<li>The financial statements of the Borrower for the fiscal quarter ended {esc(q_end)} required by the reporting section of the Credit Agreement have been delivered to the Administrative Agent.</li>')
    out.append('<li>Those financial statements fairly present the financial condition and results of operations of the Borrower under GAAP, subject to normal year-end audit adjustments.</li>')
    out.append("<li>The undersigned has reviewed the Credit Agreement and has made, or caused to be made under the undersigned's supervision, a review of the transactions and condition of the Borrower during the quarter.</li>")
    out.append(f'<li>{s4}</li></ol>')

    out.append(f'<h2 data-heading="2">{esc(HEADINGS[1])}</h2><table class="ebitda"><tbody>')
    for label, key in [('Net income', 'net_income'), ('Interest expense', 'interest_expense'), ('Income taxes', 'income_taxes'),
                       ('Depreciation and amortization', 'd_and_a'), ('Unadjusted EBITDA', 'unadjusted')]:
        cls = ' class="total"' if key == 'unadjusted' else ''
        out.append(f'<tr{cls}><td>{label}</td>{f(key, money(e[key]), "td", "num")}</tr>')
    out.append('</tbody></table>')

    out.append(f'<h3 data-heading="3">{esc(HEADINGS[2])}</h3><table class="addbacks"><thead><tr><th style="width:6%">No.</th><th>Description</th>'
               '<th style="width:17%">Category</th><th style="width:13%" class="num">Amount</th><th style="width:13%">Action date</th></tr></thead><tbody>')
    for a in c['addbacks']:
        out.append(f'<tr data-addback="{a["addback_no"]}">{f("addback_no", a["addback_no"], "td")}{f("description", a["description"], "td")}'
                   f'{f("category_printed", a["category_printed"], "td")}{f("amount", money(a["amount"]), "td", "num")}{f("action_date", a["action_date"], "td", "nowrap")}</tr>')
    out.append('</tbody></table>')
    if c['cure'] is not None:
        out.append(f'<div class="cure"><p>Equity cure contribution: {f("cure_amount", money(c["cure"]["amount"]))}</p>'
                   f'<p>Date received: {f("cure_date", c["cure"]["date"])}</p><p>Applied to Consolidated EBITDA for the quarter.</p></div>')
    out.append(f'<p class="adjusted">Adjusted EBITDA {f("adjusted_ebitda_printed", money(c["adjusted_ebitda_printed"]))}</p>')
    cert = c['certification']
    if cert['present']:
        out.append(f'<p class="certification">Officer certification of cost savings: {f("certification", cert["text"])}</p>')

    out.append(f'<h2 data-heading="4">{esc(HEADINGS[3])}</h2><table class="covenants"><thead><tr><th>Covenant</th><th class="num">Input</th>'
               '<th class="num">Adjusted EBITDA</th><th class="num">Ratio</th><th>Threshold</th><th>Status</th></tr></thead><tbody>')
    if [k['covenant'] for k in c['covenants']] != ['leverage', 'interest_coverage']:
        raise ValueError(f'{c["cert_id"]}: covenant order')
    unit_ebitda = {u['covenant']: u['adjusted_ebitda'] for u in c['units'] if u['unit_type'] == 'covenant'}
    for k in c['covenants']:
        if k['status_printed'] not in ('pass', 'fail'):
            raise ValueError(f'{c["cert_id"]}: status {k["status_printed"]!r}')
        out.append(f'<tr data-covenant="{k["covenant"]}"><td>{COVENANT_NAME[k["covenant"]]}</td>{f("input", money(k["input"]), "td", "num")}'
                   f'{f("adjusted_ebitda", money(unit_ebitda[k["covenant"]]), "td", "num")}{f("ratio_printed", ratio(k["ratio_printed"]), "td", "num")}'
                   f'<td>{THRESHOLD_WORD[k["covenant"]]} {f("threshold_printed", ratio(k["threshold_printed"]))}</td>{f("status_printed", k["status_printed"].capitalize(), "td")}</tr>')
    out.append('</tbody></table>')
    out.append(f'<div class="signature"><div class="line"></div><p>Name: {f("signer_name", c["signer_name"])}</p>'
               f'<p>Title: {f("signer_title", c["signer_title"])}</p><p>Date: {f("signature_date", c["delivery_date"])}</p></div>')
    return ''.join(out)+'</body></html>\n'


def source_only():
    s = read_spec()
    agreements = {a['borrower_id']: a for a in s['agreements']}
    (ROOT/'sources').mkdir(exist_ok=True)
    (ROOT/'clean').mkdir(exist_ok=True)
    truth = {'units': []}
    manifest = {'spec_sha256': hashlib.sha256(SPEC.read_bytes()).hexdigest(), 'certificates': []}
    for c in s['certificates']:
        name = f'sources/{c["cert_id"]}.html'
        content = cert_html(s, c, agreements[c['borrower_id']])
        (ROOT/name).write_text(content)
        for u in c['units']:
            if (u['cert_id'], u['quarter'], u['borrower_id']) != (c['cert_id'], c['quarter'], c['borrower_id']):
                raise ValueError(f'{c["cert_id"]}: unit {u["unit_id"]} identity mismatch')
            truth['units'].append(dict(u))
        manifest['certificates'].append(dict(cert_id=c['cert_id'], quarter=c['quarter'], borrower_id=c['borrower_id'], split=c['split'],
                                             source=name, pdf=f'clean/{c["cert_id"]}.pdf', source_sha256=hashlib.sha256(content.encode()).hexdigest()))
    dump(ROOT/'truth_q.json', truth)
    dump(ROOT/'reference/agreements.json', s['agreements'])
    dump(ROOT/'reference/categories.json', s['categories'])
    history = [dict(borrower_id=p['borrower_id'], quarter_label=p['quarter_label'], amount=p['amount'])
               for p in s['prior_cures'] if p['quarter_label'] < '2025']
    for k in range(1, 5):
        printed = [dict(borrower_id=c['borrower_id'], quarter_label=f'2025-Q{c["quarter"]}', amount=c['cure']['amount'])
                   for c in sorted(s['certificates'], key=lambda c: (c['quarter'], c['borrower_id'])) if c['quarter'] < k and c['cure'] is not None]
        dump(ROOT/'reference'/f'prior_cures_q{k}.json', history+printed)
    dump(ROOT/'manifest_q.json', manifest)
    print(f'SOURCE ONLY: {len(s["certificates"])} certificates, {len(truth["units"])} units. Chrome was not started.')


def render_only():
    manifest = json.loads((ROOT/'manifest_q.json').read_text())
    (ROOT/'clean').mkdir(exist_ok=True)
    profile = ROOT/'chrome-profile-q'
    for d in manifest['certificates']:
        source = ROOT/d['source']
        if hashlib.sha256(source.read_bytes()).hexdigest() != d['source_sha256']:
            raise RuntimeError(f'Source changed: {source}')
        output = ROOT/d['pdf']
        if output.exists():
            output.unlink()
        args = [CHROME, '--headless', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer', '--disable-background-networking',
                '--disable-component-update', '--no-first-run', '--no-default-browser-check', f'--user-data-dir={profile}',
                f'--print-to-pdf={output}', source.as_uri()]
        done = lambda: output.exists() and output.read_bytes().rstrip().endswith(b'%%EOF')
        with (ROOT/'chrome_q.log').open('a') as log:
            proc = subprocess.Popen(args, stdout=log, stderr=log)
            try:
                deadline = time.monotonic()+90
                while not done():
                    if proc.poll() is not None:
                        time.sleep(.5)
                        if done():
                            break
                        raise RuntimeError(f'Chrome exited before completing {output.name}; see chrome_q.log')
                    if time.monotonic() > deadline:
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source-only', action='store_true')
    mode.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    source_only() if args.source_only else render_only()
