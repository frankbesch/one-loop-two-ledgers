"""Step 6 code layer (flow steps 0, 5, 6, 8, 11): reference in force by date, format-aware AFE reading,
exact linking, the six money rules, the hold/post policy, and dollars at stake. No model is called here.

Job B's code layer (`jobb/codelayer.py`) is frozen for job B and is reused unchanged for the claim rows (Q16).
"""
import calendar, datetime as dt, re, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jobb'))
import codelayer as C  # noqa: E402

MONEY = ['wrong_decimal', 'wrong_rate', 'nonconsent_property', 'afe_overrun', 'duplicate', 'date_window']


def day(s):
    try:
        return dt.date.fromisoformat((s or '').strip())
    except ValueError:
        return None


def in_force(rows, key, val, when, date_field='effective'):
    c = [r for r in rows if r[key] == val and day(r[date_field]) and day(r[date_field]) <= when]
    return max(c, key=lambda r: day(r[date_field])) if c else None


def month_end(period):
    y, m = map(int, period.split('-'))
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def cents(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), ROUND_HALF_UP)


# ------------------------------------------------------------------ AFE numbers per saved format (step 5)

def afe_regex(display):
    """A tolerant regex from a format's display, e.g. 'BX:{serial:04d}:K' or 'K[{serial:05d}]/BX': literal
    letters kept, punctuation and spacing between parts flexible, the serial captured without its zero padding."""
    parts = re.split(r'(\{serial[^}]*\})', display)
    out = []
    for p in parts:
        if p.startswith('{serial'):
            out.append(r'0*(?P<serial>\d+)')
        else:
            for chunk in re.findall(r'[A-Za-z0-9]+|[^A-Za-z0-9]+', p):
                out.append(re.escape(chunk) if chunk.isalnum() else r'[^A-Za-z0-9]{0,6}')
    body = ''.join(out).replace(r'[^A-Za-z0-9]{0,6}[^A-Za-z0-9]{0,6}', r'[^A-Za-z0-9]{0,6}')
    return re.compile(r'(?<![A-Za-z0-9])' + body + r'(?![A-Za-z0-9])', re.I)


class Register:
    """The owner's AFE register, read through every known format's display pattern."""

    def __init__(self, register, formats):
        self.rows = register
        self.pats = {fid: afe_regex(f['afe_display']) for fid, f in formats.items()}
        base = next(iter(formats.values()))['afe_display']
        self.base = afe_regex(base)
        self.by_serial = {}
        for r in register:
            m = self.base.search(r['afe_number'])
            if m:
                self.by_serial.setdefault(int(m.group('serial')), []).append(r)

    def find(self, text):
        """[(token as printed, register row or None)] for every AFE-shaped token in a known format."""
        out, spans = [], []
        for fid, pat in self.pats.items():
            for m in pat.finditer(text or ''):
                if any(a < m.end() and m.start() < b for a, b in spans):
                    continue
                spans.append((m.start(), m.end()))
                rows = self.by_serial.get(int(m.group('serial')), [])
                out.append((m.group(0), rows[0] if len(rows) == 1 else None))
        return out

    def lookup(self, token):
        """Q10 for step 6: (status, row, kind). kind is exact when printed as the register prints it."""
        for pat in self.pats.values():
            m = pat.fullmatch(token.strip())
            if m:
                rows = self.by_serial.get(int(m.group('serial')), [])
                if len(rows) > 1:
                    return 'ambiguous', None, None
                if not rows:
                    return 'not_found', None, None
                r = rows[0]
                return r['status'], r, ('exact' if r['afe_number'] == token.strip() else 'reformatted')
        return 'not_found', None, None

    def candidates(self, text):
        """Q9 options: AFE-shaped tokens in a known format first, then any other number-like token."""
        found = [t for t, _ in self.find(text)]
        rest = [t for t in C.tokens(text) if not any(t in f or f in t for f in found)]
        return found + rest


# ------------------------------------------------------------------ linking (step 5), exact first

def norm_name(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def link_exact(printed, properties):
    for p in properties:
        if norm_name(printed) in (norm_name(p['property_no']), norm_name(p['name'])):
            return p['property_no']
    return None


# ------------------------------------------------------------------ money rules (step 6)

class Money:
    """Runs the six rules in billing order; keeps the ledger state (cumulative AFE totals, invoices seen)."""

    def __init__(self, ref, register, prior=None):
        self.ref, self.reg = ref, register
        self.tol = Decimal(str(ref['joa_terms']['afe_overrun_tolerance']))
        self.window = int(ref['joa_terms']['exception_window_months'])
        self.cum = dict((prior or {}).get('cum', {}))
        self.seen = set(tuple(x) for x in (prior or {}).get('seen', []))

    def state(self):
        return {'cum': {k: str(v) for k, v in self.cum.items()}, 'seen': sorted(self.seen)}

    def check(self, u, prop, period):
        """-> ([rule, ...], dollars at stake, notes). Fails closed: missing inputs give 'needs_review'."""
        fired, notes = [], []
        sd = day(u['service_date'])
        if sd is None or u['gross'] is None or u['owner_decimal'] is None:
            return ['needs_review'], 0.0, ['unreadable amount or date']
        net = Decimal(str(u['net_amount'] or 0))
        stake = Decimal(0)
        if prop is None:
            fired.append('needs_review'); notes.append('property not linked')
        else:
            doi = in_force(self.ref['doi'], 'property_no', prop, sd)
            if doi is None:
                fired.append('needs_review'); notes.append('no division order in force')
            elif abs(Decimal(str(doi['owner_decimal'])) - Decimal(str(u['owner_decimal']))) > Decimal('0.0000005'):
                fired.append('wrong_decimal')
                stake = max(stake, net - cents(Decimal(str(u['gross'])) * Decimal(str(doi['owner_decimal']))))
            el = in_force(self.ref['elections'], 'property_no', prop, sd)
            if el and el['election'] == 'nonconsent':
                fired.append('nonconsent_property'); stake = max(stake, net)
        if u['unit_rate'] is not None:
            rates = [r for r in self.ref['contract_rates'] if r['vendor'] == u['vendor'] and day(r['effective']) <= sd]
            named = [r for r in rates if r['service'].lower() in (u['description'] or '').lower()] or rates
            latest = {}
            for r in named:
                if r['service'] not in latest or day(r['effective']) > day(latest[r['service']]['effective']):
                    latest[r['service']] = r
            if not latest:
                fired.append('needs_review'); notes.append('no contract rate in force')
            elif all(abs(Decimal(str(r['rate'])) - Decimal(str(u['unit_rate']))) > Decimal('0.005') for r in latest.values()):
                fired.append('wrong_rate')
                best = min(latest.values(), key=lambda r: abs(Decimal(str(r['rate'])) - Decimal(str(u['unit_rate']))))
                stake = max(stake, (Decimal(str(u['unit_rate'])) - Decimal(str(best['rate']))) * Decimal(str(u['quantity'] or 0)) * Decimal(str(u['owner_decimal'])))
        coded = [r for _, r in self.reg.find(' '.join([u['reference'] or '', u['description'] or ''] + [x['text'] for x in u['remarks']])) if r]
        if coded and coded[0]['status'] == 'approved':
            a = coded[0]['afe_number']
            self.cum[a] = Decimal(str(self.cum.get(a, 0))) + Decimal(str(u['gross']))
            if self.cum[a] > Decimal(str(coded[0]['approved_amount'])) * (1 + self.tol):
                fired.append('afe_overrun'); stake = max(stake, net)
        key = (u['vendor'], u['invoice_no'], str(cents(u['gross'])))
        if key in self.seen:
            fired.append('duplicate'); stake = max(stake, net)
        self.seen.add(key)
        end = month_end(period)
        y, m = end.year, end.month - self.window
        while m <= 0:
            y, m = y - 1, m + 12
        if sd > end or sd < dt.date(y, m, min(end.day, calendar.monthrange(y, m)[1])):
            fired.append('date_window'); stake = max(stake, net)
        return fired, float(stake), notes


# ------------------------------------------------------------------ policy (steps 8, 11)

CLAIM_HOLD = {'unsupported', 'contradicted', 'other_authority', C.NEEDS_REVIEW}


def disposition(money_fired, claim_outcome, link_review, q14):
    """hold when any money rule fires, the claim needs a person, linking is unclear, or the unit is incomplete."""
    reasons = [r for r in money_fired]
    if claim_outcome in CLAIM_HOLD:
        reasons.append('claim:' + claim_outcome)
    if link_review:
        reasons.append('link:needs_review')
    if q14 != 'complete':
        reasons.append('incomplete')
    return ('hold' if reasons else 'post'), reasons


# ------------------------------------------------------------------ claim outcome (job B rows, step 6 register)

def q16m(q14v, q17_fail, q2_answers, q7, q8v, q9, reg, prop):
    """Job B's Q16 rows, first match wins, with the AFE lookup read through the saved formats (Register)."""
    if q14v == 'incomplete':
        return C.NEEDS_REVIEW, 'incomplete_unit'
    if q17_fail:
        return C.NEEDS_REVIEW, 'evidence_check_failed'
    claim = C.combined_claim(q2_answers)
    if claim == C.NEEDS_REVIEW:
        return C.NEEDS_REVIEW, 'claim_unclear'
    if claim == 'no_claim' and q8v == 'placeholder':
        return C.NEEDS_REVIEW, 'code_model_conflict'
    if claim == 'no_claim':
        return 'no_claim', ''
    if claim == 'other_authority':
        return 'other_authority', 'q6'
    if q9 in (C.NEEDS_REVIEW, None):
        return C.NEEDS_REVIEW, 'reference_unclear'
    if q9 != 'none_of_these':
        status, row, kind = reg.lookup(q9)
        if status == 'ambiguous':
            return C.NEEDS_REVIEW, 'register_ambiguous'
        if status == 'declined':
            return 'contradicted', 'afe_declined'
        if status == 'not_found':
            return 'unsupported', 'unknown_number'
        if not prop:
            return C.NEEDS_REVIEW, 'property_unknown'
        if row['property_no'] != prop:
            return 'unsupported', 'afe_other_property'
        return 'supported', kind
    if q8v == 'placeholder' or q7 == 'placeholder':
        return 'unsupported', 'placeholder'
    if q7 == 'no_reference':
        return 'unsupported', 'no_number'
    return C.NEEDS_REVIEW, 'reference_conflict'
