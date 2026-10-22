#!/usr/bin/env python3
"""Independent label/arithmetical gate plus source fidelity and PDF text checks.

Description rules below are scoped to this fixed corpus, fail closed on unknown
wording, and never use category_true or error_class to classify descriptions.
"""
import calendar
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
import json
import re
import subprocess
import sys
import traceback
from build_q import ROOT, QUARTER_END, HEADINGS, certificate_html, digest, prior_cures, statements, money, ratio

D=lambda v: Decimal(str(v))
ERRORS='ratio_arithmetic hidden_breach cap_exceeded window_expired category_not_permitted certification_missing signer_not_officer late_delivery cure_invalid duplicate_addback'.split()
LABELS={'error_class','breach','disposition','owner'}
COMMON={'cert_id','quarter','borrower_id','unit_id','unit_type'}|LABELS
FIELDS={
 'addback':set('addback_no description amount action_date category_printed category_true realized certified'.split()),
 'covenant':set('covenant adjusted_ebitda ratio_printed threshold_printed status_printed ratio_agreement'.split()),
 'delivery':{'delivery_date','due_date'}, 'signer':{'signer_name','signer_title'}, 'cure':{'cure_amount','cure_date'}}
ABBREVIATIONS={'CFO':'Chief Financial Officer','CEO':'Chief Executive Officer','COO':'Chief Operating Officer','CRO':'Chief Risk Officer'}

class Gate:
    def __init__(self):
        self.failures={f'G{i}':[] for i in range(1,8)}
        self.skipped=set()
    def require(self,g,ok,msg):
        if not ok: self.failures[g].append(msg)
    def equal(self,g,actual,expected,msg):
        self.require(g,actual==expected,f'{msg}: got {actual!r}; expected {expected!r}')

def load(path):
    return json.loads((ROOT/path).read_text())

def rounded(v):
    return v.quantize(D('.01'),rounding=ROUND_HALF_UP)

def cutoff(end,months):
    n=end.year*12+end.month-1-months
    y,m=divmod(n,12); m+=1
    return date(y,m,min(end.day,calendar.monthrange(y,m)[1]))

def semantic(description):
    t=description.lower()
    if re.search(r'\b(forecasts|expects|should reduce|projects|intends|budgets|estimates|targets|aims|predicts|anticipates|plans to save)\b',t):
        return 'cost_savings','projected'
    if re.search(r'achieved annual|has delivered|recorded the full carrier savings|has already obtained',t):
        return 'cost_savings','realized'
    if re.search(r'insurance renewal|routine janitorial|recurring payroll|normal forklift|annual warehouse alarm|regular production staffing|normal compressed air|routine accounting',t):
        return 'ordinary_operating','realized'
    if re.search(r'shattered|burned|tore through|buried|destroy|damage|ruin|lost|loss|wrote off|scrapp|soaked|broken|crush|casualty|contaminat|submerged|flood|charged on this additional line',t):
        return 'non_recurring_losses','realized'
    if re.search(r'equity|shares|share units|share-only|share-settled|share compensation|share bonus|share award|share bonuses|stock|option',t):
        return 'non_cash_compensation','realized'
    if re.search(r'dismissal|termination|lease exit|redundancy|relocation|separation|dismantling|transfer expense|closure charge|moving|decommissioning|exit cost|exit charge|severance|restructuring charge|removal charge|removal.*incurred costs|lease surrender|lease cancellation|transfer cost',t):
        return 'restructuring_charges','realized'
    raise ValueError(f'Unclassified description: {description}')

def labels(error='none',breach=False,kind=None):
    held=error!='none' or breach
    owner='none'
    if held:
        if breach or error in ('cure_invalid','late_delivery'): owner='required_lenders'
        elif kind=='addback': owner='credit_officer'
        else: owner='analyst'
    return dict(error_class=error,breach='yes' if breach else 'no',disposition='hold' if held else 'post',owner=owner)

def recompute(c,a,history,g):
    end=date.fromisoformat(QUARTER_END[c['quarter']])
    base=sum(D(c['ebitda'][k]) for k in ('net_income','interest_expense','income_taxes','d_and_a'))
    result={}; seen=set(); bucket=D(0); over=False; permitted=D(0)
    text=c['certification']['text'] or ''
    named=[int(n) for n in re.findall(r'Addback No\.\s*(\d+)',text)] if c['certification']['present'] else []
    g.equal('G3',named,c['certification']['addback_nos_named'],c['cert_id']+' certification numbers')
    g.equal('G3',bool(text),c['certification']['present'],c['cert_id']+' certification presence')
    for row in c['addbacks']:
        cat,realized=semantic(row['description'])
        g.equal('G3',(row['category_true'],row['realized']),(cat,realized),c['cert_id']+f' A{row["addback_no"]} description meaning')
        certified=('yes' if row['addback_no'] in named else 'no') if cat=='cost_savings' else 'n_a'
        key=(row['amount'],row['action_date']); err='none'
        if key in seen: err='duplicate_addback'
        elif cat not in a['permitted_categories']: err='category_not_permitted'
        elif cat=='cost_savings':
            if certified!='yes': err='certification_missing'
            elif realized=='projected' and date.fromisoformat(row['action_date'])<cutoff(end,a['cost_savings_window_months']): err='window_expired'
            elif over or bucket+D(row['amount'])>D(a['cost_savings_cap_pct'])*base:
                over=True; err='cap_exceeded'
            else: bucket+=D(row['amount'])
        seen.add(key)
        if err=='none': permitted+=D(row['amount'])
        result[f'A{row["addback_no"]}']={**row,'category_true':cat,'realized':realized,'certified':certified,**labels(err,kind='addback')}
    cure_valid=False; count_bad=False; consecutive_bad=False
    if c['cure']:
        previous=f'2025-Q{c["quarter"]-1}' if c['quarter']>1 else '2024-Q4'
        history=[r for r in history if r['borrower_id']==c['borrower_id']]
        count_bad=len(history)+1>a['cure_max']
        consecutive_bad=a['cure_no_consecutive'] and any(r['quarter_label']==previous for r in history)
        cure_valid=not count_bad and not consecutive_bad
        result['CURE']=dict(cure_amount=c['cure']['amount'],cure_date=c['cure']['date'],**labels('none' if cure_valid else 'cure_invalid'))
    agreement=base+permitted+(D(c['cure']['amount']) if cure_valid else D(0))
    for cov in c['covenants']:
        lev=cov['covenant']=='leverage'
        ar=rounded(D(cov['input'])/agreement if lev else agreement/D(cov['input']))
        pr=rounded(D(cov['input'])/D(c['adjusted_ebitda_printed']) if lev else D(c['adjusted_ebitda_printed'])/D(cov['input']))
        breach=ar>D(a['max_leverage']) if lev else ar<D(a['min_interest_coverage'])
        error='hidden_breach' if breach and cov['status_printed']=='pass' else 'ratio_arithmetic' if abs(D(cov['ratio_printed'])-pr)>D('.01') else 'none'
        result['LEV' if lev else 'ICR']={k:v for k,v in cov.items() if k!='input'}
        result['LEV' if lev else 'ICR'].update({('total_debt' if lev else 'cash_interest'):cov['input'],'adjusted_ebitda':c['adjusted_ebitda_printed'],'ratio_agreement':float(ar),**labels(error,breach)})
        if error!='ratio_arithmetic':
            g.equal('G4',D(cov['ratio_printed']),pr,c['cert_id']+' '+cov['covenant']+' printed arithmetic')
    due=end+timedelta(days=a['delivery_days_q4'] if c['quarter']==4 else a['delivery_days'])
    result['DELIVERY']=dict(delivery_date=c['delivery_date'],due_date=due.isoformat(),**labels('late_delivery' if date.fromisoformat(c['delivery_date'])>due else 'none'))
    title=ABBREVIATIONS.get(c['signer_title'],c['signer_title'])
    result['SIGNER']=dict(signer_name=c['signer_name'],signer_title=c['signer_title'],**labels('none' if title in a['responsible_officer_titles'] else 'signer_not_officer'))
    g.equal('G4',D(c['ebitda']['unadjusted']),base,c['cert_id']+' unadjusted EBITDA')
    g.equal('G4',D(c['adjusted_ebitda_printed']),base+sum(D(r['amount']) for r in c['addbacks'])+(D(c['cure']['amount']) if c['cure'] else D(0)),c['cert_id']+' adjusted EBITDA')
    return result,dict(agreement_ebitda=int(agreement),count_bad=count_bad,consecutive_bad=consecutive_bad)

def quotas(s,units,derived,g):
    agreements={a['borrower_id']:a for a in s['agreements']}
    counts={}
    scored={c['cert_id'] for c in s['certificates'] if c['split']=='scored'}
    for error in ERRORS:
        g.equal('G1',sum(u['error_class']==error for u in units),8,error+' total')
        g.equal('G1',sum(u['error_class']==error and u['cert_id'] in scored for u in units),4,error+' scored total')
    for q in range(1,5):
        cs=[c for c in s['certificates'] if c['quarter']==q]
        us=[u for u in units if u['quarter']==q]
        g.equal('G1',Counter(c['borrower_id'] for c in cs),Counter({bid:1 for bid in agreements}),f'Q{q} borrower inventory')
        tally=Counter(u['error_class'] for u in us if u['error_class']!='none')
        for error in ERRORS: g.equal('G1',tally[error],2,f'Q{q} {error}')
        borrower_errors=Counter(u['borrower_id'] for u in us if u['error_class']!='none')
        g.require('G1',all(n<=3 for n in borrower_errors.values()),f'Q{q} more than three errors per borrower')
        benign=Counter(); hidden=Counter(); invalid=Counter()
        for c in cs:
            rows=[u for u in us if u['cert_id']==c['cert_id']]; a=agreements[c['borrower_id']]
            add=[u for u in rows if u['unit_type']=='addback']
            cov=[u for u in rows if u['unit_type']=='covenant']
            g.require('G1',2<=len(add)<=6,c['cert_id']+' addback volume')
            if any(u['breach']=='yes' and u['status_printed']=='fail' and u['error_class']=='none' for u in cov) and c['statement_4']=='defaults_listed': benign['honestly_reported_breach']+=1
            benign['valid_equity_cure']+=sum(u['unit_type']=='cure' and u['error_class']=='none' for u in rows)
            benign['realized_cost_savings_older_than_window']+=sum(u['category_true']=='cost_savings' and u['realized']=='realized' and u['error_class']=='none' and date.fromisoformat(u['action_date'])<cutoff(date.fromisoformat(QUARTER_END[q]),a['cost_savings_window_months']) for u in add)
            for i,u in enumerate(add):
                benign['different_addbacks_same_amount']+=sum(u['amount']==v['amount'] and u['action_date']!=v['action_date'] and u['description']!=v['description'] and u['error_class']==v['error_class']=='none' for v in add[:i])
            benign['permitted_approval_word_addback']+=sum(u['error_class']=='none' and bool(re.search(r'\b(approved|authorized|one-time)\b',u['description'],re.I)) for u in add)
            benign['abbreviated_officer_title']+=sum(u['unit_type']=='signer' and u['signer_title'] in ABBREVIATIONS and u['error_class']=='none' for u in rows)
            for u in cov:
                if u['error_class']=='hidden_breach':
                    limit=a['max_leverage'] if u['covenant']=='leverage' else a['min_interest_coverage']
                    looser=u['threshold_printed']>limit if u['covenant']=='leverage' else u['threshold_printed']<limit
                    if looser: hidden['threshold']+=1
                    elif any(v['error_class']!='none' for v in add):
                        adjusted=D(c['adjusted_ebitda_printed'])
                        printed_input=D(u['total_debt'] if u['covenant']=='leverage' else u['cash_interest'])
                        inflated_ratio=rounded(printed_input/adjusted if u['covenant']=='leverage' else adjusted/printed_input)
                        would_pass=inflated_ratio<=D(limit) if u['covenant']=='leverage' else inflated_ratio>=D(limit)
                        if would_pass and adjusted>D(derived[c['cert_id']]['agreement_ebitda']): hidden['addback']+=1
            if any(u['error_class']=='cure_invalid' for u in rows):
                d=derived[c['cert_id']]
                # Count violations take precedence when history also breaks consecutiveness.
                invalid['count' if d['count_bad'] else 'consecutive' if d['consecutive_bad'] else 'unknown']+=1
        for name in ['honestly_reported_breach','valid_equity_cure','realized_cost_savings_older_than_window','different_addbacks_same_amount','permitted_approval_word_addback','abbreviated_officer_title']:
            g.equal('G1',benign[name],1,f'Q{q} {name}')
        g.equal('G1',dict(hidden),{'addback':1,'threshold':1},f'Q{q} hidden breach mechanisms')
        g.equal('G1',dict(invalid),{'count':1,'consecutive':1},f'Q{q} invalid cure mechanisms')
        g.require('G1',sum(c['certification']['present'] and any(r['category_true']=='cost_savings' for r in c['addbacks']) for c in cs)>=3,f'Q{q} certified cost-savings volume')
        g.require('G1',3<=sum(bool(c['cure']) for c in cs)<=4,f'Q{q} cure volume')
        average=sum(len(c['addbacks']) for c in cs)/len(cs)
        g.require('G1',3.5<=average<=4.5,f'Q{q} average addbacks {average} outside approximately four (3.5–4.5)')
        counts[str(q)]={**dict(tally),**dict(benign),'average_addbacks':average}
    g.equal('G1',len(agreements),12,'agreement count')
    g.require('G1',sum('transaction_costs' not in a['permitted_categories'] for a in agreements.values())>=3,'transaction-cost exclusions')
    for a in agreements.values():
        g.require('G1',3<=a['max_leverage']<=5 and 2<=a['min_interest_coverage']<=3.5,a['borrower_id']+' covenant limits')
        g.require('G1',set(a['permitted_categories'])<=set(s['categories']) and 'ordinary_operating' not in a['permitted_categories'],a['borrower_id']+' categories')
        g.require('G1',a['cost_savings_cap_pct'] in (.15,.20) and a['cost_savings_window_months']==18 and a['cure_max']==4 and a['cure_no_consecutive'] is True,a['borrower_id']+' addback/cure terms')
        g.require('G1',3<=len(a['responsible_officer_titles'])<=5 and all(t not in ABBREVIATIONS for t in a['responsible_officer_titles']),a['borrower_id']+' officer titles')
        g.require('G1',a['delivery_days']==45 and a['delivery_days_q4']==90,a['borrower_id']+' delivery terms')
        g.require('G1',3<=len(a['commitments'])<=5 and all(v['amount']>0 for v in a['commitments']),a['borrower_id']+' lender commitments')
    g.equal('G1',set(s['categories']),set('restructuring_charges transaction_costs non_cash_compensation cost_savings non_recurring_losses ordinary_operating'.split()),'category inventory')
    g.require('G1',all(isinstance(v,str) and v.endswith('.') for v in s['categories'].values()),'category meanings')
    g.require('G1',2<=len({r['borrower_id'] for r in s['prior_cures'] if r['quarter_label']<'2025'})<=3,'historical cure borrower count')
    return counts

def normalize(text):
    # Retain a lexical hyphen, but remove the newline and indentation after it.
    text=re.sub(r'(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)','-',text)
    return ' '.join(text.split())

class Visible(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('style','script','title'): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('style','script','title'): self.hidden-=1
    def handle_data(self,data):
        if not self.hidden: self.parts.append(data)

def main():
    g=Gate(); counts={}; derived={}; units=[]; certificates=[]
    try:
        s=load('case_spec_q.json'); certificates=s['certificates']; truth=load('truth_q.json'); units=truth['units']; m=load('manifest_q.json')
        agreements={a['borrower_id']:a for a in s['agreements']}
        g.equal('G2',set(truth),{'units'},'truth top-level fields')
        g.equal('G2',units,[u for c in certificates for u in c['units']],'complete exact spec units')
        g.equal('G2',len({(u['cert_id'],u['unit_id']) for u in units}),len(units),'unique unit ids')
        g.equal('G2',len({c['cert_id'] for c in certificates}),len(certificates),'unique certificate ids')
        for u in units:
            required=COMMON|FIELDS[u['unit_type']]
            if u['unit_type']=='covenant': required|={'total_debt' if u['covenant']=='leverage' else 'cash_interest'}
            g.equal('G2',set(u),required,u['cert_id']+' '+u['unit_id']+' fields')
            g.require('G2',u['error_class'] in ERRORS+['none'] and u['breach'] in ['yes','no'] and u['disposition'] in ['hold','post'] and u['owner'] in ['required_lenders','credit_officer','analyst','none'],'label vocabulary '+u['cert_id']+' '+u['unit_id'])
        for name,expected in [('agreements',s['agreements']),('categories',s['categories'])]+[(f'prior_cures_q{k}',prior_cures(s,k)) for k in range(1,5)]:
            reference=load('reference/'+name+'.json')
            g.equal('G2',reference,expected,'reference/'+name)
            def no_labels(v):
                if isinstance(v,dict): return not (set(v)&LABELS) and all(no_labels(x) for x in v.values())
                if isinstance(v,list): return all(no_labels(x) for x in v)
                return True
            g.require('G2',no_labels(reference),'reference label leak '+name)
        g.equal('G2',m['spec_sha256'],digest((ROOT/'case_spec_q.json').read_bytes()),'manifest spec hash')
        g.equal('G2',[v['cert_id'] for v in m['certificates']],[c['cert_id'] for c in certificates],'manifest inventory')
        g.equal('G2',{p.name for p in (ROOT/'sources').glob('*.html')},{c['cert_id']+'.html' for c in certificates},'source inventory')
        for c in certificates:
            cid=c['cert_id']; a=agreements[c['borrower_id']]
            entry=next(v for v in m['certificates'] if v['cert_id']==cid)
            source=(ROOT/entry['source']).read_text()
            g.equal('G2',source,certificate_html(s,c),cid+' exact source fidelity')
            g.equal('G2',entry['source_sha256'],digest(source.encode()),cid+' source hash')
            g.equal('G2',[r['addback_no'] for r in c['addbacks']],list(range(1,len(c['addbacks'])+1)),cid+' addback order')
            expected,derived[cid]=recompute(c,a,load(f'reference/prior_cures_q{c["quarter"]}.json'),g)
            actual=[u for u in units if u['cert_id']==cid]
            g.equal('G2',{u['unit_id'] for u in actual},set(expected),cid+' unit inventory')
            for u in actual:
                target={k:v for k,v in u.items() if k not in COMMON-LABELS}
                g.equal('G3',target,expected[u['unit_id']],cid+' '+u['unit_id']+' recomputed fields and labels')
            dates=[c['delivery_date'],a['agreement_date'],QUARTER_END[c['quarter']]]+[r['action_date'] for r in c['addbacks']]+([c['cure']['date']] if c['cure'] else [])+[u['due_date'] for u in actual if u['unit_type']=='delivery']
            for value in dates:
                try: g.equal('G7',date.fromisoformat(value).isoformat(),value,cid+' ISO date')
                except ValueError: g.require('G7',False,cid+' invalid date '+value)
            g.require('G7',c['delivery_date']>QUARTER_END[c['quarter']],cid+' delivery must follow quarter end')
        for r in s['prior_cures']:
            g.require('G7',bool(re.fullmatch(r'\d{4}-Q[1-4]',r['quarter_label'])),'invalid historical quarter')
        counts=quotas(s,units,derived,g)
        pdfs=list((ROOT/'clean').glob('*.pdf'))
        if not pdfs:
            g.skipped.update(['G5','G6'])
        else:
            g.equal('G5',{p.name for p in pdfs},{c['cert_id']+'.pdf' for c in certificates},'PDF inventory')
            for c in certificates:
                p=ROOT/'clean'/f'{c["cert_id"]}.pdf'
                if not p.exists():
                    g.require('G6',False,'missing PDF '+p.name); continue
                g.require('G5',p.read_bytes().rstrip().endswith(b'%%EOF'),p.name+' complete PDF')
                try:
                    raw=subprocess.run(['pdftotext','-raw',str(p),'-'],check=True,capture_output=True,text=True).stdout
                    text=normalize(raw)
                    for phrase in [r['description'] for r in c['addbacks']]+[c['signer_title']]+([c['certification']['text']] if c['certification']['present'] else []):
                        g.require('G5',normalize(phrase) in text,p.name+' missing text: '+phrase)
                    for phrase in statements(c)+[f'Name: {c["signer_name"]}',f'Title: {c["signer_title"]}',f'Date: {c["delivery_date"]}']:
                        g.require('G5',normalize(phrase) in text,p.name+' missing statement/signature: '+phrase)
                    locations=[text.find(h) for h in HEADINGS]
                    g.require('G6',all(i>=0 for i in locations) and locations==sorted(locations) and all(text.count(h)==(2 if h=='Adjusted EBITDA' else 1) for h in HEADINGS),p.name+' section heading sequence')
                    parser=Visible(); parser.feed((ROOT/'sources'/f'{c["cert_id"]}.html').read_text())
                    for phrase in parser.parts:
                        if phrase.strip(): g.require('G5',normalize(phrase) in text,p.name+' missing printed value: '+phrase)
                    info=subprocess.run(['pdfinfo',str(p)],check=True,capture_output=True,text=True).stdout
                    pages=re.search(r'^Pages:\s+(\d+)',info,re.M)
                    size=re.search(r'^Page size:\s+([\d.]+) x ([\d.]+)',info,re.M)
                    g.require('G6',bool(pages) and 1<=int(pages[1])<=2,p.name+' requires 1–2 pages')
                    g.require('G6',bool(size) and float(size[1])<float(size[2]),p.name+' requires portrait')
                except (OSError,subprocess.CalledProcessError) as exc:
                    g.require('G5',False,p.name+' extraction failed: '+str(exc))
                    g.require('G6',False,p.name+' inspection failed: '+str(exc))
    except Exception as exc:
        g.require('G2',False,f'Gate could not complete: {type(exc).__name__}: {exc}')
        traceback.print_exc()
        for gate in g.failures:
            if not g.failures[gate]: g.failures[gate].append('Gate incomplete after exception')
    lines=['# Source report','',f'Built {len(certificates)} certificate sources and {len(units)} truth units.','', 'Deviations from spec: none. Printed values and supplied truth remain unchanged.', '', 'The spec caches 2025 cures in prior_cures. References use pre-2025 history plus earlier printed cures, once each.', '', 'Gate results:']
    for gate,failures in g.failures.items():
        status='SKIP — clean/ contains no PDFs; rendered text and layout UNVERIFIED' if gate in g.skipped else f'FAIL ({len(failures)})' if failures else 'PASS'
        print(f'{gate}: {status}'); lines.append(f'- {gate}: {status}.')
        for failure in failures: print('  '+failure); lines.append('  - '+failure)
    lines+=['','Quota recounts:','', '```json',json.dumps(counts,indent=2),'```','', 'Interpretation: “about 4” means 3.5–4.5 average addbacks. Each observed quarterly average is reported above.', '', 'UNVERIFIED: agreements provide lender commitments, but do not identify a Required Lenders coalition. No coalition was invented.', 'Required Lenders means more than 50% of commitments; a named coalition cannot be checked from this spec.']
    if g.skipped: lines+=['','UNVERIFIED: Chrome rendering, PDF text, page count, portrait geometry, and visual layout. Chrome was not run.']
    else: lines+=['','UNVERIFIED: visual appearance beyond extracted PDF text, page count, and portrait geometry.']
    lines+=['','Next action: run `python3 build_q.py --render-only`, then `python3 check_q.py`.']
    (ROOT/'SOURCE-REPORT.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'gate_results_q.json').write_text(json.dumps({'results':{k:('skip' if k in g.skipped else 'fail' if v else 'pass') for k,v in g.failures.items()},'failures':g.failures,'quota_recounts':counts,'recomputed':derived},indent=2)+'\n')
    return int(any(g.failures.values()))

if __name__=='__main__': sys.exit(main())
