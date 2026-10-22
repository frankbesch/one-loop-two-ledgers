#!/usr/bin/env python3
"""Offline build gate. PDF checks use only pdftotext -bbox-layout word geometry."""
import calendar
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
FAIL=defaultdict(list)
DETAIL=defaultdict(list)
D=lambda x:Decimal(str(x))
Q=lambda x:D(x).quantize(D('.01'),rounding=ROUND_HALF_UP)
FIELD={'property':'property_printed','decimal':'owner_decimal','net':'net_amount'}
LABELS={
 'money_error':{'none','wrong_decimal','wrong_rate','nonconsent_property','afe_overrun','duplicate','date_window'},
 'claim_type':{'claims_afe','claims_other','no_claim'},
 'reference_kind':{'exact','reformatted','reworded','placeholder','unknown_number','no_number','none'},
 'placeholder_style':{'literal','paraphrased','n_a'},
 'property_match':{'match','mismatch','n_a'},
 'authority_kind':{'emergency','service_contract','operating_agreement_clause','prior_election','verbal_or_informal','operator_policy','other','n_a'},
 'outcome':{'supported','unsupported','contradicted','other_authority','no_claim'},
 'difficulty':{'plain','hard'},'property_print':{'exact','variant'},'disposition':{'post','hold'}}
LINE_KEYS=set('line_no page property_printed property_no property_print account description reference vendor invoice_no service_date quantity unit_rate gross owner_decimal net_amount money_error error_dollars claim_type reference_kind placeholder_style property_match authority_kind outcome difficulty claim_text claim_location disposition'.split())
LEDGER='doc_id line_no property_printed vendor invoice_no service_date reference gross net_amount'.split()

def require(g, condition, message):
    if not condition:
        FAIL[g].append(message)

def unique_object(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise ValueError(f'Duplicate JSON key: {k}')
        out[k]=v
    return out

def load(path):
    return json.loads((ROOT/path).read_text(),object_pairs_hook=unique_object)

def printed(k,v):
    return '' if v is None else f'{Q(v):.2f}' if k in ('gross','net','unit_rate') else str(v)

def text(el):
    return ''.join(el.itertext())

def norm(s):
    return re.sub(r'\s+',' ',s).strip()

def ids(s):
    found=[]
    for m in re.finditer(r'BX\s*:\s*(\d+)\s*:\s*K|K\s*\[\s*(\d+)\s*\]\s*/\s*BX',s,re.I):
        found.append((f'BX:{int(m.group(1) or m.group(2)):04d}:K',m.group()))
    return found

def in_force(rows, when, **keys):
    candidates=[r for r in rows if all(r[k]==v for k,v in keys.items()) and r['effective']<=when]
    if not candidates:
        raise ValueError(f'No effective reference for {keys} at {when}')
    return max(candidates,key=lambda r:r['effective'])

def month_end(period):
    y,m=map(int,period.split('-'))
    return date(y,m,calendar.monthrange(y,m)[1])

def months_before(dt,n):
    y,m=divmod(dt.year*12+dt.month-1-n,12)
    return date(y,m+1,min(dt.day,calendar.monthrange(y,m+1)[1]))

def check_quotas(s):
    for m in s['months']:
        docs=[d for d in s['documents'] if d['month']==m['month']]
        lines=[l for d in docs for l in d['lines']]
        count=Counter(l['money_error'] for l in lines)
        for k in LABELS['money_error']-{'none'}:
            require('G1',count[k]>=4,f'Month {m["month"]}: {k} {count[k]} < 4')
        counts={k:sum(l['outcome']==k for l in lines) for k in ('supported','contradicted','other_authority')}
        for k in ('placeholder','unknown_number','no_number'):
            counts[k]=sum(l['outcome']=='unsupported' and l['reference_kind']==k for l in lines)
        counts['wrong_property']=sum(l['outcome']=='unsupported' and l['property_match']=='mismatch' for l in lines)
        counts['no_claim_bait']=sum(l['outcome']=='no_claim' and re.search(r'\b(?:approved|authorized)\b',l['description'],re.I) is not None for l in lines)
        counts['hard']=sum(l['difficulty']=='hard' for l in lines)
        counts['remarks_no_claim']=sum(r['remark_role']=='no_claim' for d in docs for r in d['remarks'])
        counts['property_variant']=sum(l['property_print']=='variant' for l in lines)
        for k,n in dict(supported=6,placeholder=3,unknown_number=3,no_number=2,wrong_property=2,contradicted=2,other_authority=2,no_claim_bait=2,hard=2,remarks_no_claim=2,property_variant=8).items():
            require('G1',counts[k]>=n,f'Month {m["month"]}: {k} {counts[k]} < {n}')
        para=sum(l['reference_kind']=='placeholder' and l['placeholder_style']=='paraphrased' for l in lines)
        require('G1',para*2>=counts['placeholder'],f'Month {m["month"]}: fewer than half placeholders paraphrased')
        DETAIL['G1'].append(f'Month {m["month"]}: '+', '.join(f'{k}={v}' for k,v in (dict(count,**counts,paraphrased_placeholder=para)).items() if k!='none'))
    scored=Counter(l['money_error'] for d in s['documents'] if d['month'] in (3,4,5,6) for l in d['lines'])
    for k in LABELS['money_error']-{'none'}:
        require('G1',scored[k]>=16,f'Scored corpus: {k} < 16')
    # Changes must occur in the stated months, not merely exist in quota_check.
    r=s['reference']; periods={m['month']:m['billing_period'] for m in s['months']}
    for key,month in [('doi',2),('afe_register',3),('elections',5),('contract_rates',4)]:
        stamp='approved_on' if key=='afe_register' else 'effective'
        rows=[v for v in r[key] if v[stamp].startswith(periods[month])]
        if key=='elections': rows=[v for v in rows if v['election']=='nonconsent']
        if key=='afe_register': rows=[v for v in rows if v['status']=='approved']
        require('G1',bool(rows),f'Missing month {month} reference change: {key}')
        if key in ('doi','contract_rates'):
            keys=['property_no'] if key=='doi' else ['vendor','service']
            value='owner_decimal' if key=='doi' else 'rate'
            require('G1',any(any(all(old[k]==v[k] for k in keys) and old[stamp]<v[stamp] and old[value]!=v[value] for old in r[key]) for v in rows),f'{key} does not change a prior value')

def check_claim(l,d,register):
    tag=f'{d["doc_id"]}:{l["line_no"]}'
    remarks=[r for r in d['remarks'] if r['names_line']==l['line_no']]
    ct=l['claim_text']
    claim_remarks=[r for r in remarks if r['remark_role']=='claim']
    require('G3',l['difficulty']==('hard' if claim_remarks else 'plain'),f'{tag}: difficulty')
    if ct is not None:
        loc=l['claim_location']
        source=' '.join(r['text'] for r in claim_remarks) if loc=='remark' else l.get(loc,'')
        require('G3',ct in source,f'{tag}: claim text absent from claimed location')
        if loc=='remark':
            require('G3',ct not in l['description'] and ct not in l['reference'],f'{tag}: hard claim also in line')
    else:
        require('G3',l['claim_location'] is None and not claim_remarks,f'{tag}: missing claim text')
    # Derive cases from visible language, independent of expected outcome labels.
    visible=' '.join([l['description'],l['reference']]+[r['text'] for r in remarks])
    afe_claim=bool(re.search(r'\bAFE\b|expenditure authorization.*approved|Approved expenditure authorization',visible,re.I))
    other='emergency' if 'Emergency authority covers' in visible else 'service_contract' if 'Service contract authorizes' in visible else None
    typ='claims_afe' if afe_claim else 'claims_other' if other else 'no_claim'
    require('G3',l['claim_type']==typ,f'{tag}: claim_type')
    require('G3',(ct is not None)==(typ!='no_claim'),f'{tag}: claim presence')
    kind='none'; style='n_a'; match='n_a'; authority='n_a'
    outcome='no_claim'
    if typ=='claims_other':
        outcome='other_authority'; authority=other
    elif typ=='claims_afe':
        c=ct or ''; numbers=ids(c)
        placeholder=re.search(r'\b(?:TBD|Pending|N/A|To follow)\b|number will arrive|identifier awaits entry|^AFE:\s*[-–—]$',c,re.I)
        if placeholder:
            kind='placeholder'; outcome='unsupported'
            style='literal' if c.removeprefix('AFE:').strip() in ('N/A','TBD','Pending','To follow','-','–','—') else 'paraphrased'
        elif not numbers:
            kind='no_number'; outcome='unsupported'
        else:
            number,display=numbers[0]; a=register.get(number)
            if a is None:
                kind='unknown_number'; outcome='unsupported'
            else:
                kind='reworded' if re.search(r'authorizes|covers this work',c) else 'exact' if display==number else 'reformatted'
                if a['approved_on']>l['service_date']:
                    outcome='unsupported'
                elif a['status']=='declined':
                    outcome='contradicted'
                else:
                    match='match' if a['property_no']==l['property_no'] else 'mismatch'
                    outcome='supported' if match=='match' else 'unsupported'
    for k,v in dict(reference_kind=kind,placeholder_style=style,property_match=match,authority_kind=authority,outcome=outcome).items():
        require('G3',l[k]==v,f'{tag}: {k} {l[k]} != derived {v}')
    disposition='hold' if l['money_error']!='none' or outcome in ('unsupported','contradicted','other_authority') else 'post'
    require('G3',l['disposition']==disposition,f'{tag}: disposition')

def check_reference(s,truth):
    refs=s['reference']
    for k,v in refs.items():
        require('G3',load(f'reference/{k}.json')==v,f'Reference {k} differs from spec')
    properties=[{k:p[k] for k in ('property_no','name')} for p in s['entities']['properties']]
    require('G3',load('reference/properties.json')==properties,'Property master differs or exposes variants')
    for k in range(2,7):
        expected=[{f:l[f] for f in LEDGER} for l in truth['lines'] if l['month']<k]
        require('G3',load(f'reference/prior_ledger_m{k}.json')==expected,f'Prior ledger m{k} differs')
    expected_files={f'{k}.json' for k in refs}|{'properties.json'}|{f'prior_ledger_m{k}.json' for k in range(2,7)}
    require('G3',{p.name for p in (ROOT/'reference').iterdir()}==expected_files,'Unexpected reference files')
    register={a['afe_number']:a for a in refs['afe_register']}
    seen=set(); cumulative=defaultdict(Decimal)
    months={m['month']:m for m in s['months']}
    props={p['property_no']:p for p in s['entities']['properties']}
    for d in s['documents']:
        end=month_end(months[d['month']]['billing_period'])
        for l in d['lines']:
            tag=f'{d["doc_id"]}:{l["line_no"]}'
            when=l['service_date']; gross=D(l['gross']); dec=D(l['owner_decimal']); net=D(l['net_amount'])
            correct=D(in_force(refs['doi'],when,property_no=l['property_no'])['owner_decimal'])
            errors={}
            if dec!=correct:
                errors['wrong_decimal']=net-Q(gross*correct)
            if l['quantity'] is not None:
                service=l['description'].split(';')[0]
                rate=D(in_force(refs['contract_rates'],when,vendor=l['vendor'],service=service)['rate'])
                if D(l['unit_rate'])!=rate:
                    errors['wrong_rate']=net-Q(D(l['quantity'])*rate*dec)
            election=in_force(refs['elections'],when,property_no=l['property_no'])
            if election['election']=='nonconsent' and election['effective']<when:
                errors['nonconsent_property']=net
            key=(l['vendor'],l['invoice_no'],gross)
            if key in seen: errors['duplicate']=net
            seen.add(key)
            service=date.fromisoformat(when)
            if service>end or service<months_before(end,refs['joa_terms']['exception_window_months']):
                errors['date_window']=net
            references=l['reference']+' '+(l['claim_text'] or '')
            for number in {a for a,_ in ids(references)}:
                a=register.get(number)
                if a and a['status']=='approved' and a['approved_on']<=when:
                    limit=D(a['approved_amount'])*(1+D(refs['joa_terms']['afe_overrun_tolerance']))
                    prior=cumulative[number]; cumulative[number]+=gross
                    excess=max(D(0),cumulative[number]-limit)-max(D(0),prior-limit)
                    if excess>0:
                        errors['afe_overrun']=Q(excess*dec)
            require('G3',len(errors)<=1,f'{tag}: multiple actual money errors {list(errors)}')
            actual=next(iter(errors),'none')
            require('G3',l['money_error']==actual,f'{tag}: money_error {l["money_error"]} != {actual}')
            require('G3',D(l['error_dollars'])==errors.get(actual,D(0)),f'{tag}: error_dollars {l["error_dollars"]} != {errors.get(actual,0)}')
            prop=props[l['property_no']]
            exact=l['property_printed'] in (prop['property_no'],prop['name'])
            require('G3',exact or l['property_printed'] in prop['name_variants'],f'{tag}: property cannot be linked')
            require('G3',l['property_print']==('exact' if exact else 'variant'),f'{tag}: property_print')
            check_claim(l,d,register)


def check_sources(s,truth,manifest):
    expected_lines=[dict(month=d['month'],doc_id=d['doc_id'],**l) for d in s['documents'] for l in d['lines']]
    expected_remarks=[dict(month=d['month'],doc_id=d['doc_id'],**r) for d in s['documents'] for r in d['remarks']]
    require('G2',set(truth)=={'lines','remarks'},'Truth top-level schema')
    require('G2',truth['lines']==expected_lines,'Truth lines differ from spec')
    require('G2',truth['remarks']==expected_remarks,'Truth remarks differ from spec')
    require('G2',len({(l['doc_id'],l['line_no']) for l in truth['lines']})==len(truth['lines']),'Duplicate truth lines')
    for d in s['documents']:
        for l in d['lines']:
            tag=f'{d["doc_id"]}:{l["line_no"]}'
            require('G2',set(l)==LINE_KEYS,f'{tag}: field schema')
            for k,values in LABELS.items():
                require('G2',isinstance(l[k],str) and l[k] in values,f'{tag}: invalid {k}')
            require('G2',isinstance(l['error_dollars'],(int,float)) and not isinstance(l['error_dollars'],bool),f'{tag}: invalid error_dollars')
            require('G4',Q(D(l['gross'])*D(l['owner_decimal']))==D(l['net_amount']),f'{tag}: net arithmetic')
            require('G4',(l['quantity'] is None)==(l['unit_rate'] is None),f'{tag}: partial rate fields')
            if l['quantity'] is not None:
                require('G4',D(l['gross'])==D(l['quantity'])*D(l['unit_rate']),f'{tag}: rate arithmetic')
        require('G7',set(l['page'] for l in d['lines'])==set(range(1,d['pages']+1)),f'{d["doc_id"]}: page assignments')
        for r in d['remarks']:
            require('G2',set(r)=={'remark_id','page','names_line','text','remark_role'},f'{d["doc_id"]}: remark fields')
            require('G2',r['remark_role'] in ('claim','no_claim'),f'{d["doc_id"]}: remark role')
            require('G7',any(l['line_no']==r['names_line'] for l in d['lines']),f'{d["doc_id"]}: remark references missing line')
            require('G7',r['text'].startswith(f'Line {r["names_line"]}:'),f'{d["doc_id"]}: remark names wrong line')
            require('G7',1<=r['page']<=d['pages'],f'{d["doc_id"]}: remark page')
        require('G2',[r['remark_id'] for r in d['remarks']]==list(range(1,len(d['remarks'])+1)),f'{d["doc_id"]}: remark order')
    require('G2',manifest['spec_sha256']==hashlib.sha256((ROOT/'case_spec_m.json').read_bytes()).hexdigest(),'Manifest spec hash')
    require('G2',[m['doc_id'] for m in manifest['documents']]==[d['doc_id'] for d in s['documents']],'Manifest documents')
    require('G2',{p.name for p in (ROOT/'sources').glob('*.html')}=={d['doc_id']+'.html' for d in s['documents']},'HTML source file set')
    for d,m in zip(s['documents'],manifest['documents']):
        source=ROOT/m['source']; raw=source.read_bytes()
        require('G2',hashlib.sha256(raw).hexdigest()==m['source_sha256'],f'{d["doc_id"]}: source hash')
        root=ET.fromstring(raw)
        css=text(root.find('.//style'))
        require('G7','break-inside:avoid' in css and 'break-after:page' in css,f'{d["doc_id"]}: missing page/row break protection')
        for key in ('month','type','format','pages'):
            require('G2',m[key]==d[key],f'{d["doc_id"]}: manifest {key}')
        pages=root.findall('.//section')
        require('G7',len(pages)==d['pages'],f'{d["doc_id"]}: HTML page count')
        fmt=s['formats'][d['format']]; order=fmt['column_order']
        for pn,page in enumerate(pages,1):
            tag=f'{d["doc_id"]} page {pn}'
            headers=[text(h) for h in page.findall('.//th')]
            require('G2',headers==[fmt['headers'][k] for k in order],f'{tag}: source headers/order')
            lines=[l for l in d['lines'] if l['page']==pn]
            rows=page.findall('.//tbody/tr')
            require('G2',len(rows)==len(lines),f'{tag}: HTML line count')
            for row,l in zip(rows,lines):
                require('G2',[text(td) for td in row.findall('td')]==[printed(k,l[FIELD.get(k,k)]) for k in order],f'{tag} line {l["line_no"]}: printed fields')
                require('G7',row.attrib['data-line']==str(l['line_no']),f'{tag}: row/page identity')
            require('G2',[text(r) for r in page.findall("div[@class='note']")]==[r['text'] for r in d['remarks'] if r['page']==pn],f'{tag}: source remarks')
            total_nodes=page.findall("div[@class='totals']")
            groups=[lines]+([d['lines']] if pn==d['pages'] else [])
            require('G4',len(total_nodes)==len(groups),f'{tag}: total count')
            for node,group in zip(total_nodes,groups):
                g=f'{sum((D(l["gross"]) for l in group),D(0)):.2f}'
                n=f'{sum((D(l["net_amount"]) for l in group),D(0)):.2f}'
                require('G4',node.attrib['data-gross']==g and node.attrib['data-net']==n and [text(v) for v in node.findall('span')]==[f'Gross: {g}',f'Net: {n}'],f'{tag}: printed totals')
        for k in ('gross','net_amount'):
            require('G4',D(m['totals'][k])==sum(D(l[k]) for l in d['lines']),f'{d["doc_id"]}: manifest total {k}')


def check_dates(s):
    periods=[]
    def valid(value,where):
        try:
            require('G8',date.fromisoformat(value).isoformat()==value,where)
        except (ValueError,TypeError):
            require('G8',False,f'{where}: invalid date {value}')
    for m in s['months']:
        end=month_end(m['billing_period']); periods.append(end.year*12+end.month)
    require('G8',all(b-a==1 for a,b in zip(periods,periods[1:])),'Billing periods not consecutive')
    require('G8',[m['month'] for m in s['months']]==list(range(1,7)),'Month sequence')
    for d in s['documents']:
        require('G8',d['month'] in [m['month'] for m in s['months']],f'{d["doc_id"]}: month')
        for l in d['lines']: valid(l['service_date'],f'{d["doc_id"]}:{l["line_no"]}')
    for name,rows in s['reference'].items():
        if isinstance(rows,list):
            for row in rows:
                for k in ('effective','approved_on'):
                    if k in row: valid(row[k],f'{name}.{k}')


def visual_lines(words):
    """Group words by baseline before reading left to right; ignore XML flow order."""
    rows=[]
    for w in sorted(words,key=lambda w:(w['y0'],w['x0'])):
        row=next((r for r in reversed(rows[-4:]) if abs(r[0]['y0']-w['y0'])<1.2),None)
        if row is None: rows.append([w])
        else: row.append(w)
    return [sorted(r,key=lambda w:w['x0']) for r in rows]


def bbox_text(words):
    result=''
    for row in visual_lines(words):
        part=' '.join(w['text'] for w in row)
        # Preserve an actual in-word hyphen across a visual wrap, without adding a space.
        separator='' if result.endswith('-') and part[:1].isalnum() else ' '
        result+=separator+part
    return norm(result)


def box_words(words,left,right,top=-1,bottom=float('inf')):
    return [w for w in words if left<=w['x0']<right and top<=w['y0']<bottom]


def check_pdfs(s,truth,manifest):
    clean=ROOT/'clean'
    if not clean.exists() or not any(clean.iterdir()):
        DETAIL['G5'].append('SKIP: clean/ is empty; rendered claim and remark text is UNVERIFIED.')
        DETAIL['G6'].append('SKIP: clean/ is empty; rendered header labels and order are UNVERIFIED.')
        DETAIL['G7'].append('Source page assignments and indivisible HTML rows pass; rendered page boundaries are UNVERIFIED.')
        return False
    expected={d['doc_id']+'.pdf' for d in s['documents']}
    actual={p.name for p in clean.glob('*.pdf')}
    require('G5',actual==expected,f'PDF set differs: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
    for d,m in zip(s['documents'],manifest['documents']):
        pdf=ROOT/m['pdf']
        if not pdf.exists(): continue
        try:
            require('G5',pdf.read_bytes().rstrip().endswith(b'%%EOF'),f'{d["doc_id"]}: PDF incomplete')
            cp=subprocess.run(['pdftotext','-bbox-layout',str(pdf),'-'],capture_output=True,text=True,timeout=45)
            if cp.returncode: raise ValueError(cp.stderr)
            xml=ET.fromstring(cp.stdout)
            pdfpages=xml.findall('.//{*}page')
            require('G7',len(pdfpages)==d['pages'],f'{d["doc_id"]}: PDF page count')
            source=ET.fromstring((ROOT/m['source']).read_text())
            fmt=s['formats'][d['format']]; order=fmt['column_order']
            fractions=[float(c.attrib['style'].split(':')[1].rstrip('%'))/100 for c in source.findall('.//section')[0].findall('.//col')]
            for pn,pdfpage in enumerate(pdfpages,1):
                tag=f'{d["doc_id"]} page {pn}'
                words=[dict(text=w.text or '',x0=float(w.attrib['xMin']),x1=float(w.attrib['xMax']),y0=float(w.attrib['yMin']),y1=float(w.attrib['yMax'])) for w in pdfpage.findall('.//{*}word')]
                pagewidth=float(pdfpage.attrib['width']); pageheight=float(pdfpage.attrib['height'])
                require('G7',abs(pagewidth-1224)<2 and abs(pageheight-792)<2,f'{tag}: page dimensions')
                require('G7',all(w['x0']>=0 and w['x1']<=pagewidth+1 and w['y0']>=0 and w['y1']<=pageheight+1 for w in words),f'{tag}: content outside page')
                left=.55*72; usable=pagewidth-2*left
                bounds=[left]
                for f in fractions: bounds.append(bounds[-1]+usable*f)
                def col(k,top=-1,bottom=float('inf')):
                    i=order.index(k)
                    return box_words(words,bounds[i],bounds[i+1],top,bottom)
                # Locate the row containing BOTH identifying labels. Remarks cannot match it.
                first=fmt['headers']['line_no'].split()[0]
                second=fmt['headers']['property'].split()[0]
                candidates=[w['y0'] for w in col('line_no') if w['text']==first and any(v['text']==second and abs(v['y0']-w['y0'])<1.2 for v in col('property'))]
                require('G6',len(candidates)==1,f'{tag}: expected exactly one header row with line-number and property labels')
                if len(candidates)!=1: continue
                top=candidates[0]; header_bottom=top
                for k in order:
                    expected_header=fmt['headers'][k]
                    selected=[]; found=False
                    for row in visual_lines(col(k,top-.5,top+55)):
                        selected+=row
                        if bbox_text(selected)==expected_header:
                            found=True; break
                    require('G6',found,f'{tag}: header {k} missing, altered, or out of order')
                    if found: header_bottom=max(header_bottom,max(w['y1'] for w in selected))
                header_band=box_words(words,left,pagewidth-left,top-.5,header_bottom+1)
                for k in order:
                    i=order.index(k)
                    actual_header=bbox_text(box_words(header_band,bounds[i],bounds[i+1]))
                    require('G6',actual_header==fmt['headers'][k],f'{tag}: extra or missing header text in {k}')
                if d['format']=='B':
                    for a in s['formats']['A']['headers'].values():
                        require('G6',all(a not in bbox_text(col(k,top-.5,header_bottom+1)) for k in order),f'{tag}: format A header {a}')
                lines=[l for l in d['lines'] if l['page']==pn]
                anchors=[w for w in col('line_no',header_bottom+1) if re.fullmatch(r'\d+',w['text'])]
                anchors.sort(key=lambda w:w['y0'])
                require('G7',[w['text'] for w in anchors]==[str(l['line_no']) for l in lines],f'{tag}: PDF line identities/page assignment')
                subtotal=[w for w in words if w['text']=='subtotal' and w['y0']>header_bottom]
                require('G4',len(subtotal)==1,f'{tag}: page subtotal missing')
                if not subtotal: continue
                table_end=subtotal[0]['y0']
                for idx,(anchor,l) in enumerate(zip(anchors,lines)):
                    end=anchors[idx+1]['y0']-.5 if idx+1<len(anchors) else table_end-.5
                    cells={k:bbox_text(col(k,anchor['y0']-.5,end)) for k in order}
                    for k in order:
                        require('G7',cells[k]==norm(printed(k,l[FIELD.get(k,k)])),f'{tag} line {l["line_no"]}: field {k} missing, changed, or crosses a page/row')
                    if l['claim_text'] is not None and l['claim_location']!='remark':
                        require('G5',norm(l['claim_text']) in cells[l['claim_location']],f'{tag} line {l["line_no"]}: claim missing in word boxes')
                for title,group in [('Page subtotal',lines)]+([('Document total',d['lines'])] if pn==d['pages'] else []):
                    target=title.split()[-1]
                    markers=[w for w in words if w['text']==target and w['y0']>=table_end-1]
                    g=f'{sum((D(l["gross"]) for l in group),D(0)):.2f}'
                    n=f'{sum((D(l["net_amount"]) for l in group),D(0)):.2f}'
                    require('G4',any(bbox_text([w for w in words if abs(w['y0']-marker['y0'])<1.2])==f'{title} Gross: {g} Net: {n}' for marker in markers),f'{tag}: rendered {title} arithmetic')
                remarks=[r for r in d['remarks'] if r['page']==pn]
                starts=sorted([w for w in words if w['text']=='Line' and w['y0']>table_end],key=lambda w:w['y0'])
                require('G5',len(starts)==len(remarks),f'{tag}: rendered remark count')
                for idx,(start,r) in enumerate(zip(starts,remarks)):
                    footer_top=min((w['y0'] for w in words if w['text']==d['doc_id'] and w['y0']>table_end),default=pageheight-28)
                    end=starts[idx+1]['y0']-.5 if idx+1<len(starts) else footer_top-.5
                    actual_remark=bbox_text(box_words(words,left,pagewidth-left,start['y0']-.5,end))
                    require('G5',actual_remark==norm(r['text']),f'{tag}: remark {r["remark_id"]} absent or changed')
                    for l in d['lines']:
                        if l['line_no']==r['names_line'] and l['claim_location']=='remark':
                            require('G5',norm(l['claim_text']) in actual_remark,f'{tag}: remark claim missing')
        except (OSError,ValueError,ET.ParseError,subprocess.SubprocessError) as exc:
            require('G5',False,f'{d["doc_id"]}: bbox check failed: {exc}')
    return True


def report(rendered):
    out=['# Source report','', 'Deviations from the supplied spec: none detected.' if not FAIL else 'Deviations or gate failures: see the failures below.', '', 'The reference builder was read, never executed. No network or scan set is used.', 'Sources use 17 × 11 inch landscape pages and preserve all specified page assignments.', '', '## Gate results','']
    for g in (f'G{i}' for i in range(1,9)):
        skipped=not rendered and g in ('G5','G6')
        state='FAIL' if FAIL[g] else 'SKIP' if skipped else 'PASS (source checks; PDF boundaries UNVERIFIED)' if not rendered and g=='G7' else 'PASS'
        line=f'{g}: {state}'
        print(line); out.append('- '+line+'.')
        if g!='G1': out.extend('  - '+v for v in DETAIL[g])
        out.extend('  - '+v for v in FAIL[g])
    out+=['','## Verification limits','']
    if not rendered:
        out+=['UNVERIFIED: Chrome rendering, visual layout, rendered totals, rendered claim/remark text, rendered headers, and rendered page boundaries.', 'G5 and G6 explicitly skipped because clean/ is empty. HTML fields, source totals, and row/page assignments were checked.', 'Next action: run `python3 build_m.py --render-only`, then `python3 check_m.py` in the rendering session.']
    else:
        out+=['PDF text, headers, totals, and line/page boundaries were checked with `pdftotext -bbox-layout`.', 'UNVERIFIED: visual appearance beyond the word-box and page-boundary checks.']
    out+=['','## Recount from spec labels','']
    out+=DETAIL['G1']
    (ROOT/'SOURCE-REPORT.md').write_text('\n'.join(out)+'\n')
    if any(FAIL.values()):
        for g,errors in FAIL.items():
            for error in errors[:12]: print(f'{g}: {error}',file=sys.stderr)
        return 1
    return 0


def main():
    rendered=False
    try:
        s=load('case_spec_m.json'); truth=load('truth_m.json'); manifest=load('manifest_m.json')
        checks=[('G1',lambda:check_quotas(s)),('G2',lambda:check_sources(s,truth,manifest)),('G8',lambda:check_dates(s)),('G3',lambda:check_reference(s,truth))]
        for g,fn in checks:
            try: fn()
            except Exception as exc: require(g,False,f'{type(exc).__name__}: {exc}')
        rendered=check_pdfs(s,truth,manifest)
    except Exception as exc:
        require('G2',False,f'{type(exc).__name__}: {exc}')
    return report(rendered)

if __name__=='__main__':
    sys.exit(main())
