#!/usr/bin/env python3
"""Build gate for the quarterly compliance certificate corpus. Exits non-zero on any failure."""
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUARTER_END = {1: '2025-03-31', 2: '2025-06-30', 3: '2025-09-30', 4: '2025-12-31'}
HEADINGS = ['Quarterly Compliance Certificate', 'Schedule 1: Consolidated EBITDA (last four quarters)',
            'Addbacks', 'Schedule 2: Financial covenants']
CLASSES = ['ratio_arithmetic', 'hidden_breach', 'cap_exceeded', 'window_expired', 'category_not_permitted',
           'certification_missing', 'signer_not_officer', 'late_delivery', 'cure_invalid', 'duplicate_addback']
ADDBACK_CLASSES = {'cap_exceeded', 'window_expired', 'category_not_permitted', 'certification_missing', 'duplicate_addback'}
LABELS = ['error_class', 'breach', 'disposition', 'owner']
COMMON = ['cert_id', 'quarter', 'borrower_id', 'unit_id', 'unit_type']
FIELDS = {
    'addback': ['addback_no', 'description', 'amount', 'action_date', 'category_printed', 'category_true', 'realized', 'certified'],
    'leverage': ['covenant', 'total_debt', 'adjusted_ebitda', 'ratio_printed', 'threshold_printed', 'status_printed', 'ratio_agreement'],
    'interest_coverage': ['covenant', 'cash_interest', 'adjusted_ebitda', 'ratio_printed', 'threshold_printed', 'status_printed', 'ratio_agreement'],
    'delivery': ['delivery_date', 'due_date'],
    'signer': ['signer_name', 'signer_title'],
    'cure': ['cure_amount', 'cure_date'],
}
ENUMS = {'error_class': ['none']+CLASSES, 'breach': ['yes', 'no'], 'disposition': ['hold', 'post'],
         'owner': ['required_lenders', 'credit_officer', 'analyst', 'none'], 'realized': ['realized', 'projected'],
         'certified': ['yes', 'no', 'n_a'], 'status_printed': ['pass', 'fail']}
ABBREV = {'cfo': 'chief financial officer', 'ceo': 'chief executive officer', 'cao': 'chief accounting officer',
          'coo': 'chief operating officer', 'evp': 'executive vice president', 'svp': 'senior vice president', 'vp': 'vice president'}
APPROVAL = re.compile(r'approv|one-time', re.I)

failures = defaultdict(list)
notes = []


def fail(gate, msg):
    failures[gate].append(msg)


def d2(x):
    return Decimal(x).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def load(path):
    return json.loads((ROOT/path).read_text())


def parse_date(s):
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
            return None
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def months_before(d, months):
    y, m = divmod(d.year*12+d.month-1-months, 12)
    m += 1
    last = (date(y+m//12, m % 12+1, 1)-timedelta(days=1)).day
    return date(y, m, min(d.day, last))


def money(s):
    m = re.fullmatch(r'(-?)\$(\d{1,3}(?:,\d{3})*)', s)
    if not m:
        raise ValueError(f'bad money {s!r}')
    return (-1 if m.group(1) else 1)*int(m.group(2).replace(',', ''))


def ratio(s):
    m = re.fullmatch(r'(\d+\.\d{2})x', s)
    if not m:
        raise ValueError(f'bad ratio {s!r}')
    return Decimal(m.group(1))


def norm_title(t):
    words = re.sub(r'[^a-z ]', ' ', t.lower()).split()
    words = ' '.join(ABBREV.get(w, w) for w in words).split()
    return ' '.join(w for w in words if w not in ('and', 'of', 'the'))


class Source(HTMLParser):
    """Collects every data-f value as visible text, with its row context, plus headings."""
    def __init__(self):
        super().__init__()
        self.stack, self.fields, self.headings, self.addbacks, self.covenants = [], {}, [], [], {}
        self.row = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'tr' and 'data-addback' in a:
            self.row = {}
            self.addbacks.append(self.row)
        elif tag == 'tr' and 'data-covenant' in a:
            self.row = {}
            self.covenants[a['data-covenant']] = self.row
        entry = {'tag': tag, 'f': a.get('data-f'), 'v': a.get('data-v'), 'h': 'data-heading' in a, 'text': []}
        self.stack.append(entry)

    def handle_endtag(self, tag):
        e = self.stack.pop()
        assert e['tag'] == tag, (e['tag'], tag)
        text = ''.join(e['text'])
        for p in self.stack:
            p['text'].append(text)
        if e['h']:
            self.headings.append(text)
        if e['f']:
            target = self.row if self.row is not None else self.fields
            target[e['f']] = e['v'] if e['v'] is not None else text
        if tag == 'tr':
            self.row = None

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['text'].append(data)

    def handle_entityref(self, name):
        raise AssertionError('convert_charrefs should be on')


def read_source(path):
    p = Source()
    p.feed(path.read_text())
    p.close()
    return p


def main():
    spec = load('case_spec_q.json')
    truth = load('truth_q.json')
    manifest = load('manifest_q.json')
    agreements = {a['borrower_id']: a for a in load('reference/agreements.json')}
    categories = load('reference/categories.json')
    prior = {k: load(f'reference/prior_cures_q{k}.json') for k in range(1, 5)}
    certs = {c['cert_id']: c for c in spec['certificates']}

    # ---- reference files: no labels, faithful to the spec
    if load('reference/agreements.json') != spec['agreements']:
        fail('G2', 'reference/agreements.json differs from the spec agreements list')
    if categories != spec['categories']:
        fail('G2', 'reference/categories.json differs from the spec categories')
    label_keys = set(LABELS) | {'realized', 'certified', 'category_true', 'ratio_agreement', 'due_date'}
    for k, rows in prior.items():
        for r in rows:
            if set(r) != {'borrower_id', 'quarter_label', 'amount'}:
                fail('G2', f'prior_cures_q{k}: unexpected keys {sorted(r)}')
    for path in (ROOT/'reference').glob('*.json'):
        def walk(o):
            if isinstance(o, dict):
                for kk, v in o.items():
                    if kk in label_keys:
                        fail('G2', f'{path.name} contains label key {kk}')
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(path.read_text()))
    history = [p for p in spec['prior_cures'] if p['quarter_label'] < '2025']
    for k in range(1, 5):
        exp = history+[dict(borrower_id=c['borrower_id'], quarter_label=f'2025-Q{c["quarter"]}', amount=c['cure']['amount'])
                       for c in sorted(spec['certificates'], key=lambda c: (c['quarter'], c['borrower_id'])) if c['quarter'] < k and c['cure']]
        if prior[k] != exp:
            fail('G2', f'prior_cures_q{k}.json is not history + cures printed before Q{k}')
    spec_2025 = sorted((p['borrower_id'], p['quarter_label'], p['amount']) for p in spec['prior_cures'] if p['quarter_label'] >= '2025')
    printed_2025 = sorted((c['borrower_id'], f'2025-Q{c["quarter"]}', c['cure']['amount']) for c in spec['certificates'] if c['cure'])
    if spec_2025 != printed_2025:
        notes.append('NOTE: spec prior_cures 2025 entries differ from printed cures; reference files follow the printed cures')

    # ---- sources: printed values
    src = {}
    for m in manifest['certificates']:
        src[m['cert_id']] = read_source(ROOT/m['source'])
    if set(src) != set(certs):
        fail('G2', 'manifest certificates differ from the spec')

    units_by_cert = defaultdict(list)
    for u in truth['units']:
        units_by_cert[u['cert_id']].append(u)

    # ---- G2: every unit has every field and label
    spec_units = [u for c in spec['certificates'] for u in c['units']]
    if truth['units'] != spec_units:
        fail('G2', 'truth_q.json units differ from the spec units')
    for u in truth['units']:
        kind = u.get('covenant') if u.get('unit_type') == 'covenant' else u.get('unit_type')
        if kind not in FIELDS:
            fail('G2', f'{u.get("cert_id")}/{u.get("unit_id")}: unknown unit type {u.get("unit_type")}')
            continue
        want = set(COMMON+FIELDS[kind]+LABELS)
        if set(u) != want:
            fail('G2', f'{u["cert_id"]}/{u["unit_id"]}: missing {sorted(want-set(u))} extra {sorted(set(u)-want)}')
        for key, allowed in ENUMS.items():
            if key in u and u[key] not in allowed:
                fail('G2', f'{u["cert_id"]}/{u["unit_id"]}: {key}={u[key]!r}')
        if 'category_true' in u and u['category_true'] not in categories:
            fail('G2', f'{u["cert_id"]}/{u["unit_id"]}: category_true {u["category_true"]!r}')
        for key in list(want):
            if u.get(key) in (None, ''):
                fail('G2', f'{u["cert_id"]}/{u["unit_id"]}: empty {key}')
    for cid, c in certs.items():
        us = units_by_cert[cid]
        ids = [u['unit_id'] for u in us]
        exp = [f'A{a["addback_no"]}' for a in c['addbacks']]+['LEV', 'ICR', 'DELIVERY', 'SIGNER']+(['CURE'] if c['cure'] else [])
        if sorted(ids) != sorted(exp) or len(set(ids)) != len(ids):
            fail('G2', f'{cid}: unit ids {ids} expected {exp}')
        for u in us:
            if (u['quarter'], u['borrower_id']) != (c['quarter'], c['borrower_id']):
                fail('G2', f'{cid}/{u["unit_id"]}: quarter/borrower mismatch')

    # ---- per-certificate: printed values, G3 recompute, G4 arithmetic, G7 dates
    for cid, c in certs.items():
        s = src[cid]
        k = c['quarter']
        ag = agreements[c['borrower_id']]
        us = {u['unit_id']: u for u in units_by_cert[cid]}
        F = s.fields
        q_end = parse_date(QUARTER_END[k])
        try:
            e = {key: money(F[key]) for key in ('net_income', 'interest_expense', 'income_taxes', 'd_and_a', 'unadjusted')}
            adds = [dict(no=int(r['addback_no']), description=r['description'], category_printed=r['category_printed'],
                         amount=money(r['amount']), action_date=r['action_date']) for r in s.addbacks]
            cure = (money(F['cure_amount']), F['cure_date']) if 'cure_amount' in F else None
            adj = money(F['adjusted_ebitda_printed'])
            cov = {n: dict(input=money(r['input']), ebitda=money(r['adjusted_ebitda']), ratio=ratio(r['ratio_printed']),
                           threshold=ratio(r['threshold_printed']), status=r['status_printed'].lower()) for n, r in s.covenants.items()}
        except (KeyError, ValueError) as ex:
            fail('G3', f'{cid}: cannot read printed values: {ex}')
            continue
        cert_text = F.get('certification')
        named = []
        if cert_text:
            m = re.search(r'Addback Nos?\. ((?:\d+)(?:(?:, | and )\d+)*)', cert_text)
            named = [int(x) for x in re.findall(r'\d+', m.group(1))] if m else []
            if not m:
                fail('G3', f'{cid}: certification paragraph names no addback number')

        # printed values agree with the truth fields
        for a in adds:
            u = us.get(f'A{a["no"]}')
            if not u:
                continue
            for key, val in (('addback_no', a['no']), ('description', a['description']), ('amount', a['amount']),
                             ('action_date', a['action_date']), ('category_printed', a['category_printed'])):
                if u[key] != val:
                    fail('G2', f'{cid}/A{a["no"]}: {key} truth {u[key]!r} printed {val!r}')
        for n, uid, inkey in (('leverage', 'LEV', 'total_debt'), ('interest_coverage', 'ICR', 'cash_interest')):
            u, r = us.get(uid), cov.get(n)
            if not u or not r:
                fail('G2', f'{cid}: covenant {n} missing')
                continue
            for key, val in ((inkey, r['input']), ('adjusted_ebitda', r['ebitda']), ('ratio_printed', r['ratio']),
                             ('threshold_printed', r['threshold']), ('status_printed', r['status'])):
                if (Decimal(str(u[key])) if isinstance(val, Decimal) else u[key]) != val:
                    fail('G2', f'{cid}/{uid}: {key} truth {u[key]!r} printed {val!r}')
        for uid, key, val in (('DELIVERY', 'delivery_date', F.get('delivery_date')), ('SIGNER', 'signer_name', F.get('signer_name')),
                              ('SIGNER', 'signer_title', F.get('signer_title'))):
            if us.get(uid, {}).get(key) != val:
                fail('G2', f'{cid}/{uid}: {key} truth {us.get(uid, {}).get(key)!r} printed {val!r}')
        if cure and (us.get('CURE', {}).get('cure_amount'), us.get('CURE', {}).get('cure_date')) != cure:
            fail('G2', f'{cid}/CURE: truth differs from printed {cure}')
        if F.get('borrower') != ag['borrower'] or F.get('agreement_date') != ag['agreement_date'] or F.get('bank') != spec['bank']['name']:
            fail('G2', f'{cid}: header borrower/agreement/bank mismatch')

        # G4: arithmetic
        if e['unadjusted'] != e['net_income']+e['interest_expense']+e['income_taxes']+e['d_and_a']:
            fail('G4', f'{cid}: unadjusted EBITDA {e["unadjusted"]} is not the sum of its four lines')
        if adj != e['unadjusted']+sum(a['amount'] for a in adds)+(cure[0] if cure else 0):
            fail('G4', f'{cid}: adjusted EBITDA {adj} != unadjusted + addbacks + cure')
        for n, r in cov.items():
            if r['ebitda'] != adj:
                fail('G4', f'{cid}/{n}: covenant adjusted EBITDA {r["ebitda"]} != {adj}')
            implied = d2(Decimal(r['input'])/r['ebitda']) if n == 'leverage' else d2(Decimal(r['ebitda'])/r['input'])
            uid = 'LEV' if n == 'leverage' else 'ICR'
            if us.get(uid, {}).get('error_class') != 'ratio_arithmetic' and implied != r['ratio']:
                fail('G4', f'{cid}/{uid}: printed ratio {r["ratio"]} != inputs ratio {implied}')

        # G7: dates
        for label, val in [('agreement_date', F.get('agreement_date')), ('delivery_date', F.get('delivery_date')),
                           ('signature_date', F.get('signature_date')), ('quarter_end', F.get('quarter_end'))] + \
                          [(f'A{a["no"]} action_date', a['action_date']) for a in adds] + ([('cure_date', cure[1])] if cure else []):
            if parse_date(val) is None:
                fail('G7', f'{cid}: invalid {label} {val!r}')
        dd = parse_date(F.get('delivery_date'))
        if F.get('quarter_end') != QUARTER_END[k]:
            fail('G7', f'{cid}: printed quarter end {F.get("quarter_end")} is not {QUARTER_END[k]}')
        if dd and not dd > q_end:
            fail('G7', f'{cid}: delivery {dd} not after quarter end {q_end}')
        if F.get('signature_date') != F.get('delivery_date'):
            fail('G7', f'{cid}: signature date {F.get("signature_date")} != delivery date')
        if parse_date(F.get('agreement_date')) and dd and parse_date(F['agreement_date']) >= q_end:
            fail('G7', f'{cid}: agreement date not before quarter end')

        # G3: recompute labels
        unadj = e['net_income']+e['interest_expense']+e['income_taxes']+e['d_and_a']
        cap = Decimal(str(ag['cost_savings_cap_pct']))*unadj
        window_start = months_before(q_end, ag['cost_savings_window_months'])
        seen, bucket, over, permitted_sum = set(), Decimal(0), False, 0
        exp = {}
        for a in adds:
            u = us.get(f'A{a["no"]}')
            if not u:
                continue
            cs = u['category_true'] == 'cost_savings'
            certified = ('yes' if a['no'] in named else 'no') if cs else 'n_a'
            if u['certified'] != certified:
                fail('G3', f'{cid}/A{a["no"]}: certified {u["certified"]} expected {certified}')
            ec = 'none'
            key = (a['amount'], a['action_date'])
            if key in seen:
                ec = 'duplicate_addback'
            elif u['category_true'] not in ag['permitted_categories']:
                ec = 'category_not_permitted'
            elif cs and certified != 'yes':
                ec = 'certification_missing'
            elif cs and u['realized'] == 'projected' and parse_date(a['action_date']) < window_start:
                ec = 'window_expired'
            elif cs:
                if over or bucket+a['amount'] > cap:
                    over, ec = True, 'cap_exceeded'
                else:
                    bucket += a['amount']
            seen.add(key)
            if ec == 'none':
                permitted_sum += a['amount']
            exp[f'A{a["no"]}'] = dict(error_class=ec, breach='no')
        valid_cure = 0
        if cure:
            mine = [p for p in prior[k] if p['borrower_id'] == c['borrower_id']]
            prev = f'2024-Q4' if k == 1 else f'2025-Q{k-1}'
            count_ok = len(mine)+1 <= ag['cure_max']
            consec_ok = not (ag['cure_no_consecutive'] and any(p['quarter_label'] == prev for p in mine))
            exp['CURE'] = dict(error_class='none' if count_ok and consec_ok else 'cure_invalid', breach='no')
            if count_ok and consec_ok:
                valid_cure = cure[0]
        agr_ebitda = unadj+permitted_sum+valid_cure
        for n, uid in (('leverage', 'LEV'), ('interest_coverage', 'ICR')):
            r, u = cov[n], us.get(uid)
            if not u:
                continue
            if n == 'leverage':
                ra = d2(Decimal(r['input'])/agr_ebitda)
                breach = ra > Decimal(str(ag['max_leverage']))
                raw = Decimal(r['input'])/r['ebitda']
            else:
                ra = d2(Decimal(agr_ebitda)/r['input'])
                breach = ra < Decimal(str(ag['min_interest_coverage']))
                raw = Decimal(r['ebitda'])/r['input']
            if Decimal(str(u['ratio_agreement'])) != ra:
                fail('G3', f'{cid}/{uid}: ratio_agreement {u["ratio_agreement"]} expected {ra}')
            arith = abs(r['ratio']-d2(raw)) > Decimal('.01')
            if arith != (abs(r['ratio']-raw) > Decimal('.01')):
                notes.append(f'NOTE: {cid}/{uid}: ratio_arithmetic depends on rounding the inputs ratio ({raw:.4f} vs {r["ratio"]})')
            if r['status'] == 'pass' and breach:
                ec = 'hidden_breach'
            elif arith:
                ec = 'ratio_arithmetic'
            else:
                ec = 'none'
            if r['status'] == 'fail' and not breach:
                fail('G3', f'{cid}/{uid}: status Fail printed but no agreement breach (undefined case)')
            exp[uid] = dict(error_class=ec, breach='yes' if breach else 'no')
        due = q_end+timedelta(days=ag['delivery_days_q4'] if k == 4 else ag['delivery_days'])
        if us.get('DELIVERY', {}).get('due_date') != due.isoformat():
            fail('G3', f'{cid}/DELIVERY: due_date {us.get("DELIVERY", {}).get("due_date")} expected {due}')
        exp['DELIVERY'] = dict(error_class='late_delivery' if dd and dd > due else 'none', breach='no')
        officer = norm_title(F.get('signer_title', '')) in {norm_title(t) for t in ag['responsible_officer_titles']}
        exp['SIGNER'] = dict(error_class='none' if officer else 'signer_not_officer', breach='no')
        for uid, x in exp.items():
            hold = x['error_class'] != 'none' or x['breach'] == 'yes'
            x['disposition'] = 'hold' if hold else 'post'
            if not hold:
                x['owner'] = 'none'
            elif (uid in ('LEV', 'ICR') and x['breach'] == 'yes') or x['error_class'] in ('cure_invalid', 'late_delivery'):
                x['owner'] = 'required_lenders'
            elif uid.startswith('A'):
                x['owner'] = 'credit_officer'
            elif x['error_class'] in ('ratio_arithmetic', 'signer_not_officer'):
                x['owner'] = 'analyst'
            else:
                x['owner'] = 'UNDEFINED'
            u = us.get(uid)
            if u is None:
                continue
            for lab in LABELS:
                if u[lab] != x[lab]:
                    fail('G3', f'{cid}/{uid}: {lab} {u[lab]} expected {x[lab]}')
        if (c['statement_4'] == 'defaults_listed') != (F.get('statement_4') == 'defaults_listed'):
            fail('G2', f'{cid}: statement 4 not printed as specified')

    # ---- G1: quotas, recounted from labels
    def g1(k, msg):
        fail('G1', f'Q{k}: {msg}')
    recount_all = {}
    for k in range(1, 5):
        kc = [c for c in spec['certificates'] if c['quarter'] == k]
        ku = [u for u in truth['units'] if u['quarter'] == k]
        cls = Counter(u['error_class'] for u in ku)
        for name in CLASSES:
            want = 4 if name == 'cap_exceeded' else 2
            if cls[name] != want:
                g1(k, f'{name} = {cls[name]}, want {want}')
        cap_units = [u for u in ku if u['error_class'] == 'cap_exceeded']
        if len({u['cert_id'] for u in cap_units}) != 4:
            g1(k, 'cap_exceeded is not in 4 different certificates')
        per_cert = Counter(u['cert_id'] for u in ku if u['error_class'] != 'none')
        if per_cert and max(per_cert.values()) > 3:
            g1(k, f'a borrower carries more than 3 errors: {per_cert.most_common(1)}')
        if len({c['borrower_id'] for c in kc}) != len(kc):
            g1(k, 'a borrower has more than one certificate')
        # hidden_breach mechanisms
        mech = Counter()
        for u in ku:
            if u['error_class'] != 'hidden_breach':
                continue
            ag = agreements[u['borrower_id']]
            agr_t = Decimal(str(ag['max_leverage'] if u['covenant'] == 'leverage' else ag['min_interest_coverage']))
            pt = Decimal(str(u['threshold_printed']))
            looser = pt > agr_t if u['covenant'] == 'leverage' else pt < agr_t
            pr = Decimal(str(u['ratio_printed']))
            passes_agr_on_printed = pr <= agr_t if u['covenant'] == 'leverage' else pr >= agr_t
            add_err = [x for x in units_by_cert[u['cert_id']] if x['unit_type'] == 'addback' and x['error_class'] != 'none']
            if looser and pt != agr_t:
                mech['threshold'] += 1
            elif pt == agr_t and add_err and passes_agr_on_printed:
                mech['addbacks'] += 1
            else:
                mech['other'] += 1
        if mech != Counter(threshold=1, addbacks=1):
            g1(k, f'hidden_breach mechanisms {dict(mech)}, want one threshold and one addbacks')
        # cure_invalid mechanisms
        cm = Counter()
        for u in ku:
            if u['error_class'] != 'cure_invalid':
                continue
            ag = agreements[u['borrower_id']]
            mine = [p for p in prior[k] if p['borrower_id'] == u['borrower_id']]
            prev = '2024-Q4' if k == 1 else f'2025-Q{k-1}'
            count_bad = len(mine)+1 > ag['cure_max']
            consec_bad = any(p['quarter_label'] == prev for p in mine)
            cm['count' if count_bad and not consec_bad else 'consecutive' if consec_bad and not count_bad else 'both']+=1
        if cm != Counter(count=1, consecutive=1):
            g1(k, f'cure_invalid mechanisms {dict(cm)}, want one count and one consecutive')
        # benign cases
        honest = {u['cert_id'] for u in ku if u['unit_type'] == 'covenant' and u['breach'] == 'yes' and u['error_class'] == 'none'
                  and u['status_printed'] == 'fail' and certs[u['cert_id']]['statement_4'] == 'defaults_listed'}
        valid_cure = [u for u in ku if u['unit_type'] == 'cure' and u['error_class'] == 'none']
        cure_claimed = [u for u in ku if u['unit_type'] == 'cure']
        realized_old = []
        for u in ku:
            if u['unit_type'] == 'addback' and u['category_true'] == 'cost_savings' and u['realized'] == 'realized' and u['error_class'] == 'none':
                ag = agreements[u['borrower_id']]
                if parse_date(u['action_date']) < months_before(parse_date(QUARTER_END[k]), ag['cost_savings_window_months']):
                    realized_old.append(u)
        pairs = 0
        for c in kc:
            ab = [u for u in units_by_cert[c['cert_id']] if u['unit_type'] == 'addback']
            for i, x in enumerate(ab):
                for y in ab[i+1:]:
                    if x['amount'] == y['amount'] and x['action_date'] != y['action_date'] and 'duplicate_addback' not in (x['error_class'], y['error_class']):
                        pairs += 1
        approval = [u for u in ku if u['unit_type'] == 'addback' and u['error_class'] == 'none'
                    and (APPROVAL.search(u['description']) or APPROVAL.search(u['category_printed']))]
        abbrev = [u for u in ku if u['unit_type'] == 'signer' and u['error_class'] == 'none'
                  and u['signer_title'] not in agreements[u['borrower_id']]['responsible_officer_titles']]
        certs_cert = [c for c in kc if src[c['cert_id']].fields.get('certification')]
        n_add = [len(src[c['cert_id']].addbacks) for c in kc]
        counts = dict(honest_breach=len(honest), valid_equity_cure=len(valid_cure), realized_savings_outside_window=len(realized_old),
                      same_amount_pair=pairs, permitted_approval_or_one_time=len(approval), signer_title_abbreviated=len(abbrev))
        for name, n in counts.items():
            if n != 1:
                g1(k, f'{name} = {n}, want 1')
        if not all(2 <= n <= 6 for n in n_add):
            g1(k, f'addback lines per certificate out of 2-6: {n_add}')
        if not 3.5 <= sum(n_add)/len(n_add) <= 4.5:
            g1(k, f'average addback lines {sum(n_add)/len(n_add):.2f} is not about 4')
        if len(certs_cert) < 3:
            g1(k, f'only {len(certs_cert)} certificates with a certification paragraph')
        if not 3 <= len(cure_claimed) <= 4:
            g1(k, f'{len(cure_claimed)} equity cures claimed, want 3-4')
        # stress amendment: every cap line is dependent on valid anchors
        for u in cap_units:
            c = certs[u['cert_id']]
            ag = agreements[u['borrower_id']]
            e = c['ebitda']
            cap = Decimal(str(ag['cost_savings_cap_pct']))*(e['net_income']+e['interest_expense']+e['income_taxes']+e['d_and_a'])
            ab = sorted([x for x in units_by_cert[u['cert_id']] if x['unit_type'] == 'addback'], key=lambda x: x['addback_no'])
            if u['amount'] > cap:
                g1(k, f'{u["cert_id"]}/{u["unit_id"]}: cap line amount exceeds the cap on its own')
            earlier_cap = [x for x in ab if x['addback_no'] < u['addback_no'] and x['error_class'] == 'cap_exceeded']
            if earlier_cap:
                continue
            anchors = [x for x in ab if x['addback_no'] < u['addback_no'] and x['category_true'] == 'cost_savings' and x['error_class'] == 'none']
            if not anchors:
                g1(k, f'{u["cert_id"]}/{u["unit_id"]}: cap line has no anchor line')
            run = Decimal(0)
            for x in anchors:
                run += x['amount']
                if x['certified'] != 'yes' or run > cap:
                    g1(k, f'{u["cert_id"]}/{x["unit_id"]}: anchor not certified or bucket over cap after it')
                if parse_date(x['action_date']) < months_before(parse_date(QUARTER_END[k]), 12):
                    g1(k, f'{u["cert_id"]}/{x["unit_id"]}: anchor action date more than 12 months before quarter end')
            if run+u['amount'] <= cap:
                g1(k, f'{u["cert_id"]}/{u["unit_id"]}: cap line does not take the bucket over the cap')
        recount = dict(cls)
        recount.pop('none', None)
        recount.update(counts, addback_lines=sum(n_add), certs_with_certification=len(certs_cert), equity_cure_claimed=len(cure_claimed))
        qc = spec['quota_check'][str(k)]
        for name, n in qc.items():
            if recount.get(name, 0) != n:
                g1(k, f'spec quota_check {name}={n} but recount {recount.get(name, 0)}')
        recount_all[k] = recount
    # reference quotas
    ags = list(agreements.values())
    if len(ags) != 12:
        fail('G1', f'{len(ags)} agreements, want 12')
    for a in ags:
        b = a['borrower_id']
        if not 3 <= a['max_leverage'] <= 5 or not 2 <= a['min_interest_coverage'] <= 3.5:
            fail('G1', f'{b}: thresholds out of range')
        if not set(a['permitted_categories']) <= set(categories) or 'ordinary_operating' in a['permitted_categories']:
            fail('G1', f'{b}: permitted_categories invalid')
        if a['cost_savings_cap_pct'] not in (0.15, 0.2) or a['cost_savings_window_months'] != 18:
            fail('G1', f'{b}: cost savings terms')
        if a['cure_max'] != 4 or a['cure_no_consecutive'] is not True or a['delivery_days'] != 45 or a['delivery_days_q4'] != 90:
            fail('G1', f'{b}: cure/delivery terms')
        if not 3 <= len(a['responsible_officer_titles']) <= 5 or not 3 <= len(a['commitments']) <= 5:
            fail('G1', f'{b}: titles or commitments count')
    if sum('transaction_costs' not in a['permitted_categories'] for a in ags) < 3:
        fail('G1', 'fewer than 3 agreements exclude transaction_costs')
    if set(categories) != {'restructuring_charges', 'transaction_costs', 'non_cash_compensation', 'cost_savings', 'non_recurring_losses', 'ordinary_operating'}:
        fail('G1', 'categories.json codes')
    hist_b = {p['borrower_id'] for p in prior[1] if p['quarter_label'][:4] in ('2023', '2024')}
    if not 2 <= len(hist_b) <= 3:
        fail('G1', f'2023-2024 cure history covers {len(hist_b)} borrowers, want 2-3')

    # ---- G6 (sources): heading order in every source
    for cid, s in src.items():
        if s.headings != HEADINGS:
            fail('G6', f'{cid}: source headings {s.headings}')

    # ---- G5 / G6 on rendered PDFs
    pdfs = list((ROOT/'clean').glob('*.pdf'))
    skipped = []
    if not pdfs:
        skipped = ['G5', 'G6']
        print('SKIP G5, G6 (rendered-PDF checks): clean/ is empty. Run build_q.py --render-only, then re-run check_q.py.')
    elif not shutil.which('pdftotext'):
        fail('G5', 'pdftotext not found')
    else:
        def text_of(pdf, *flags):
            t = subprocess.run(['pdftotext', *flags, str(pdf), '-'], capture_output=True, text=True, check=True).stdout
            t = unicodedata.normalize('NFKC', t).replace('­', '')
            t = re.sub(r'(?<=\w)-[ \t]*\n\s*(?=\w)', '-', t)
            return re.sub(r'\s+', ' ', t)
        def norm(x):
            return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', x)).strip()
        for cid, c in certs.items():
            pdf = ROOT/'clean'/f'{cid}.pdf'
            if not pdf.exists():
                fail('G5', f'{cid}: clean/{cid}.pdf missing')
                continue
            texts = [text_of(pdf), text_of(pdf, '-raw')]
            want = [('description', a['description']) for a in c['addbacks']]+[('signer title', c['signer_title'])]
            if c['certification']['present']:
                want.append(('certification', 'Officer certification of cost savings: '+c['certification']['text']))
            for what, val in want:
                if not any(norm(val) in t for t in texts):
                    fail('G5', f'{cid}: {what} not found in PDF text: {val[:60]!r}')
            pos, t = 0, texts[0]
            for h in HEADINGS:
                i = t.find(h, pos)
                if i < 0:
                    fail('G6', f'{cid}: heading {h!r} missing or out of order in PDF')
                    break
                pos = i+len(h)
            info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
            m = re.search(r'Pages:\s+(\d+)', info)
            if not m or not 1 <= int(m.group(1)) <= 2:
                fail('G6', f'{cid}: page count {m.group(1) if m else "?"} not 1-2')
            if m and 'Page size' in info and not re.search(r'Page size:\s+612 x 792', info):
                fail('G6', f'{cid}: not US Letter portrait')

    for n in notes:
        print(n)
    for g in ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7']:
        if g in skipped and not failures[g]:
            print(f'{g}: SKIPPED (clean/ is empty)')
        elif failures[g]:
            print(f'{g}: FAIL ({len(failures[g])})')
            for msg in failures[g][:40]:
                print(f'  - {msg}')
        else:
            print(f'{g}: PASS')
    print(f'Certificates: {len(certs)}; units: {len(truth["units"])}')
    for k, r in recount_all.items():
        print(f'Q{k} recount: ' + ', '.join(f'{n}={r[n]}' for n in sorted(r)))
    sys.exit(1 if any(failures.values()) else 0)


if __name__ == '__main__':
    main()
