#!/usr/bin/env python3
"""Step 6 arm C, the v1 confidence handoff (cascade): Jev answers each line; at confidence 0.80 or more its answer
stands, otherwise Claude answers. No code rules beyond arithmetic.

  arm_c.py --months 1 2                                                  dry-run: both models simulated from the key
  arm_c.py --months 1 --mode live --model claude-sonnet-5-5 --yes --d283 D-300 --max-spend 0.50   (Frank's Terminal)
  arm_c.py --months 3 4 5 6 --mode live --model claude-sonnet-5-5 --yes --d283 D-300 --frozen month/frozen/FREEZE-ABC.json

v1 as built (01-architecture-brief.md §3): a whole document per call; confidence decides what skips review; 0.80
carried over from Claude; Jev gets no needs_review option. Per document, one Jev request carries one choice
question per line ("which issue, if any, applies to line n?"), on a state of the reference files plus the
document's layout text. Confidence is the API's `confidence` field when present, else the top probability (the
basis is logged per answer). Lines below 0.80 go to one Claude call for the document, with the same inputs and
the same options; Claude's answer is final. A line is held when the final answer names an issue, when the
printed numbers do not add up (arithmetic), or when a call fails (fail closed).
What v1 never had, and arm C does not get: the ledger of earlier months (it would not fit Jev's 32k-token state),
so duplicates and AFE overruns that need earlier lines are out of its reach by design. Score per class to show it.
Jev spend: D-300 (all Jev spend for this study pre-approved); log it in the run record and memory/costs.md.
"""
import argparse, datetime, hashlib, json, os, sys, time
from pathlib import Path

import arms_common as AC
import jev_backend as jev  # noqa: E402  (on the path through arms_common)
import questions as Q  # noqa: E402

THRESHOLD = 0.80
OPTIONS = dict(AC.ISSUES)
MONEY = {'wrong_decimal', 'wrong_rate', 'nonconsent_property', 'afe_overrun', 'duplicate', 'date_window'}
KEY_ISSUE = {'unsupported': 'claim_unsupported', 'contradicted': 'claim_contradicted', 'other_authority': 'claim_other_authority'}
NOTES = ('An AFE claim the register supports (an approved AFE for the same property, in any format or reworded) is '
         'fine. Approval words inside a name or an item are not a claim. Use the reference version in force on the '
         "line's service date.")
SYSTEM = 'You answer typed questions about one billing document. Reply with only a JSON object, no prose, no code fence.'


def state_for(ref, doc_id, text, period):
    return (f'Billing month: {period}. Reference data (each row applies from its effective or approved date):\n'
            + AC.reference_block(ref) + f'\n\n==== Document {doc_id} ====\n{text}')


def jev_body(state, line_nos, model):
    qs = {f'L{n}': {'type': 'choice', 'criteria': dict(OPTIONS),
                    'instructions': jev.DOMAIN + f'Which issue, if any, applies to billing line {n} of this document? ' + NOTES}
          for n in line_nos}
    return {'state': state, 'model': model, 'questions': qs}


def jev_parse(resp, line_nos):
    if not isinstance(resp, dict) or 'answers' not in resp or 'usage' not in resp:
        raise Q.Shape('missing answers or usage')
    out = {}
    for n in line_nos:
        a = resp['answers'].get(f'L{n}')
        p = Q._probs(a, OPTIONS)
        top = max(p, key=p.get)
        c = a.get('confidence')
        conf, basis = (float(c), 'api_confidence') if isinstance(c, (int, float)) and not isinstance(c, bool) else (p[top], 'top_probability')
        out[n] = dict(answer=top, probabilities=p, confidence=conf, basis=basis)
    return out


def claude_prompt(state, line_nos):
    return (AC.POLICY + '\n' + state + '\n\nFor each of these billing lines of the document: '
            + ', '.join(f'L{n}' for n in line_nos)
            + f'\nchoose the one issue that applies. Options, with what each one means: {json.dumps(OPTIONS, ensure_ascii=False)}\n'
            'Return {"answers": {"L<n>": {"answer": <one option>, "probabilities": {<every option>: <number 0-1>}}}} '
            'with each line\'s probabilities summing to 1.')


def claude_parse(ans, line_nos):
    out = {}
    for n in line_nos:
        a = ((ans or {}).get('answers') or {}).get(f'L{n}')
        p = a.get('probabilities') if isinstance(a, dict) else None
        if not isinstance(p, dict) or set(p) - set(OPTIONS) or not p:
            raise Q.Shape(f'L{n}: probabilities missing or outside the option set')
        top = max(p, key=lambda k: float(p[k]))
        out[n] = dict(answer=top, probabilities=p, confidence=float(p[top]), basis='claude_top_probability')
    return out


class Oracle:
    """Simulated answers from the key: Jev is sure on plain lines and unsure on hard ones, so both paths run."""

    def __init__(self, truth):
        self.l = {(t['doc_id'], t['line_no']): t for t in truth['lines']}

    def answer(self, doc_id, n, sure):
        t = self.l[(doc_id, n)]
        k = 'none' if t['disposition'] == 'post' else t['money_error'] if t['money_error'] != 'none' else KEY_ISSUE[t['outcome']]
        top = 0.9 if sure else 0.6
        rest = (1 - top) / (len(OPTIONS) - 1)
        return dict(answer=k, probabilities={o: (top if o == k else rest) for o in OPTIONS}, confidence=top, basis='oracle')

    def jev(self, doc_id, line_nos):
        return {n: self.answer(doc_id, n, self.l[(doc_id, n)]['difficulty'] != 'hard' and n % 5) for n in line_nos}

    def claude(self, doc_id, line_nos):
        return {n: self.answer(doc_id, n, True) for n in line_nos}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(AC.DEMO / 'synth-month'))
    ap.add_argument('--months', type=int, nargs='+', required=True)
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model', help='Claude model id for the handoff (live)')
    ap.add_argument('--jev-model', default=jev.MODEL)
    ap.add_argument('--deadline-s', type=float, default=300.0)
    ap.add_argument('--max-spend', type=float, default=0.50)
    ap.add_argument('--yes', action='store_true'); ap.add_argument('--d283')
    ap.add_argument('--frozen', help='frozen/FREEZE-ABC.json (required for a live run on months 3-6)')
    ap.add_argument('--out')
    a = ap.parse_args()
    live = a.mode == 'live'
    AC.guard_months(a.months, a.frozen, live)
    if live:
        if not a.model:
            ap.error('live needs --model <exact Claude id> for the handoff')
        if not (a.yes and a.d283):
            ap.error('jev live is metered: --yes and --d283 <case> (D-300 covers this study)')
        ok, msg = jev.key_status()
        if not ok:
            sys.exit(msg)
    else:
        jev.install_socket_guard()
    truth, ref, period = AC.load(a.corpus)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm = f"C-cascade-{a.mode}-m{''.join(map(str, a.months))}-{stamp}"
    out = Path(a.out) if a.out else AC.DEMO / 'runs' / 'month' / arm
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(arm=arm, corpus=str(Path(a.corpus).resolve()), months=a.months, backend='jev+claude', mode=a.mode,
                jev_model=a.jev_model, model=a.model, threshold=THRESHOLD, d283=a.d283, frozen=a.frozen, started=stamp,
                truth_sha256=hashlib.sha256((Path(a.corpus) / 'truth_m.json').read_bytes()).hexdigest())
    key = None
    if live:
        key = os.environ[jev.KEY_ENV]
        ok, msg = jev.auth_check(key); meta['jev_auth'] = msg
        if not ok:
            sys.exit(msg)
        from run_b import claude_version, claude_auth_method
        meta.update(claude_version=claude_version(), claude_auth_method=claude_auth_method())
    oracle = Oracle(truth)
    log = open(out / 'calls.jsonl', 'a')
    spend, jev_calls, claude_calls, errors_in_row = 0.0, 0, 0, 0
    t0 = time.time()
    try:
        for m in a.months:
            units, left = AC.month_lines(a.corpus, m)
            if left:
                sys.exit(f'month {m}: {len(left)} documents unreadable with both format maps: {left}')
            docs = {}
            for u in units:
                docs.setdefault(u['doc_id'], []).append(u)
            rows = []
            for doc_id, us in docs.items():
                ns = [u['line_no'] for u in us]
                state = state_for(ref, doc_id, AC.doc_text(Path(a.corpus) / 'clean' / f'{doc_id}.pdf'), period[m])
                # Jev first
                rec = dict(month=m, doc_id=doc_id, step='jev', lines=ns)
                jans, err = None, None
                if live:
                    body = jev_body(state, ns, a.jev_model)
                    b = jev.max_tokens(body); rec['bound_bytes'] = b
                    if spend + jev.usd(b) > a.max_spend:
                        raise SystemExit(f'STOP: next call would pass --max-spend ${a.max_spend} (spent ${spend:.4f})')
                    for attempt in range(5):
                        st, raw, ms = jev.http('POST', jev.API_URL, key, body)
                        if st in (429, 529) and attempt < 4:
                            time.sleep(2 ** attempt); continue
                        break
                    jev_calls += 1
                    rec['envelope'] = {'http_status': st, 'duration_ms': int(ms), 'attempts': attempt + 1}
                    if st != 200:
                        spend += jev.usd(b) if st == 0 else 0
                        err = f'HTTP {st}: {jev.redact(raw, key)[:200]}'
                    else:
                        resp = json.loads(raw)
                        toks = resp.get('usage', {}).get('input_tokens', b)
                        if toks > b:
                            raise SystemExit(f'STOP: usage {toks} passes the byte bound {b} (bound falsified, V6)')
                        spend += jev.usd(toks); rec['envelope'].update(input_tokens=toks, model=resp.get('model'))
                        if resp.get('model') != a.jev_model:
                            err = f"served model {resp.get('model')!r} is not the pinned {a.jev_model!r}"
                        else:
                            try:
                                jans = jev_parse(resp, ns)
                            except Q.Shape as e:
                                err = f'API SHAPE: {e}'
                else:
                    jans = oracle.jev(doc_id, ns)
                rec.update(answers=jans, error=err); log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
                errors_in_row = errors_in_row + 1 if err else 0
                if errors_in_row >= 3:
                    raise SystemExit(f'STOP: 3 errors in a row; last: {err}')
                final = {n: dict(jans[n], by='jev') for n in ns if jans and jans[n]['confidence'] >= THRESHOLD}
                low = [n for n in ns if n not in final]
                # the handoff: Claude answers every line below the threshold (all lines when Jev failed)
                if low:
                    crec = dict(month=m, doc_id=doc_id, step='claude', lines=low)
                    cans, cerr = None, None
                    if live:
                        prompt = claude_prompt(state, low)
                        crec['prompt_sha256'] = hashlib.sha256(prompt.encode()).hexdigest()
                        ans, env, cerr = AC.claude_call(prompt, a.model, a.deadline_s, SYSTEM)
                        claude_calls += 1
                        ok, served = AC.served_ok(env, a.model)
                        if not cerr and not ok:
                            cerr = f'served model {served} is not the pinned {a.model}'
                        crec['envelope'] = AC.slim_env(env)
                        if not cerr:
                            try:
                                cans = claude_parse(ans, low)
                            except Q.Shape as e:
                                cerr = f'malformed: {e}'
                    else:
                        cans = oracle.claude(doc_id, low)
                    crec.update(answers=cans, error=cerr); log.write(json.dumps(crec, ensure_ascii=False) + '\n'); log.flush()
                    for n in low:
                        final[n] = dict(cans[n], by='claude') if cans else dict(answer=None, by='error', error=cerr)
                for u in us:
                    f = final[u['line_no']]
                    reasons = []
                    if f['answer'] is None:
                        reasons.append('error:failed_closed')
                    elif f['answer'] != 'none':
                        reasons.append(f"{f['by']}:{f['answer']}")
                    ar = AC.arithmetic(u)
                    if ar:
                        reasons.append(ar)
                    rows.append(dict(month=m, doc_id=doc_id, line_no=u['line_no'], format=u['format'],
                                     disposition='hold' if reasons else 'post', by=f['by'],
                                     confidence=f.get('confidence'), money=[f['answer']] if f['answer'] in MONEY else [],
                                     reasons=reasons))
            AC.write_month(out, m, rows)
            print(f"m{m}: held {sum(r['disposition'] == 'hold' for r in rows)}, by claude {sum(r['by'] == 'claude' for r in rows)}"
                  f", errors {sum(r['by'] == 'error' for r in rows)}, jev spend so far ${spend:.6f}", flush=True)
    finally:
        log.close()
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                    wall_s=round(time.time() - t0, 1), jev_calls=jev_calls, claude_calls=claude_calls,
                    spend_usd=round(spend, 6) if live else 0.0,
                    spend_basis='usage.input_tokens at $0.042/Mtok (docs price)' if live else 'dry-run: no call')
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps({k: meta[k] for k in ('arm', 'jev_calls', 'claude_calls', 'spend_usd', 'wall_s')}, indent=1))
    print(f'outputs: {out}')


if __name__ == '__main__':
    main()
