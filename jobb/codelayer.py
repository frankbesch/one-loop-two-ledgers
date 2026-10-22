"""Job B code layer: the code-owned questions of the set in publishing one-loop-two-ledgers/02-question-set.md.

Q8 literal placeholder, Q9's candidate token lister, Q10 register match, Q11 property match,
Q14 unit completeness, Q16 outcome rows, Q17 evidence check. No model is called here.
"""
import re

NEEDS_REVIEW = 'needs_review'
NO_EVIDENCE = 'no evidence in text'
PLACEHOLDERS = {'n/a', 'tbd', 'pending', 'to follow', '-', '–', '—'}   # Q8 list; blank is not on it
# Q9 lister: spaces allowed around / and -, never after ':'; a bare token needs a digit
TOKEN = re.compile(r'[A-Za-z0-9]+(?:(?:\s?[/\-]\s?|[:.])[A-Za-z0-9]+)+|[A-Za-z]*\d[A-Za-z0-9]*')
NOTHING_FOUND = {'no_claim', 'none_of_these'}   # no_reference quotes the claim that lacks a number (live check 10-08)


def norm(tok):
    """Q10 normalizer: case, separators, and leading zeros. Adjacent letter groups merge (R-W-M = RWM);
    digit groups stay bounded (DB-26-9011 is not DB-26-901)."""
    out = []
    for g in re.findall(r'[A-Za-z]+|\d+', tok):
        if g.isalpha() and out and out[-1].isalpha():
            out[-1] += g.upper()
        else:
            out.append(g.upper() if g.isalpha() else str(int(g)))
    return tuple(out)


def tokens(text):
    """Q9 candidates: number-like tokens, money amounts left out, first occurrence order, no duplicates."""
    seen, out = set(), []
    for t in TOKEN.findall(text or ''):
        if re.search(r'\d', t) and not re.fullmatch(r'[\d,]+(\.\d+)?', t) and t not in seen:
            seen.add(t); out.append(t)
    return out


LABELLED_STANDIN = re.compile(r'\bAFE\b[^:;]*:\s*(N/A|TBD|Pending|To follow|-|\u2013|\u2014)\s*(?:$|;)', re.I)


def q8(reference, description=None):
    """Literal placeholder: the reference value (after any leading label such as 'Approved AFE:') is on the
    fixed list, or either column holds a labelled AFE field whose value is on the list (widened 10-08, Frank:
    12 literal placeholders sit in the description column)."""
    val = (reference or '').rsplit(':', 1)[-1].strip().lower()
    if val in PLACEHOLDERS:
        return 'placeholder'
    if LABELLED_STANDIN.search(reference or '') or LABELLED_STANDIN.search(description or ''):
        return 'placeholder'
    return 'not_listed'


def q10(tok, register):
    """-> (status, entry, kind): status approved|declined|not_found|ambiguous; kind exact|reformatted."""
    hits = [r for r in register if norm(r['afe_number']) == norm(tok)]
    if len(hits) > 1:
        return 'ambiguous', None, None
    if not hits:
        return 'not_found', None, None
    h = hits[0]
    return h['status'], h, ('exact' if h['afe_number'] == tok else 'reformatted')


def q11(entry, line_property):
    if not entry or not entry.get('property_no') or not line_property:
        return 'unknown'
    return 'match' if entry['property_no'] == line_property else 'mismatch'


def q14(unit):
    """Complete: the line has text, sits on one page, and every remark naming it was found."""
    ok = bool(unit.get('line_no')) and unit.get('page') is not None and not unit.get('unmatched_remarks')
    return 'complete' if ok else 'incomplete'


def _squash(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def q17(value, quote, unit_text, token=None, negative_needs_quote=True):
    """Structural evidence check (no keyword lists): 'nothing found' values quote the literal phrase;
    every other value needs a verbatim quote of 3+ characters from its unit; a Q9 quote holds the token."""
    q = _squash(quote)
    if value in NOTHING_FOUND:
        # Frank, 10-08 (option 2): for Jev, whose evidence is a span pick that rarely says "none", a
        # nothing-found answer is not checked against its pick; Claude still quotes the literal phrase.
        if not negative_needs_quote:
            return 'pass'
        return 'pass' if q.lower() == NO_EVIDENCE else 'fail'
    if value == NEEDS_REVIEW:
        return 'pass'
    if len(q) < 3 or q.lower() == NO_EVIDENCE or q not in _squash(unit_text):
        return 'fail'
    if token is not None and token not in q:
        return 'fail'
    return 'pass'


def combined_claim(q2_answers):
    """Row 4: afe if any Q2 call says afe; else other_authority; else no_claim. needs_review blocks (row 3)."""
    if NEEDS_REVIEW in q2_answers:
        return NEEDS_REVIEW
    if 'afe' in q2_answers:
        return 'afe'
    if 'other_authority' in q2_answers:
        return 'other_authority'
    return 'no_claim'


def q16(q14v, q17_fail, q2_answers, q7, q8v, q9, register, line_property):
    """Outcome rows, first match wins. -> (outcome, reason)."""
    if q14v == 'incomplete':
        return NEEDS_REVIEW, 'incomplete_unit'
    if q17_fail:
        return NEEDS_REVIEW, 'evidence_check_failed'
    claim = combined_claim(q2_answers)
    if claim == NEEDS_REVIEW:
        return NEEDS_REVIEW, 'claim_unclear'
    if claim == 'no_claim' and q8v == 'placeholder':
        # cross-check (Frank, 10-08): code sees a literal AFE stand-in, the model sees no claim
        return NEEDS_REVIEW, 'code_model_conflict'
    if claim == 'no_claim':
        return 'no_claim', ''
    if claim == 'other_authority':
        return 'other_authority', 'q6'
    also = 'also_cites_other' if 'other_authority' in q2_answers else ''
    if q9 == NEEDS_REVIEW or q9 is None:
        return NEEDS_REVIEW, 'reference_unclear'
    if q9 != 'none_of_these':
        status, hit, kind = q10(q9, register)
        if status == 'ambiguous':
            return NEEDS_REVIEW, 'register_ambiguous'
        if status == 'declined':
            return 'contradicted', 'afe_declined'
        if status == 'not_found':
            return 'unsupported', 'unknown_number'
        pm = q11(hit, line_property)
        if pm == 'unknown':
            return NEEDS_REVIEW, 'property_unknown'
        if pm == 'mismatch':
            return 'unsupported', 'afe_other_property'
        return 'supported', ' '.join(x for x in (kind, also) if x)
    if q8v == 'placeholder' or q7 == 'placeholder':
        return 'unsupported', 'placeholder'
    if q7 == 'no_reference':
        return 'unsupported', 'no_number'
    return NEEDS_REVIEW, 'reference_conflict'


def code_only(unit, register):
    """The code-only arm (no model): a register token anywhere in the unit is an AFE claim; else a literal
    placeholder in the reference column is unsupported; else no claim."""
    for t in tokens(unit_text(unit)):
        st, hit, _ = q10(t, register)
        if st in ('approved', 'declined'):
            return q16('complete', False, ['afe'], 'number_given', 'not_listed', t, register, unit.get('property'))
    if q8(unit.get('reference'), unit.get('description')) == 'placeholder':
        return 'unsupported', 'placeholder'
    return 'no_claim', ''


LABELS = {'description': 'Description', 'reference': 'Reference', 'remark': 'Line {n} remark'}


def line_text(unit, labels=LABELS):
    return '\n'.join([f"{labels['description']}: {unit.get('description') or ''}",
                      f"{labels['reference']}: {unit.get('reference') or ''}"])


def remark_text(remark, labels=LABELS):
    """A remark as printed, its 'Line N:' lead-in replaced by the vocabulary's lead-in."""
    body = re.sub(r'^\s*Line\s+\d+\s*:\s*', '', remark['text'])
    return f"{labels['remark'].format(n=remark['names_line'])}: {body}"


def unit_text(unit, labels=LABELS):
    return '\n'.join([line_text(unit, labels)] + [remark_text(r, labels) for r in unit.get('remarks', [])])
