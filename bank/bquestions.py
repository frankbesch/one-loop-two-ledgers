"""Step 7 typed questions (arm D on the general model; R3): the banking mirror's narrow reads.

  QC  addback category: what kind of item is this, judged from the description? (choice over categories.json,
      plus needs_review). Code then decides whether the agreement permits it.
  QR  realized or projected: does the description say the amount was achieved, or is expected? (choice + needs_review)
      Asked only when QC says cost_savings.
  QX  certification: does the officer certification paragraph name this addback's number? (choice yes/no +
      needs_review), with a quote that must contain the number.
House rules as in step 6 (D-208, D-210, D-241): closed lists with needs_review; the model quotes; code applies the
floor and decides. The call goes through job B's CLI wrapper (jobb/run_b.ask_claude), reused unchanged.
"""
import json, re, sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO / 'jobb'))
from codelayer import NEEDS_REVIEW, NO_EVIDENCE, _squash  # noqa: E402

DOMAIN = 'The text is part of a quarterly compliance certificate that a borrower sends to its bank under a credit agreement. '
NR_DESC = 'The evidence is thin.'
QUESTIONS = {
    'QC': 'Judged from what the description says the item actually is (not from the label printed beside it), which kind of item is this EBITDA addback?',
    'QR': 'Does the description say these cost savings were already achieved, or that they are expected or planned?',
    'QX': 'Does the officer certification paragraph name this addback number among the cost savings it certifies?',
}


def options(qid, categories=None):
    if qid == 'QC':
        return dict(categories)
    if qid == 'QR':
        return {'realized': 'The savings were already achieved.', 'projected': 'The savings are expected, planned, or not yet achieved.'}
    if qid == 'QX':
        return {'yes': 'The paragraph names this addback number.', 'no': 'The paragraph does not name this number, or no certification paragraph is printed.'}
    raise KeyError(qid)


def text_for(qid, addback, cert_text_cert=None):
    if qid in ('QC', 'QR'):
        return f"Addback No. {addback['addback_no']}\nDescription: {addback['description']}\nCategory label printed: {addback['category_printed']}"
    return (f"Addback number in question: {addback['addback_no']}\n"
            f"Officer certification paragraph: {cert_text_cert or 'none printed'}")


def claude_prompt(qid, text, categories=None):
    opts = options(qid, categories); opts[NEEDS_REVIEW] = NR_DESC
    ev = (f'"evidence" is the exact words from the text that support the answer, copied verbatim, or "{NO_EVIDENCE}" '
          'when the text holds none.')
    if qid == 'QX':
        ev = (f'"evidence" is the exact words of the paragraph that name the number, copied verbatim, or "{NO_EVIDENCE}" '
              'when the answer is no.')
    prompt = (DOMAIN + f'Question: {QUESTIONS[qid]}\n'
              f'Options (unordered), with what each one means: {json.dumps(opts, ensure_ascii=False)}\n'
              'Return {"answer": <one option>, "probabilities": {<every option>: <number 0-1>}, "evidence": <string>} '
              f'with probabilities summing to 1. {ev}\n\nText:\n{text}')
    if not prompt.endswith('Text:\n' + text):
        raise AssertionError('prompt does not carry the text')
    return prompt


class Shape(ValueError):
    pass


def decide(ans, qid, floor, categories=None):
    """-> (value, top, p_top). value is needs_review below the floor, on a needs_review top, or on a mismatch."""
    keys = set(options(qid, categories)) | {NEEDS_REVIEW}
    p = ans.get('probabilities') if isinstance(ans, dict) else None
    if not isinstance(p, dict) or not p or set(p) - keys:
        raise Shape(f'{qid} probabilities missing or outside the option set')
    for k, v in p.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise Shape(f'probability {k}={v!r}')
    if abs(sum(p.values()) - 1) > 0.05:
        raise Shape(f'probabilities sum to {sum(p.values()):.3f}')
    top = max(p, key=p.get)
    value = NEEDS_REVIEW if top == NEEDS_REVIEW or p[top] < floor or ans.get('answer') not in (None, top) else top
    return value, top, p[top]


def quote_ok(qid, value, evidence, text, addback_no=None):
    """The evidence check (step 6 Q17 idea): a positive answer needs a verbatim quote from the text; for QX 'yes'
    the quote must also contain the addback number."""
    if value in (NEEDS_REVIEW,):
        return True
    if qid == 'QX' and value == 'no':
        return True
    ev = evidence or ''
    if ev == NO_EVIDENCE or len(_squash(ev)) < 3 or _squash(ev) not in _squash(text):
        return False
    if qid == 'QX' and value == 'yes' and not re.search(rf'(?<!\d){addback_no}(?!\d)', ev):
        return False
    return True
