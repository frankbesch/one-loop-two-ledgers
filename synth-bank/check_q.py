#!/usr/bin/env python3
"""Offline build gate. Recompute labels without using spec quota_check or unit labels."""
import calendar
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import build_q as build

ROOT=Path(__file__).resolve().parent
D=lambda x: Decimal(str(x))
ERRORS='ratio_arithmetic hidden_breach cap_exceeded window_expired category_not_permitted certification_missing signer_not_officer late_delivery cure_invalid duplicate_addback'.split()
LABELS={'error_class','breach','disposition','owner'}
COMMON={'cert_id','quarter','borrower_id','unit_id','unit_type'}|LABELS
FIELDS={
 'addback':set('addback_no description amount action_date category_printed category_true realized certified'.split()),
 'covenant':set('covenant adjusted_ebitda ratio_printed threshold_printed status_printed ratio_agreement'.split()),
 'delivery':{'delivery_date','due_date'},'signer':{'signer_name','signer_title'},'cure':{'cure_amount','cure_date'}}
ABBREVS={'CFO':'Chief Financial Officer','CEO':'Chief Executive Officer','COO':'Chief Operating Officer'}
failures={f'G{i}':[] for i in range(1,8)}
counts={}


def require(g, condition, message):
    if not condition:
        failures[g].append(message)


def rounded(value):
    return D(value).quantize(D('.01'),rounding=ROUND_HALF_UP)


def cutoff(qend, months):
    n=qend.year*12+qend.month-1-months
    y,m=divmod(n,12)
    m+=1
    return date(y,m,min(qend.day,calendar.monthrange(y,m)[1]))


def normalize(text):
    # A retained hyphen inside a word must survive PDF line wrapping.
    text=re.sub(r'(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)','-',text)
    return ' '.join(text.split())


class SourceText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
        self.skip=False
    def handle_starttag(self, tag, attrs):
        if tag in ('style','script','title'):
            self.skip=True
    def handle_endtag(self,tag):
        if tag in ('style','script','title'):
            self.skip=False
    def handle_data(self,data):
        if not self.skip:
            self.parts.append(data)


def semantics(description):
    """Explicit lexical rules for this fixed synthetic corpus; unknown prose fails closed."""
    t=description.lower()
    if re.search(r'lower|reduc|savings|cut .*(?:cost|charges)|trim .*cost|decrease|decline|eliminate storage rent|spending .*expected to fall',t):
        category='cost_savings'
    elif re.search(r'\bshares?\b|stock[- ](?:based|grants|awards|options|bonuses|vested)|restricted stock|equity|option|noncash|non-cash',t):
        category='non_cash_compensation'
    elif re.search(r'severance|termination|separation|dismissal|redundancy|exit (?:benefits|packages|compensation|payments)|relocation payments|departing|employees losing their jobs',t):
        category='restructuring_charges'
    elif re.search(r'annual .*contracts|regular monthly|ordinary property insurance|normal .*crew|routine .*service agreement|customary monthly|regular janitorial|usual .*staffing-agency',t):
        category='ordinary_operating'
    elif re.search(r'destroy|ruin|spoil|damage|crush|written off|breaking|burned|contaminated|flooded|buried|shattered|smashed|swallowed|drenched|swept away',t):
        category='non_recurring_losses'
    elif re.search(r'(acquisition|financing|disposal).*(fee|expense)|(fee|expense).*(acquisition|financing|disposal)',t):
        category='transaction_costs'
    else:
        raise ValueError('Cannot classify description: '+description)
    projected=bool(re.search(r'expected|expects|targets|planned|plans|anticipates|budgets|should|projects|forecast|estimates|intends|projected|looks for|still planned|intended|continues to target',t))
    return category, 'projected' if category=='cost_savings' and projected else 'realized'


def cert_numbers(c):
    paragraph=c['certification']['text'] if c['certification']['present'] else ''
    match=re.search(r'Addback Nos\. ([\d, and]+)',paragraph or '')
    return [int(n) for n in re.findall(r'\d+',match.group(1))] if match else []


def prior_quarter(q):
    return f'2025-Q{q-1}' if q>1 else '2024-Q4'


def cure_tests(c,a,history):
    rows=[r for r in history if r['borrower_id']==c['borrower_id']]
    return len(rows)+1<=a['cure_max'], not a['cure_no_consecutive'] or not any(r['quarter_label']==prior_quarter(c['quarter']) for r in rows)


def labels(error,breach,kind):
    held=error!='none' or breach
    owner='none'
    if held:
        if breach or error in ('cure_invalid','late_delivery'):
            owner='required_lenders'
        elif kind=='addback':
            owner='credit_officer'
        else:
            owner='analyst'
    return {'error_class':error,'breach':'yes' if breach else 'no','disposition':'hold' if held else 'post','owner':owner}


def recompute(c,a,history):
    qend=date.fromisoformat(build.ENDS[c['quarter']])
    unadjusted=sum(c['ebitda'][k] for k in ['net_income','interest_expense','income_taxes','d_and_a'])
    base={'cert_id':c['cert_id'],'quarter':c['quarter'],'borrower_id':c['borrower_id']}
    expected=[]
    def add(kind,uid,fields,error='none',breach=False):
        expected.append(dict(base,unit_type=kind,unit_id=uid,**fields,**labels(error,breach,kind)))
    numbers=cert_numbers(c)
    require('G3',numbers==c['certification']['addback_nos_named'],c['cert_id']+': certification text versus named numbers')
    permitted=0
    bucket=D(0)
    cap_hit=False
    seen=set()
    for row in c['addbacks']:
        category,realized=semantics(row['description'])
        certified=('yes' if row['addback_no'] in numbers else 'no') if category=='cost_savings' else 'n_a'
        require('G3',category==row['category_true'] and realized==row['realized'],c['cert_id']+f': A{row["addback_no"]} description semantics')
        key=(row['amount'],row['action_date'])
        error='none'
        if key in seen:
            error='duplicate_addback'
        elif category not in a['permitted_categories']:
            error='category_not_permitted'
        elif category=='cost_savings':
            if certified!='yes':
                error='certification_missing'
            elif realized=='projected' and date.fromisoformat(row['action_date'])<cutoff(qend,a['cost_savings_window_months']):
                error='window_expired'
            elif cap_hit or bucket+D(row['amount'])>D(a['cost_savings_cap_pct'])*D(unadjusted):
                cap_hit=True
                error='cap_exceeded'
            else:
                bucket+=D(row['amount'])
        seen.add(key)
        if error=='none':
            permitted+=row['amount']
        fields={k:row[k] for k in FIELDS['addback']-{'certified'}}
        fields.update(category_true=category,realized=realized,certified=certified)
        add('addback',f'A{row["addback_no"]}',fields,error)
    valid_cure=all(cure_tests(c,a,history)) if c['cure'] else False
    agreement_ebitda=unadjusted+permitted+(c['cure']['amount'] if valid_cure else 0)
    for row in c['covenants']:
        lev=row['covenant']=='leverage'
        agreement_ratio=rounded(D(row['input'])/D(agreement_ebitda) if lev else D(agreement_ebitda)/D(row['input']))
        printed_calc=rounded(D(row['input'])/D(c['adjusted_ebitda_printed']) if lev else D(c['adjusted_ebitda_printed'])/D(row['input']))
        breach=agreement_ratio>D(a['max_leverage']) if lev else agreement_ratio<D(a['min_interest_coverage'])
        error='hidden_breach' if row['status_printed']=='pass' and breach else ('ratio_arithmetic' if abs(D(row['ratio_printed'])-printed_calc)>D('.01') else 'none')
        fields={k:row[k] for k in ('covenant','ratio_printed','threshold_printed','status_printed')}
        fields.update(adjusted_ebitda=c['adjusted_ebitda_printed'],ratio_agreement=float(agreement_ratio))
        fields['total_debt' if lev else 'cash_interest']=row['input']
        add('covenant','LEV' if lev else 'ICR',fields,error,breach)
    due=qend+timedelta(days=a['delivery_days_q4'] if c['quarter']==4 else a['delivery_days'])
    add('delivery','DELIVERY',{'delivery_date':c['delivery_date'],'due_date':due.isoformat()},'late_delivery' if date.fromisoformat(c['delivery_date'])>due else 'none')
    add('signer','SIGNER',{k:c[k] for k in ('signer_name','signer_title')},'none' if ABBREVS.get(c['signer_title'],c['signer_title']) in a['responsible_officer_titles'] else 'signer_not_officer')
    if c['cure']:
        add('cure','CURE',{'cure_amount':c['cure']['amount'],'cure_date':c['cure']['date']},'none' if valid_cure else 'cure_invalid')
    return expected, agreement_ebitda


def check_quotas(s,truth,agreements,histories):
    for q in range(1,5):
        cs=[c for c in s['certificates'] if c['quarter']==q]
        us=[u for u in truth if u['quarter']==q]
        totals=Counter(u['error_class'] for u in us)
        stats={name:totals[name] for name in ERRORS}
        for name in ERRORS:
            require('G1',totals[name]==2,f'Q{q}: {name} = {totals[name]}, expected 2')
        for b in agreements:
            require('G1',sum(u['error_class']!='none' for u in us if u['borrower_id']==b)<=3,f'Q{q} {b}: more than 3 errors')
        benign=Counter()
        mechanisms=Counter()
        for c in cs:
            a=agreements[c['borrower_id']]
            rows=[u for u in us if u['cert_id']==c['cert_id']]
            units={u['unit_id']:u for u in rows}
            require('G1',2<=len(c['addbacks'])<=6,c['cert_id']+': addback volume')
            if all(u['error_class']=='none' for u in rows) and any(u['breach']=='yes' and u.get('status_printed')=='fail' for u in rows) and c['statement_4']=='defaults_listed' and c['defaults_text']:
                benign['honestly_reported_breach']+=1
            if c['cure']:
                benign['cures_claimed']+=1
                if units['CURE']['error_class']=='none':
                    benign['valid_equity_cure']+=1
                else:
                    count_ok,timing_ok=cure_tests(c,a,histories[q])
                    mechanisms['cure_count']+=not count_ok
                    mechanisms['cure_consecutive']+=not timing_ok
            if c['certification']['present'] and any(r['category_true']=='cost_savings' for r in c['addbacks']):
                benign['certified_cost_savings_certificates']+=1
            if c['signer_title'] in ABBREVS and units['SIGNER']['error_class']=='none':
                benign['abbreviated_officer_title']+=1
            qend=date.fromisoformat(build.ENDS[q])
            for i,row in enumerate(c['addbacks']):
                permitted=units[f'A{row["addback_no"]}']['error_class']=='none'
                if permitted and row['category_true']=='cost_savings' and row['realized']=='realized' and date.fromisoformat(row['action_date'])<cutoff(qend,a['cost_savings_window_months']):
                    benign['realized_cost_savings_older_than_window']+=1
                if permitted and re.search(r'approved|authorized|one-time',row['description'],re.I):
                    benign['permitted_approval_or_one_time']+=1
                for earlier in c['addbacks'][:i]:
                    if permitted and units[f'A{earlier["addback_no"]}']['error_class']=='none' and earlier['amount']==row['amount'] and earlier['action_date']!=row['action_date']:
                        benign['same_amount_different_dates']+=1
            for u in rows:
                if u['error_class']=='hidden_breach':
                    lev=u['covenant']=='leverage'
                    threshold=D(a['max_leverage'] if lev else a['min_interest_coverage'])
                    looser=D(u['threshold_printed'])>threshold if lev else D(u['threshold_printed'])<threshold
                    invalid_addbacks=any(r['unit_type']=='addback' and r['error_class']!='none' for r in rows)
                    mechanisms['hidden_threshold']+=looser
                    mechanisms['hidden_addback']+=invalid_addbacks and not looser
        for name in ['honestly_reported_breach','valid_equity_cure','realized_cost_savings_older_than_window','same_amount_different_dates','permitted_approval_or_one_time','abbreviated_officer_title']:
            require('G1',benign[name]==1,f'Q{q}: {name} = {benign[name]}, expected 1')
        for name in ['cure_count','cure_consecutive','hidden_threshold','hidden_addback']:
            require('G1',mechanisms[name]==1,f'Q{q}: {name} = {mechanisms[name]}, expected 1')
        require('G1',3<=benign['cures_claimed']<=4,f'Q{q}: cure volume')
        require('G1',benign['certified_cost_savings_certificates']>=3,f'Q{q}: certified cost savings volume')
        mean=sum(len(c['addbacks']) for c in cs)/len(cs)
        require('G1',3.5<=mean<=4.5,f'Q{q}: average addbacks {mean}, outside operational interpretation of about 4')
        stats.update(benign)
        stats.update(mechanisms)
        stats['average_addbacks']=mean
        counts[q]=stats
    for name in ERRORS:
        require('G1',sum(u['error_class']==name for u in truth)==8,f'All quarters: {name} total')
        scored={c['cert_id'] for c in s['certificates'] if c['split']=='scored'}
        require('G1',sum(u['error_class']==name for u in truth if u['cert_id'] in scored)==4,f'Scored quarters: {name} total')
    require('G1',len(agreements)==12,'Reference: 12 borrowers required')
    require('G1',sum('transaction_costs' not in a['permitted_categories'] for a in agreements.values())>=3,'Reference: transaction exclusions')
    require('G1',2<=len({r['borrower_id'] for r in s['prior_cures']})<=3,'Reference: historical cure borrowers')
    expected_categories=set('restructuring_charges transaction_costs non_cash_compensation cost_savings non_recurring_losses ordinary_operating'.split())
    require('G1',set(s['categories'])==expected_categories,'Reference: categories')
    for category,meaning in s['categories'].items():
        require('G1',isinstance(meaning,str) and meaning.endswith('.') and len(re.findall(r'[.!?](?:\s|$)',meaning))==1,f'Reference: {category} one-sentence meaning')
    for b,a in agreements.items():
        ok=(3<=a['max_leverage']<=5 and 2<=a['min_interest_coverage']<=3.5 and set(a['permitted_categories'])<=expected_categories and 'ordinary_operating' not in a['permitted_categories'] and a['cost_savings_cap_pct'] in (.15,.2) and a['cost_savings_window_months']==18 and a['cure_max']==4 and a['cure_no_consecutive'] is True and 3<=len(a['responsible_officer_titles'])<=5 and all(' ' in t or t in ('Treasurer','Controller') for t in a['responsible_officer_titles']) and a['delivery_days']==45 and a['delivery_days_q4']==90 and 3<=len(a['commitments'])<=5 and all(l['amount']>0 for l in a['commitments']))
        require('G1',ok,b+': agreement reference constraints')


def check_dates(value,location='spec'):
    if isinstance(value,dict):
        for k,v in value.items():
            if isinstance(v,str) and (k.endswith('_date') or k=='date'):
                try:
                    require('G7',date.fromisoformat(v).isoformat()==v,location+'.'+k+': noncanonical date')
                except ValueError:
                    require('G7',False,location+'.'+k+': invalid date '+v)
            elif k=='quarter_label':
                require('G7',bool(re.fullmatch(r'\d{4}-Q[1-4]',v)),location+': invalid quarter label')
            else:
                check_dates(v,location+'.'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value):
            check_dates(v,location+f'[{i}]')


def main():
    s=build.read_spec()
    truth=json.loads((ROOT/'truth_q.json').read_text())['units']
    manifest=json.loads((ROOT/'manifest_q.json').read_text())
    agreements={a['borrower_id']:a for a in s['agreements']}
    histories={k:json.loads((ROOT/f'reference/prior_cures_q{k}.json').read_text()) for k in range(1,5)}
    for name in ['agreements','categories']:
        require('G2',json.loads((ROOT/f'reference/{name}.json').read_text())==s[name],f'Reference {name} differs from spec')
    for k in histories:
        require('G2',histories[k]==build.history(s,k),f'Q{k} cure history differs from printed cures')
        require('G2',all(set(r)=={'borrower_id','quarter_label','amount'} for r in histories[k]),f'Q{k}: history schema')
    def no_labels(value):
        if isinstance(value,dict):
            return not (set(value)&LABELS) and all(no_labels(v) for v in value.values())
        return all(no_labels(v) for v in value) if isinstance(value,list) else True
    for file in (ROOT/'reference').glob('*.json'):
        require('G2',no_labels(json.loads(file.read_text())),str(file.name)+': reference label leakage')
    expected_truth=[dict(u,cert_id=c['cert_id'],quarter=c['quarter'],borrower_id=c['borrower_id']) for c in s['certificates'] for u in c['units']]
    require('G2',truth==expected_truth,'Truth does not preserve every spec unit and field')
    keys=[(u['cert_id'],u['unit_id']) for u in truth]
    require('G2',len(keys)==len(set(keys)),'Duplicate unit IDs')
    for u in truth:
        required=COMMON|FIELDS.get(u['unit_type'],set())
        if u['unit_type']=='covenant':
            required|={'total_debt' if u['covenant']=='leverage' else 'cash_interest'}
        require('G2',set(u)==required,f'{u["cert_id"]}/{u["unit_id"]}: field names differ: {set(u)^required}')
        require('G2',u['error_class'] in ['none']+ERRORS and u['breach'] in ('yes','no') and u['disposition'] in ('hold','post') and u['owner'] in ('required_lenders','credit_officer','analyst','none'),f'{u["cert_id"]}/{u["unit_id"]}: label domain')
    check_quotas(s,truth,agreements,histories)
    require('G2',manifest['spec_sha256']==hashlib.sha256((ROOT/'case_spec_q.json').read_bytes()).hexdigest(),'Manifest spec hash')
    entries={e['cert_id']:e for e in manifest['certificates']}
    cert_ids={c['cert_id'] for c in s['certificates']}
    require('G2',set(entries)==cert_ids and len(entries)==len(manifest['certificates']),'Manifest certificate inventory')
    require('G2',{p.stem for p in (ROOT/'sources').glob('*.html')}==cert_ids,'Source certificate inventory')
    pdfs=list((ROOT/'clean').glob('*.pdf'))
    render_skipped=not any((ROOT/'clean').iterdir())
    if not render_skipped:
        require('G5',{p.stem for p in pdfs}==cert_ids,'PDF certificate inventory incomplete or extra')
        require('G5',bool(shutil.which('pdftotext')),'pdftotext unavailable')
        require('G6',bool(shutil.which('pdfinfo')),'pdfinfo unavailable for portrait/page-count verification')
    check_dates(s)
    check_dates(truth,'truth')
    for k,h in histories.items():
        check_dates(h,f'prior_cures_q{k}')
    for c in s['certificates']:
        cid=c['cert_id']
        rows=[u for u in truth if u['cert_id']==cid]
        a=agreements[c['borrower_id']]
        try:
            expected,agreement_ebitda=recompute(c,a,histories[c['quarter']])
            actual={u['unit_id']:u for u in rows}
            require('G3',set(actual)=={u['unit_id'] for u in expected},cid+': unit inventory')
            for u in expected:
                got=actual.get(u['unit_id'],{})
                differences={k:{'expected':v,'actual':got.get(k)} for k,v in u.items() if got.get(k)!=v}
                require('G3',not differences,f'{cid}/{u["unit_id"]}: {differences}')
        except (ValueError,KeyError,ZeroDivisionError) as exc:
            require('G3',False,cid+': '+str(exc))
        e=c['ebitda']
        require('G4',e['unadjusted']==sum(e[k] for k in ['net_income','interest_expense','income_taxes','d_and_a']),cid+': unadjusted EBITDA')
        require('G4',c['adjusted_ebitda_printed']==e['unadjusted']+sum(r['amount'] for r in c['addbacks'])+(c['cure']['amount'] if c['cure'] else 0),cid+': adjusted EBITDA')
        for r in c['covenants']:
            lev=r['covenant']=='leverage'
            u=next(u for u in rows if u['unit_id']==('LEV' if lev else 'ICR'))
            calc=rounded(D(r['input'])/D(c['adjusted_ebitda_printed']) if lev else D(c['adjusted_ebitda_printed'])/D(r['input']))
            require('G4',u['error_class']=='ratio_arithmetic' or D(r['ratio_printed'])==calc,cid+': '+r['covenant']+' printed ratio arithmetic')
        try:
            require('G7',date.fromisoformat(c['delivery_date'])>date.fromisoformat(build.ENDS[c['quarter']]),cid+': delivery must follow quarter end')
        except (KeyError,ValueError) as exc:
            require('G7',False,cid+': '+str(exc))
        entry=entries[cid]
        content=(ROOT/entry['source']).read_text()
        require('G2',hashlib.sha256(content.encode()).hexdigest()==entry['source_sha256'],cid+': source hash')
        require('G2',content==build.certificate_html(s,c),cid+': source differs from fixed template/spec')
        parser=SourceText()
        parser.feed(content)
        source_text=normalize(' '.join(parser.parts))
        expected_texts=[r['description'] for r in c['addbacks']]+build.statements(c)+[c['signer_title'],f'Date: {c["delivery_date"]}']
        if c['certification']['present']:
            expected_texts.append('Officer certification of cost savings: '+c['certification']['text'])
        for t in expected_texts:
            require('G2',normalize(t) in source_text,cid+': source missing text '+t)
        positions=[source_text.find(h) for h in build.HEADINGS]
        require('G2',all(p>=0 for p in positions) and positions==sorted(positions),cid+': source section order')
        if render_skipped:
            continue
        path=ROOT/entry['pdf']
        if not path.exists():
            require('G6',False,cid+': PDF missing')
            continue
        require('G5',path.read_bytes().rstrip().endswith(b'%%EOF'),cid+': PDF incomplete')
        if shutil.which('pdftotext'):
            run=subprocess.run(['pdftotext','-raw',str(path),'-'],capture_output=True,text=True)
            require('G5',run.returncode==0,cid+': pdftotext failed '+run.stderr)
            text=normalize(run.stdout)
            for t in expected_texts:
                require('G5',normalize(t) in text,cid+': PDF missing text '+t)
            # Full source comparison also protects every number, date, row and fixed label.
            require('G5',source_text==normalize(re.sub(r'(?<!\S)[1-4]\.(?=\s)', '', text)),cid+': PDF text differs from source (excluding list markers)')
            headings=re.findall(r'Quarterly Compliance Certificate|Schedule 1: Consolidated EBITDA \(last four quarters\)|Addbacks|Adjusted EBITDA|Schedule 2: Financial covenants',text)
            # Adjusted EBITDA also appears once as the mandatory Schedule 2 column header.
            require('G6',headings==build.HEADINGS+['Adjusted EBITDA'],cid+': PDF section sequence '+str(headings))
        if shutil.which('pdfinfo'):
            run=subprocess.run(['pdfinfo',str(path)],capture_output=True,text=True)
            pages=re.search(r'^Pages:\s+(\d+)',run.stdout,re.M)
            size=re.search(r'^Page size:\s+([\d.]+) x ([\d.]+)',run.stdout,re.M)
            require('G6',run.returncode==0 and pages is not None and 1<=int(pages[1])<=2,cid+': PDF must have 1–2 pages')
            require('G6',size is not None and float(size[1])<float(size[2]),cid+': PDF must be portrait')
    lines=['# Source report','',f'Built {len(s["certificates"])} HTML certificates and {len(truth)} truth units from the fixed spec.','', 'Spec deviations: none. No spec values or labels were altered.','', '## Gate results','']
    for g,issues in failures.items():
        status='SKIP — clean/ is empty; PDF rendering UNVERIFIED.' if render_skipped and g in ('G5','G6') else ('FAIL' if issues else 'PASS')
        print(f'{g}: {status}')
        lines.append(f'- {g}: {status}')
        for issue in issues:
            print('  '+issue)
            lines.append('  - '+issue)
    lines+=['','## Recounted quarterly quotas','', '```json',json.dumps(counts,indent=2),'```','','## Interpretations and unverified items','', '- “About 4” means an average from 3.5 to 4.5; the actual average is reported above.', '- Required Lenders means commitments exceeding 50%. The spec does not identify a lender coalition or voting definition; coalition compliance is UNVERIFIED.', '- Description classification uses explicit rules for this fixed corpus and fails on unknown descriptions.']
    if render_skipped:
        lines+=['- PDF text fidelity, pagination, portrait dimensions, visual layout, and rendered section order are UNVERIFIED.', '- Chrome was not started. The brain session must run `python3 build_q.py --render-only`, then `python3 check_q.py`.']
    else:
        lines+=['- Visual layout inspection remains UNVERIFIED; PDF text, page count, and portrait dimensions are checked mechanically.']
    (ROOT/'SOURCE-REPORT.md').write_text('\n'.join(lines)+'\n')
    return 1 if any(failures.values()) else 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'BUILD GATE ERROR: {type(exc).__name__}: {exc}',file=sys.stderr)
        sys.exit(1)
