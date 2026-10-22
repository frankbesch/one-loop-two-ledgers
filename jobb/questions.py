"""Job B model questions (Q2, Q6, Q7, Q9) and the two adapters that ask them.

House rules (D-208, D-210, D-241): the model picks one value from a fixed list that includes needs_review;
code applies the floor and decides the outcome. Evidence:
  Claude quotes the unit verbatim (or "no evidence in text"); Q17 checks the quote.
  Jev cannot write text, so evidence is a second choice in the same request: which code-cut span of the
  unit carries the answer (or none). Q17 then checks that the pick agrees with the answer.
Instructions carry no routing prose (D-241): what code does with an answer is never shown to the model.
"""
import json, re

from codelayer import NEEDS_REVIEW, NO_EVIDENCE, LABELS

DOMAIN = 'The text is one line of a joint-interest billing statement or vendor invoice, or a remark about that line. '

Q2_OPTIONS = {
    'afe': 'The text says the charge is covered by an approved AFE (an authorization for expenditure, a budget approval), in any wording. A labelled AFE field counts, even when its value is a stand-in such as N/A, TBD, or a promise to supply the number later.',
    'other_authority': 'The text says the charge is authorized by something other than an AFE: an emergency, a service contract, an operating agreement clause, a prior election, a verbal or informal approval, or an operator policy.',
    'no_claim': 'The text makes no claim that the charge is authorized. Approval words inside a name or an item (for example "Approved-vendor list fee") are not a claim.',
}
Q6_OPTIONS = {
    'emergency': 'An emergency.', 'service_contract': 'A service or maintenance contract.',
    'operating_agreement_clause': 'A clause of the operating agreement.', 'prior_election': "The owner's earlier election or consent.",
    'verbal_or_informal': 'A verbal or informal approval.', 'operator_policy': "The operator's own policy.",
    'other': 'Another authority not listed.',
}
Q7_OPTIONS = {
    'number_given': 'A specific AFE number is printed with the claim, in any format or inside a sentence.',
    'placeholder': 'A stand-in appears instead of a number: N/A, TBD, Pending, To follow, a dash, or wording that promises the number later.',
    'no_reference': 'The claim gives no number and no stand-in.',
}
QUESTIONS = {
    'Q2': 'Does this text claim that the charge is authorized, and by what?',
    'Q6': 'Which authority other than an AFE does this line cite for the charge?',
    'Q7': 'What form does the AFE reference take in this line?',
    'Q9': 'Which listed token is the AFE number that the authorization claim for this line refers to?',
}
NR_DESC = 'The evidence is thin.'

# Label-swap vocabulary (D-295): the column-header and remark lead-in words only; cell text never changes.
VOCAB = {
    'standard': LABELS,
    'alternate': {'description': 'Particulars', 'reference': 'Authority ref', 'remark': 'Note on item {n}'},
}


def options_for(qid, tokens=None):
    if qid == 'Q2':
        return dict(Q2_OPTIONS)
    if qid == 'Q6':
        return dict(Q6_OPTIONS)
    if qid == 'Q7':
        return dict(Q7_OPTIONS)
    if qid == 'Q9':
        opts = {f't{i}': f'The token "{t}".' for i, t in enumerate(tokens or [], 1)}
        opts['none_of_these'] = 'None of the listed tokens is the AFE number the claim cites.'
        return opts
    raise KeyError(qid)


def spans(text):
    """Code-cut evidence spans for Jev: each labelled field, split at ';' and sentence ends."""
    out = []
    for line in text.split('\n'):
        _, _, body = line.partition(': ')
        for part in re.split(r';\s+|(?<=[.!?])\s+', body):
            part = part.strip()
            if len(part) >= 3 and part not in out:
                out.append(part)
    return out


# ------------------------------------------------------------------ Claude (subscription CLI)

SYSTEM_PROMPT = 'You answer one typed question. Reply with only a JSON object, no prose, no code fence.'


def claude_prompt(qid, text, tokens=None):
    """The unit text must reach the model: a guard, after an f-string slip sent '{text}' (10-08 rerun)."""
    opts = options_for(qid, tokens)
    opts[NEEDS_REVIEW] = NR_DESC
    prompt = (DOMAIN + f'Question: {QUESTIONS[qid]}\n'
            f'Options (unordered), with what each one means: {json.dumps(opts, ensure_ascii=False)}\n'
            'Return {"answer": <one option>, "probabilities": {<every option>: <number 0-1>}, "evidence": <string>} '
            'with probabilities summing to 1. "evidence" is the exact words from the text that support the answer, '
            f'copied verbatim. When the answer says nothing is there (no claim, or none of the tokens), evidence is "{NO_EVIDENCE}". '
            f'When a claim gives no number, evidence is the claim itself.\n\nText:\n{text}')
    if not prompt.endswith('Text:\n' + text) or '{text}' in prompt.replace(text, ''):
        raise AssertionError('prompt does not carry the unit text')
    return prompt


# ------------------------------------------------------------------ Jev (TypeSafe System One)

def jev_body(qid, text, model, tokens=None):
    """One request, two independent choice questions on the same state: the answer and its evidence span."""
    opts = options_for(qid, tokens)
    crit = dict(opts); crit[NEEDS_REVIEW] = NR_DESC
    sp = spans(text)
    ev = {f's{i}': s for i, s in enumerate(sp, 1)}
    ev['none'] = 'No part of the text supports a claim of this kind.'
    ev[NEEDS_REVIEW] = NR_DESC
    ev_q = {'Q2': 'Which listed part of the text claims that the charge is authorized?',
            'Q6': 'Which listed part of the text names the authority for the charge?',
            'Q7': 'Which listed part of the text states the AFE claim, with its reference if it has one?',
            'Q9': 'Which listed part of the text holds the AFE number?'}[qid]
    body = {'state': text, 'model': model, 'questions': {
        'a': {'type': 'choice', 'instructions': DOMAIN + QUESTIONS[qid], 'criteria': crit},
        'e': {'type': 'choice', 'instructions': DOMAIN + ev_q, 'criteria': ev}}}
    return body, sp


class Shape(ValueError):
    pass


def _probs(a, keys):
    if not isinstance(a, dict) or a.get('type') != 'choice':
        raise Shape('not a choice answer')
    p = a.get('probabilities')
    if not isinstance(p, dict) or set(p) != set(keys):
        raise Shape('probabilities keys do not equal the option set')
    for k, v in p.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise Shape(f'probability {k}={v!r}')
    return {k: float(v) for k, v in p.items()}


def jev_parse(body, resp, sp):
    """-> contract answer {'answer','probabilities','evidence'}; evidence is the picked span's text."""
    if not isinstance(resp, dict) or 'answers' not in resp or 'usage' not in resp:
        raise Shape('missing answers or usage')
    a = _probs(resp['answers'].get('a'), body['questions']['a']['criteria'])
    e = _probs(resp['answers'].get('e'), body['questions']['e']['criteria'])
    best_e = max(e, key=e.get)
    evidence = NO_EVIDENCE if best_e in ('none', NEEDS_REVIEW) else sp[int(best_e[1:]) - 1]
    return {'answer': max(a, key=a.get), 'probabilities': a, 'evidence': evidence, 'evidence_pick': best_e,
            'evidence_p': e[best_e]}


# ------------------------------------------------------------------ contract scoring (code owns the floor)

def decide(ans, qid, floor, tokens=None, check_sum=True):
    """Validate a contract answer; -> (value, top, p_top). value is needs_review below the floor."""
    keys = set(options_for(qid, tokens)) | {NEEDS_REVIEW}
    p = ans.get('probabilities') if isinstance(ans, dict) else None
    if not isinstance(p, dict) or not p or set(p) - keys:
        raise Shape(f'probabilities missing or outside the option set: {sorted(set(p or {}) - keys)}')
    for k, v in p.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise Shape(f'probability {k}={v!r}')
    if check_sum and abs(sum(p.values()) - 1) > 0.05:
        raise Shape(f'probabilities sum to {sum(p.values()):.3f}')
    top = max(p, key=p.get)
    value = NEEDS_REVIEW if top == NEEDS_REVIEW or p[top] < floor or (ans.get('answer') not in (None, top)) else top
    if qid == 'Q9' and value.startswith('t') and value[1:].isdigit():
        value = tokens[int(value[1:]) - 1]
    return value, top, p[top]
