#!/usr/bin/env python3
"""Step 7 arm C, banking: the v1 confidence handoff (cascade). Configured from month/arm_c.py.

  arm_c_bank.py --quarters 1 2                                                    dry-run (simulated answers)
  arm_c_bank.py --quarters 3 4 --mode live --model claude-sonnet-5-5 --yes --d283 D-300 --max-spend 0.50 --frozen bank/frozen/FREEZE-BANK.json

Per certificate: one Jev request asks one choice question per unit ("which issue, if any, applies to unit U?") on a
state of the reference files plus the certificate's text. At confidence 0.80 or more Jev's answer stands; below it,
one Claude call per certificate answers those units with the same options, and its answer is final. No needs_review
option (v1). Code adds arithmetic only: each printed ratio against its printed inputs; unadjusted EBITDA against its
four lines. Reused unchanged: typed/jev_backend.py, month/arms_common.py (doc_text, claude_call), jobb/questions.py (_probs).
"""
import argparse, datetime, hashlib, json, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(DEMO / 'month')); sys.path.insert(0, str(DEMO / 'jobb')); sys.path.insert(0, str(DEMO / 'typed'))
import arms_common as AC  # noqa: E402
import jev_backend as jev  # noqa: E402
import questions as Q  # noqa: E402

THRESHOLD = 0.80
OPTIONS = {
    'none': 'No issue: the unit can be accepted.',
    'ratio_arithmetic': 'A covenant ratio does not follow from its own printed inputs.',
    'hidden_breach': 'The certificate says the covenant passes, but under the agreement (permitted addbacks only, valid cure only, the agreement threshold) it fails.',
    'reported_breach': 'The certificate itself reports a covenant failure.',
    'cap_exceeded': 'A cost-savings addback takes the cost-savings total over the agreement cap.',
    'window_expired': 'A projected cost-savings addback is older than the agreement window.',
    'category_not_permitted': 'The addback is a kind of item the agreement does not permit, whatever its label.',
    'certification_missing': 'A cost-savings addback lacks the officer certification naming it.',
    'signer_not_officer': 'The signer is not a Responsible Officer under the agreement.',
    'late_delivery': 'The certificate was delivered after the agreement deadline.',
    'cure_invalid': 'An equity cure exceeds the agreement limits (count, or consecutive quarters).',
    'duplicate_addback': 'The addback repeats an earlier addback on the same certificate.',
}
SYSTEM = 'You answer typed questions about one compliance certificate. Reply with only a JSON object, no prose, no code fence.'
NUM = r'\(?-?\$?[\d,]+\)?'


def money(s):
    s = s.replace('$', '').replace(',', '').strip()
    neg = s.startswith('(') or s.startswith('-')
    v = int(s.strip('()-'))
    return -v if neg else v


def arithmetic(text):
    """-> {unit_id: reason} for printed numbers that do not add up (the only code check v1 keeps)."""
    out = {}
    for uid, lab in (('LEV', 'Total leverage'), ('ICR', 'Interest coverage')):
        m = re.search(lab + r'\s+\$?([\d,]+)\s+\$?([\d,]+)\s+([\d.]+)x', text)
        if m:
            inp, adj, ratio = money(m.group(1)), money(m.group(2)), float(m.group(3))
            calc = inp / adj if uid == 'LEV' else adj / inp
            if abs(round(calc + 1e-9, 2) - ratio) > 0.011:
                out[uid] = 'arithmetic:ratio'
    return out


def state_for(corpus, q, cert_id, text):
    ref = Path(corpus) / 'reference'
    refs = '\n'.join(f'{n}: ' + json.dumps(json.loads((ref / n).read_text()), separators=(',', ':'))
                     for n in ('agreements.json', 'categories.json', f'prior_cures_q{q}.json'))
    return f'Quarter: 2025 Q{q}. Reference data:\n{refs}\n\n==== Certificate {cert_id} ====\n{text}'


def jev_body(state, unit_ids, model):
    qs = {f'U_{u}': {'type': 'choice', 'criteria': dict(OPTIONS),
                     'instructions': 'The text is a quarterly compliance certificate with the credit agreement terms. '
                                     f'Which issue, if any, applies to unit {u} of this certificate? Units: A<n> is addback n; '
                                     'LEV and ICR are the leverage and interest-coverage lines; DELIVERY, SIGNER, CURE.'}
          for u in unit_ids}
    return {'state': state, 'model': model, 'questions': qs}


def parse(resp_answers, unit_ids, prefix='U_'):
    out = {}
    for u in unit_ids:
        a = resp_answers.get(f'{prefix}{u}')
        p = Q._probs(a, OPTIONS)
        top = max(p, key=p.get)
        c = a.get('confidence')
        conf = float(c) if isinstance(c, (int, float)) and not isinstance(c, bool) else p[top]
        out[u] = dict(answer=top, confidence=conf, probabilities=p)
    return out


def claude_prompt(state, unit_ids):
    return (state + '\n\nFor each of these units of the certificate: ' + ', '.join(unit_ids)
            + f'\nchoose the one issue that applies. Options, with what each one means: {json.dumps(OPTIONS)}\n'
            'Return {"answers": {"<unit id>": {"answer": <one option>, "probabilities": {<every option>: <number 0-1>}}}} '
            "with each unit's probabilities summing to 1.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(DEMO / 'synth-bank'))
    ap.add_argument('--quarters', type=int, nargs='+', required=True)
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model'); ap.add_argument('--jev-model', default=jev.MODEL)
    ap.add_argument('--deadline-s', type=float, default=300.0); ap.add_argument('--max-spend', type=float, default=0.50)
    ap.add_argument('--yes', action='store_true'); ap.add_argument('--d283'); ap.add_argument('--frozen'); ap.add_argument('--out')
    a = ap.parse_args()
    live = a.mode == 'live'
    if live and any(q > 2 for q in a.quarters):
        if not a.frozen:
            sys.exit('REFUSED: quarters 3-4 run live only with --frozen bank/frozen/FREEZE-BANK.json')
        fz = json.loads(Path(a.frozen).read_text()); root = Path(a.frozen).resolve().parent
        bad = [f for f, h in fz['hashes'].items() if hashlib.sha256((root / f).read_bytes()).hexdigest() != h]
        if bad:
            sys.exit(f'REFUSED: frozen files changed since the freeze: {bad}')
    if live:
        if not a.model:
            ap.error('live needs --model')
        if not (a.yes and a.d283):
            ap.error('jev live is metered: --yes and --d283 (D-300 covers this study)')
        ok, msg = jev.key_status()
        if not ok:
            sys.exit(msg)
    else:
        jev.install_socket_guard()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    keyu = {(u['cert_id'], u['unit_id']): u for u in truth['units']}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = f"C-bank-{a.mode}-q{''.join(map(str, a.quarters))}-{stamp}"
    out = Path(a.out) if a.out else DEMO / 'runs' / 'bank' / name
    if (out / 'calls.jsonl').exists():
        sys.exit(f'REFUSED: {out} already holds a run (D-301 (4))')
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(arm=name, quarters=a.quarters, mode=a.mode, jev_model=a.jev_model, model=a.model, threshold=THRESHOLD, d283=a.d283,
                frozen=a.frozen, started=stamp)
    key = os.environ.get(jev.KEY_ENV) if live else None
    if live:
        ok, msg = jev.auth_check(key); meta['jev_auth'] = msg
        if not ok:
            sys.exit(msg)
    log = open(out / 'calls.jsonl', 'a'); spend, jcalls, ccalls, errs = 0.0, 0, 0, 0; t0 = time.time()
    try:
        for q in a.quarters:
            rows = []
            for pdf in sorted((Path(a.corpus) / 'clean').glob(f'q{q}_*.pdf')):
                cid = pdf.stem
                uids = sorted(u for (c, u) in keyu if c == cid)
                text = AC.doc_text(pdf)
                state = state_for(a.corpus, q, cid, text)
                jans, err = None, None
                rec = dict(quarter=q, cert_id=cid, step='jev', units=uids)
                if live:
                    body = jev_body(state, uids, a.jev_model); b = jev.max_tokens(body); rec['bound_bytes'] = b
                    if spend + jev.usd(b) > a.max_spend:
                        raise SystemExit(f'STOP: next call would pass --max-spend ${a.max_spend} (spent ${spend:.4f})')
                    for attempt in range(5):
                        st, raw, ms = jev.http('POST', jev.API_URL, key, body)
                        if st in (429, 529) and attempt < 4:
                            time.sleep(2 ** attempt); continue
                        break
                    jcalls += 1; rec['envelope'] = dict(http_status=st, duration_ms=int(ms))
                    if st != 200:
                        err = f'HTTP {st}: {jev.redact(raw, key)[:200]}'
                    else:
                        resp = json.loads(raw); toks = resp.get('usage', {}).get('input_tokens', b)
                        spend += jev.usd(toks); rec['envelope'].update(input_tokens=toks, model=resp.get('model'))
                        try:
                            jans = parse(resp['answers'], uids)
                        except (Q.Shape, KeyError, TypeError) as e:
                            err = f'API SHAPE: {e}'
                else:
                    jans = {u: dict(answer=(keyu[(cid, u)]['error_class'] if keyu[(cid, u)]['error_class'] != 'none' else
                                            ('reported_breach' if keyu[(cid, u)]['breach'] == 'yes' else 'none')),
                                    confidence=0.9 if hash((cid, u)) % 4 else 0.6) for u in uids}
                rec.update(answers=jans, error=err); log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
                errs = errs + 1 if err else 0
                if errs >= 3:
                    raise SystemExit(f'STOP: 3 errors in a row; last: {err}')
                final = {u: dict(jans[u], by='jev') for u in uids if jans and jans[u]['confidence'] >= THRESHOLD}
                low = [u for u in uids if u not in final]
                if low:
                    crec = dict(quarter=q, cert_id=cid, step='claude', units=low); cans, cerr = None, None
                    if live:
                        ans, env, cerr = AC.claude_call(claude_prompt(state, low), a.model, a.deadline_s, SYSTEM); ccalls += 1
                        crec['envelope'] = AC.slim_env(env)
                        if not cerr:
                            try:
                                cans = {u: dict(answer=max(ans['answers'][u]['probabilities'], key=lambda k: float(ans['answers'][u]['probabilities'][k])))
                                        for u in low}
                                if any(v['answer'] not in OPTIONS for v in cans.values()):
                                    raise ValueError('option outside the list')
                            except (KeyError, TypeError, ValueError) as e:
                                cerr, cans = f'malformed: {e}', None
                    else:
                        cans = {u: dict(answer=(keyu[(cid, u)]['error_class'] if keyu[(cid, u)]['error_class'] != 'none' else
                                                ('reported_breach' if keyu[(cid, u)]['breach'] == 'yes' else 'none'))) for u in low}
                    crec.update(answers=cans, error=cerr); log.write(json.dumps(crec, ensure_ascii=False) + '\n'); log.flush()
                    for u in low:
                        final[u] = dict(cans[u], by='claude') if cans else dict(answer=None, by='error')
                ar = arithmetic(text)
                for u in uids:
                    f = final[u]
                    reasons = (['error:failed_closed'] if f['answer'] is None else [f"{f['by']}:{f['answer']}"] if f['answer'] != 'none' else []) \
                        + ([ar[u]] if u in ar else [])
                    rows.append(dict(quarter=q, cert_id=cid, unit_id=u, disposition='hold' if reasons else 'post', by=f['by'],
                                     breach='yes' if f['answer'] in ('hidden_breach', 'reported_breach') else 'no', owner=None, reasons=reasons))
            (out / f'q{q}').mkdir(exist_ok=True)
            (out / f'q{q}' / 'outcomes.json').write_text(json.dumps(rows, indent=1) + '\n')
            print(f"q{q}: held {sum(r['disposition'] == 'hold' for r in rows)}, by claude {sum(r['by'] == 'claude' for r in rows)}, jev ${spend:.6f}", flush=True)
    finally:
        log.close()
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'), wall_s=round(time.time() - t0, 1),
                    jev_calls=jcalls, claude_calls=ccalls, spend_usd=round(spend, 6) if live else 0.0,
                    spend_basis='usage.input_tokens at $0.042/Mtok (docs price)' if live else 'dry-run: no call')
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(f'outputs: {out}')


if __name__ == '__main__':
    main()
