"""Step 7 code layer (banking): the credit agreement's rules, applied to one compliance certificate.

Pure functions, no model call. Used twice:
  - by the independent spec check (check_spec_q.py), fed the key's true category, realized, and certified values,
    to confirm the Codex key follows from the printed values (the step 6 check_spec_m.py role);
  - by arm D (run_bank.py), fed the typed-question answers, to decide every unit.
Definitions: synth-bank rekey_fields_q.md (artifacts/one-loop-step7-2026-10-08/inputs), mirrored here line for line.
"""
import calendar, datetime as dt, itertools, re
from decimal import Decimal, ROUND_HALF_UP

QUARTER_END = {1: dt.date(2025, 3, 31), 2: dt.date(2025, 6, 30), 3: dt.date(2025, 9, 30), 4: dt.date(2025, 12, 31)}
NEEDS_REVIEW = 'needs_review'
ABBREV = {'cfo': 'chief financial officer', 'ceo': 'chief executive officer', 'coo': 'chief operating officer',
          'cao': 'chief accounting officer', 'evp': 'executive vice president', 'svp': 'senior vice president',
          'vp': 'vice president', 'treas.': 'treasurer'}


def day(s):
    return dt.date.fromisoformat(str(s).strip())


def r2(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def add_months(d, n):
    y, m = d.year, d.month + n
    while m <= 0:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def norm_title(t):
    t = re.sub(r'\s+', ' ', (t or '').strip().lower())
    for k, v in ABBREV.items():
        t = re.sub(rf'(?<![a-z]){re.escape(k)}(?![a-z])', v, t)
    return re.sub(r'[^a-z ]', '', t).strip()


def due_date(quarter, ag):
    return QUARTER_END[quarter] + dt.timedelta(days=ag['delivery_days_q4'] if quarter == 4 else ag['delivery_days'])


def cures_before(prior, borrower_id):
    return [c for c in prior if c['borrower_id'] == borrower_id]


def prev_quarter_label(quarter):
    return f'2025-Q{quarter - 1}' if quarter > 1 else '2024-Q4'


def addback_tests(addbacks, ag, quarter, unadjusted, judged):
    """judged[n] = {'category': code|needs_review, 'realized': realized|projected|needs_review, 'certified': yes|no|needs_review}.
    -> {n: (error_class or 'none' or 'needs_review', permitted_bool)} in definition order: duplicate, category,
    certification, window, cap."""
    out, seen, bucket = {}, set(), Decimal(0)
    cap = Decimal(str(ag['cost_savings_cap_pct'])) * Decimal(unadjusted)
    end = QUARTER_END[quarter]
    for a in sorted(addbacks, key=lambda a: a['addback_no']):
        n, j = a['addback_no'], judged[a['addback_no']]
        key = (int(a['amount']), str(a['action_date']))
        if key in seen:
            out[n] = ('duplicate_addback', False); continue
        seen.add(key)
        if j['category'] == NEEDS_REVIEW:
            out[n] = (NEEDS_REVIEW, False); continue
        if j['category'] not in ag['permitted_categories']:
            out[n] = ('category_not_permitted', False); continue
        if j['category'] == 'cost_savings':
            if j['certified'] == NEEDS_REVIEW or j['realized'] == NEEDS_REVIEW:
                out[n] = (NEEDS_REVIEW, False); continue
            if j['certified'] != 'yes':
                out[n] = ('certification_missing', False); continue
            if j['realized'] == 'projected' and day(a['action_date']) < add_months(end, -int(ag['cost_savings_window_months'])):
                out[n] = ('window_expired', False); continue
            if bucket + Decimal(int(a['amount'])) > cap:
                bucket = cap + 1                       # every later cost-savings line is over the cap too
                out[n] = ('cap_exceeded', False); continue
            bucket += Decimal(int(a['amount']))
        out[n] = ('none', True)
    return out


def cure_test(cure, quarter, ag, prior):
    if not cure:
        return None
    hist = cures_before(prior, ag['borrower_id'])
    if len(hist) + 1 > int(ag['cure_max']):
        return 'cure_invalid'
    if ag.get('cure_no_consecutive') and any(c['quarter_label'] == prev_quarter_label(quarter) for c in hist):
        return 'cure_invalid'
    return 'none'


def evaluate(cert, ag, prior, judged, owner_rule=True):
    """cert: the printed values (quarter, cert_id, borrower_id, delivery_date, signer_title, ebitda.unadjusted, addbacks,
    cure, adjusted_ebitda_printed, covenants). judged: per addback answers (see addback_tests).
    -> {unit_id: {'error_class', 'breach', 'disposition', 'owner', ...}}; error_class needs_review means hold for review."""
    q, unadj = cert['quarter'], int(cert['ebitda']['unadjusted'])
    ab = addback_tests(cert['addbacks'], ag, q, unadj, judged)
    permitted = sum(int(a['amount']) for a in cert['addbacks'] if ab[a['addback_no']][1])
    cure_cls = cure_test(cert.get('cure'), q, ag, prior)
    cure_amt = int(cert['cure']['amount']) if cert.get('cure') and cure_cls == 'none' else 0
    agree_ebitda = unadj + permitted + cure_amt
    any_review = any(v[0] == NEEDS_REVIEW for v in ab.values())
    units = {}
    for a in cert['addbacks']:
        cls = ab[a['addback_no']][0]
        units[f"A{a['addback_no']}"] = dict(unit_type='addback', error_class=cls, breach='no')
    for c in cert['covenants']:
        uid = 'LEV' if c['covenant'] == 'leverage' else 'ICR'
        adj = int(cert['adjusted_ebitda_printed'])
        if c['covenant'] == 'leverage':
            printed_calc = r2(Decimal(int(c['input'])) / Decimal(adj)) if adj else None
            agree = r2(Decimal(int(c['input'])) / Decimal(agree_ebitda)) if agree_ebitda > 0 else Decimal('999')
            breach = agree > r2(ag['max_leverage'])
        else:
            printed_calc = r2(Decimal(adj) / Decimal(int(c['input'])))
            agree = r2(Decimal(agree_ebitda) / Decimal(int(c['input'])))
            breach = agree < r2(ag['min_interest_coverage'])
        arith = printed_calc is None or abs(printed_calc - r2(c['ratio_printed'])) > Decimal('0.01')
        if breach and c['status_printed'] == 'pass':
            cls = 'hidden_breach'
        elif arith:
            cls = 'ratio_arithmetic'
        else:
            cls = 'none'
        units[uid] = dict(unit_type='covenant', error_class=cls, breach='yes' if breach else 'no', ratio_agreement=float(agree),
                          depends_on_review=any_review)
    units['DELIVERY'] = dict(unit_type='delivery', breach='no',
                             error_class='late_delivery' if day(cert['delivery_date']) > due_date(q, ag) else 'none')
    titles = {norm_title(t) for t in ag['responsible_officer_titles']}
    units['SIGNER'] = dict(unit_type='signer', breach='no',
                           error_class='none' if norm_title(cert['signer_title']) in titles else 'signer_not_officer')
    if cure_cls is not None:
        units['CURE'] = dict(unit_type='cure', breach='no', error_class=cure_cls)
    for uid, u in units.items():
        hold = u['error_class'] != 'none' or u['breach'] == 'yes'
        u['disposition'] = 'hold' if hold else 'post'
        u['owner'] = owner(u) if owner_rule else None
    return units, dict(agreement_ebitda=agree_ebitda, permitted_addbacks=permitted, cure_counted=cure_amt)


def resolutions(j, categories, weak=()):
    """Every answer set a person could give for one addback's doubted questions (the closed option lists).
    A doubted category opens every category, and for cost savings both realized values and both certified values.
    weak (floor lock, 16-floor-lock-preregistration.md): fields accepted under a learned floor but below the locked
    floor; they open like doubted fields when other units are tested."""
    nr_c = j['category'] == NEEDS_REVIEW or 'category' in weak
    out = []
    for c in (list(categories) if nr_c else [j['category']]):
        if c != 'cost_savings':
            out.append(dict(category=c, realized='n_a', certified='n_a')); continue
        rs = ['realized', 'projected'] if nr_c or j['realized'] == NEEDS_REVIEW or 'realized' in weak else [j['realized']]
        xs = ['yes', 'no'] if nr_c or j['certified'] == NEEDS_REVIEW or 'certified' in weak else [j['certified']]
        out += [dict(category=c, realized=r, certified=x) for r in rs for x in xs]
    return out


def evaluate_invariant(cert, ag, prior, judged, categories, weak=None):
    """The decision-invariance rule (pre-registered in publishing one-loop-two-ledgers/13-capfix-preregistration.md):
    post a unit only when it posts under every way the doubted answers could resolve. A unit that holds under any
    resolution is held for review. This replaces the step 7 covenant guard, which could not fire (its stand-in answer,
    ordinary_operating, is never permitted, so it equalled the doubted evaluation), and closes the cap gap
    (D r1, q4_b07). Owners: a covenant that breaches under some resolution goes to the Required Lenders; otherwise
    the owner rule applies to the held unit.
    weak = {addback_no: {fields}} (floor lock, 16-floor-lock-preregistration.md): answers accepted under the learned
    floor but below the locked floor. The line itself keeps its answer; every other unit must post under every
    resolution of those fields too. weak None or empty gives the step 7b rule exactly."""
    weak = weak or {}
    units, info = evaluate(cert, ag, prior, judged)
    doubt = sorted(n for n, j in judged.items() if NEEDS_REVIEW in j.values() or weak.get(n))
    if not doubt:
        return units, info
    own_fixed = {n for n in doubt if weak.get(n) and NEEDS_REVIEW not in judged[n].values()}
    holds, breach = {uid: False for uid in units}, {uid: False for uid in units}
    for combo in itertools.product(*(resolutions(judged[n], categories, weak.get(n, ())) for n in doubt)):
        res = dict(zip(doubt, combo))
        alt, _ = evaluate(cert, ag, prior, {**judged, **res})
        for uid, u in alt.items():
            n = int(uid[1:]) if uid.startswith('A') else None
            if n in own_fixed and res[n] != {k: judged[n][k] for k in ('category', 'realized', 'certified')}:
                continue                     # a weak line's own outcome rests on its own accepted answer
            holds[uid] |= u['disposition'] == 'hold'
            breach[uid] |= u['breach'] == 'yes'
    for uid, u in units.items():
        if u['disposition'] == 'post' and holds[uid]:
            u.update(disposition='hold', review='depends_on_review',
                     owner='required_lenders' if breach[uid] else owner(dict(u, disposition='hold')))
    return units, info


def owner(u):
    """The lender-vote owner rule (10-banking-mirror-plan.md §3)."""
    if u['disposition'] != 'hold':
        return 'none'
    if u['unit_type'] == 'covenant' and u['breach'] == 'yes':
        return 'required_lenders'
    if u['error_class'] in ('cure_invalid', 'late_delivery'):
        return 'required_lenders'
    if u['unit_type'] == 'addback':
        return 'credit_officer'
    if u['error_class'] in ('ratio_arithmetic', 'signer_not_officer'):
        return 'analyst'
    return 'analyst'
