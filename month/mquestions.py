"""Step 6 model questions: job B's Q2, Q6, Q7, Q9 unchanged (`jobb/questions.py`, frozen), plus Q5 linking.

Q5 (flow step 5): which of the owner's properties does the printed property refer to? Asked only when the
exact match fails (a name variant). Options are the owner's properties from `properties.json`, plus
none_of_these and needs_review. Evidence: Claude quotes the printed property; Jev picks a code-cut span.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jobb'))
import questions as Q  # noqa: E402
from codelayer import NEEDS_REVIEW, NO_EVIDENCE  # noqa: E402

Q5_TEXT = 'Which of the listed properties is the property this billing line is charged to?'


def q5_options(properties):
    o = {f'p{i}': f'{p["property_no"]}: {p["name"]}' for i, p in enumerate(properties, 1)}
    o['none_of_these'] = 'None of the listed properties.'
    return o


def q5_text(u):
    return f"Property as printed: {u['property_printed']}\nDescription: {u['description'] or ''}"


def claude_prompt(qid, text, tokens=None, properties=None):
    if qid != 'Q5':
        return Q.claude_prompt(qid, text, tokens)
    opts = q5_options(properties); opts[NEEDS_REVIEW] = Q.NR_DESC
    prompt = (Q.DOMAIN + f'Question: {Q5_TEXT}\n'
              f'Options (unordered), with what each one means: {json.dumps(opts, ensure_ascii=False)}\n'
              'Return {"answer": <one option>, "probabilities": {<every option>: <number 0-1>}, "evidence": <string>} '
              'with probabilities summing to 1. "evidence" is the exact words from the text that support the answer, '
              f'copied verbatim, or "{NO_EVIDENCE}" when the text holds none.\n\nText:\n{text}')
    if not prompt.endswith('Text:\n' + text):
        raise AssertionError('prompt does not carry the unit text')
    return prompt


def jev_body(qid, text, model, tokens=None, properties=None):
    if qid != 'Q5':
        return Q.jev_body(qid, text, model, tokens)
    crit = q5_options(properties); crit[NEEDS_REVIEW] = Q.NR_DESC
    sp = Q.spans(text)
    ev = {f's{i}': s for i, s in enumerate(sp, 1)}
    ev['none'] = 'No part of the text names a property.'; ev[NEEDS_REVIEW] = Q.NR_DESC
    body = {'state': text, 'model': model, 'questions': {
        'a': {'type': 'choice', 'instructions': Q.DOMAIN + Q5_TEXT, 'criteria': crit},
        'e': {'type': 'choice', 'instructions': Q.DOMAIN + 'Which listed part of the text names the property?', 'criteria': ev}}}
    return body, sp


def decide(ans, qid, floor, tokens=None, properties=None, check_sum=True):
    """Job B's decide for Q2/Q6/Q7/Q9; for Q5 the same rule, and the value becomes a property number."""
    if qid != 'Q5':
        return Q.decide(ans, qid, floor, tokens, check_sum)
    keys = set(q5_options(properties)) | {NEEDS_REVIEW}
    p = ans.get('probabilities') if isinstance(ans, dict) else None
    if not isinstance(p, dict) or not p or set(p) - keys:
        raise Q.Shape('Q5 probabilities missing or outside the option set')
    for k, v in p.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise Q.Shape(f'probability {k}={v!r}')
    if check_sum and abs(sum(p.values()) - 1) > 0.05:
        raise Q.Shape(f'probabilities sum to {sum(p.values()):.3f}')
    top = max(p, key=p.get)
    value = NEEDS_REVIEW if top == NEEDS_REVIEW or p[top] < floor or ans.get('answer') not in (None, top) else top
    if value.startswith('p') and value[1:].isdigit():
        value = properties[int(value[1:]) - 1]['property_no']
    return value, top, p[top]
