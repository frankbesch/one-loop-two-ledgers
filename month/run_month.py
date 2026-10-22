#!/usr/bin/env python3
"""Step 6 month runner, arm D: this architecture, month by month (flow steps 0-12 as ruled, F1).

  run_month.py --months 1 2 --backend oracle                                   harness proof (perfect answers)
  run_month.py --months 1 2 --backend claude --mode live --model claude-sonnet-5-5         subscription
  run_month.py --months 1 2 --backend jev --mode live --yes --d283 D-300 --max-spend 0.20  metered (Frank's Terminal)

Per month, in billing order:
  units from PDFs through the saved format maps (step 4); an unknown header is a drift event: the document is
    held whole for a person (fails closed), with its header fingerprint;
  linking (step 5): exact match, else Q5 from the owner's properties;
  claims (step 7): job B's Q2/Q6/Q7/Q9, frozen wording, with AFE numbers read through the saved formats;
  money (step 6): six rules on the reference in force on the service date, ledger state carried across months;
  policy (steps 8, 11): hold or post, dollars at stake; the ledger of posted and held lines;
  close (step 12): the person (the answer key) decides every held line; a 5% random audit of posted lines;
    on a drift event the person may add the new format's map (--person-maps), and the month is re-run.
The promotion rule for challengers is Frank's to approve before month 3 (not applied here).
Outputs: runs/month/<arm>/: calls.jsonl, m<k>/outcomes.json, m<k>/close.json, events.json, state.json, meta.json.
"""
import argparse, datetime, hashlib, json, os, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(DEMO / 'jobb')); sys.path.insert(0, str(DEMO / 'typed'))
import codelayer as C  # noqa: E402
import jev_backend as jev  # noqa: E402
import mcode as M  # noqa: E402
import mquestions as MQ  # noqa: E402
import munits as MU  # noqa: E402
import questions as Q  # noqa: E402
from run_b import ask_claude, claude_version, claude_auth_method  # noqa: E402

DEFAULT_FLOOR = 0.60
AUDIT_SHARE = 0.05
AUTH = {'claims_afe': 'afe', 'claims_other': 'other_authority', 'no_claim': 'no_claim'}
Q7_TRUTH = {'placeholder': 'placeholder', 'no_number': 'no_reference', 'none': 'no_reference'}


class Oracle:
    """Perfect answers from the key: proves the harness, never a result."""

    def __init__(self, truth, reg):
        self.l = {(x['doc_id'], x['line_no']): x for x in truth['lines']}
        self.reg = reg

    @staticmethod
    def _ans(key, keys, evidence):
        keys = list(keys) + [C.NEEDS_REVIEW]
        rest = 0.1 / (len(keys) - 1)
        return {'answer': key, 'probabilities': {k: (0.9 if k == key else rest) for k in keys}, 'evidence': evidence}

    def ask(self, qid, u, text, target, tokens=None, properties=None):
        t = self.l[(u['doc_id'], u['line_no'])]
        claim = AUTH[t['claim_type']]
        ev = (t.get('claim_text') or '') if C._squash(t.get('claim_text') or '') in C._squash(text) and t.get('claim_text') else \
            next((s for s in Q.spans(text) if len(s) >= 3), C.NO_EVIDENCE)
        if qid == 'Q5':
            i = next(i for i, p in enumerate(properties, 1) if p['property_no'] == t['property_no'])
            return self._ans(f'p{i}', MQ.q5_options(properties), u['property_printed'])
        if qid == 'Q2':
            v = ('no_claim' if t['difficulty'] == 'hard' else claim) if target == 'line' else \
                (claim if target.get('remark_role') == 'claim' else 'no_claim')
            return self._ans(v, Q.options_for('Q2'), ev if v != 'no_claim' else C.NO_EVIDENCE)
        if qid == 'Q6':
            k = t['authority_kind'] if t['authority_kind'] in Q.Q6_OPTIONS else 'other'
            return self._ans(k, Q.Q6_OPTIONS, ev)
        if qid == 'Q7':
            return self._ans(Q7_TRUTH.get(t['reference_kind'], 'number_given'), Q.Q7_OPTIONS, ev)
        if qid == 'Q9':
            pick = None
            if t['reference_kind'] in ('exact', 'reformatted', 'reworded', 'unknown_number'):
                known = [x for x in tokens if self.reg.lookup(x)[0] in ('approved', 'declined')]
                inclaim = [x for x in tokens if x in (t.get('claim_text') or '')]
                pick = ((known if t['reference_kind'] != 'unknown_number' else []) or inclaim or [None])[0]
            opts = Q.options_for('Q9', tokens)
            if pick is None:
                return self._ans('none_of_these', opts, C.NO_EVIDENCE)
            return self._ans(f't{tokens.index(pick) + 1}', opts, next((s for s in Q.spans(text) if pick in s), pick))
        raise KeyError(qid)


class Replay:
    """Logged answers keyed by (month, doc, line, qid, n-th ask of that qid on the line)."""

    def __init__(self, sources):
        self.by = {}
        for qid, run in sources.items():
            seen = {}
            for x in open(Path(run) / 'calls.jsonl'):
                c = json.loads(x)
                if qid != '*' and c['qid'] != qid:
                    continue
                k = (c['month'], c['doc_id'], c['line_no'], c['qid'])
                seen[k] = seen.get(k, 0) + 1
                self.by.setdefault((qid,) + k + (seen[k],), c)

    def get(self, month, doc, line, qid, n):
        return self.by.get((qid, month, doc, line, qid, n)) or self.by.get(('*', month, doc, line, qid, n))


class Arm:
    def __init__(self, a, truth, reg, props, out):
        self.a, self.reg, self.props, self.out = a, reg, props, out
        self.oracle = Oracle(truth, reg)
        self.truth = truth
        self.floors = json.loads(Path(a.floors).read_text()) if a.floors else {}
        self.log = open(out / 'calls.jsonl', 'a')
        self.spend, self.calls, self.errors_in_row = 0.0, 0, 0
        self.key = os.environ.get(jev.KEY_ENV) if a.backend == 'jev' and a.mode == 'live' else None
        self.rem_role = {(r['doc_id'], r['names_line'], C._squash(r['text'])): r['remark_role'] for r in truth['remarks']}
        self.replay = None
        self.ord = {}
        self.unsimulated = 0

    def ask(self, month, qid, u, text, target, tokens=None):
        rec = dict(month=month, doc_id=u['doc_id'], line_no=u['line_no'], qid=qid, backend=self.a.backend, mode=self.a.mode,
                   target=target if isinstance(target, str) else 'remark', tokens=tokens)
        ans, env, err = None, {}, None
        props = self.props if qid == 'Q5' else None
        live = self.a.mode == 'live'
        neg = self.a.backend != 'jev'
        if self.a.backend == 'replay':
            k = (month, u['doc_id'], u['line_no'], qid)
            self.ord[k] = self.ord.get(k, 0) + 1
            src = self.replay.get(month, u['doc_id'], u['line_no'], qid, self.ord[k])
            if src is None:
                self.unsimulated += 1
                err = 'unsimulated: not asked in the logged run'
            else:
                ans, err, neg = src.get('answer'), src.get('error'), src.get('backend') != 'jev'
                rec['replayed_from'] = src.get('backend')
                if src.get('tokens') is not None and tokens is not None and src['tokens'] != tokens:
                    err = 'replay token list differs'
        elif self.a.backend == 'jev':
            body, sp = MQ.jev_body(qid, text, self.a.jev_model, tokens, props)
            b = jev.max_tokens(body)
            rec['bound_bytes'] = b
            if live:
                if self.spend + jev.usd(b) > self.a.max_spend:
                    raise SystemExit(f'STOP: next call would pass --max-spend ${self.a.max_spend} (spent ${self.spend:.4f})')
                for attempt in range(5):          # retry 429/529 overload (job B lesson; the job B runner is frozen)
                    st, raw, ms = jev.http('POST', jev.API_URL, self.key, body)
                    if st in (429, 529) and attempt < 4:
                        time.sleep(2 ** attempt); continue
                    break
                env = {'http_status': st, 'duration_ms': int(ms), 'attempts': attempt + 1}
                self.calls += 1
                if st != 200:
                    self.spend += jev.usd(b) if st == 0 else 0
                    err = f'HTTP {st}: {jev.redact(raw, self.key)[:200]}'
                else:
                    resp = json.loads(raw)
                    toks = resp.get('usage', {}).get('input_tokens', b)
                    self.spend += jev.usd(toks); env.update(input_tokens=toks, model=resp.get('model'))
                    if resp.get('model') != self.a.jev_model:
                        err = f"served model {resp.get('model')!r} is not the pinned {self.a.jev_model!r}"
                    else:
                        try:
                            ans = Q.jev_parse(body, resp, sp)
                        except Q.Shape as e:
                            err = f'API SHAPE: {e}'
            else:
                ans = self.oracle.ask(qid, u, text, target, tokens, props)
        elif self.a.backend == 'claude':
            prompt = MQ.claude_prompt(qid, text, tokens, props)
            rec['prompt_sha256'] = hashlib.sha256(prompt.encode()).hexdigest()
            if live:
                ans, env, err = ask_claude(prompt, self.a.model, self.a.deadline_s)
                self.calls += 1
                env = {k: env.get(k) for k in ('duration_ms', 'usage', 'total_cost_usd', 'modelUsage') if k in env}
                served = list((env.get('modelUsage') or {}).keys())
                if not err and served and self.a.model not in served:
                    err = f'served model {served} is not the pinned {self.a.model}'
            else:
                ans = self.oracle.ask(qid, u, text, target, tokens, props)
        else:
            ans = self.oracle.ask(qid, u, text, target, tokens, props)
        value, top, p = C.NEEDS_REVIEW, None, None
        if err is None:
            try:
                value, top, p = MQ.decide(ans, qid, float(self.floors.get(qid, DEFAULT_FLOOR)), tokens, props,
                                          check_sum=neg)
            except Q.Shape as e:
                err = f'malformed: {e}'
        self.errors_in_row = self.errors_in_row + 1 if err else 0
        ev = (ans or {}).get('evidence', '')
        tok = value if qid == 'Q9' and value not in ('none_of_these', C.NEEDS_REVIEW) else None
        if qid == 'Q5':
            q17 = 'pass' if value == C.NEEDS_REVIEW or (len(C._squash(ev)) >= 3 and C._squash(ev) in C._squash(text)) else 'fail'
        else:
            q17 = C.q17(value, ev, text, tok, negative_needs_quote=neg) if err is None else 'fail'
        rec.update(answer=ans, value=value, top=top, p_top=p, error=err, envelope=env, q17=q17)
        self.log.write(json.dumps(rec, ensure_ascii=False) + '\n'); self.log.flush()
        if self.errors_in_row >= 3 and self.a.backend != 'replay':
            raise SystemExit(f'STOP: 3 errors in a row; last: {err}')
        if qid == 'Q5' and q17 == 'fail':
            value = C.NEEDS_REVIEW
        return value, rec

    def line(self, month, u, money, period):
        res = dict(month=month, doc_id=u['doc_id'], line_no=u['line_no'], format=u['format'])
        q14 = C.q14(u)
        recs = []
        prop = M.link_exact(u['property_printed'], self.props)
        link_how = 'exact' if prop else None
        if prop is None:
            v, r = self.ask(month, 'Q5', u, MQ.q5_text(u), 'unit'); recs.append(r)
            prop = None if v in (C.NEEDS_REVIEW, 'none_of_these') else v
            link_how = 'q5' if prop else 'needs_review'
        ltxt = C.line_text(u)
        v, r = self.ask(month, 'Q2', u, ltxt, 'line'); q2 = [v]; recs.append(r)
        for rm in u['remarks']:
            role = self.rem_role.get((u['doc_id'], rm['names_line'], C._squash(rm['text'])), 'no_claim')
            v, r = self.ask(month, 'Q2', u, C.remark_text(rm), {'remark_role': role}); q2.append(v); recs.append(r)
        claim = C.combined_claim(q2)
        text = C.unit_text(u)
        q6 = q7 = q9 = None
        q8v = C.q8(u['reference'], u['description'])
        if claim == 'other_authority':
            q6, r = self.ask(month, 'Q6', u, text, 'unit'); recs.append(r)
        if claim == 'afe':
            if q8v != 'placeholder':
                q7, r = self.ask(month, 'Q7', u, text, 'unit'); recs.append(r)
            toks = self.reg.candidates(text)
            if toks:
                q9, r = self.ask(month, 'Q9', u, text, 'unit', toks); recs.append(r)
            else:
                q9 = 'none_of_these'
        fail = any(r['q17'] == 'fail' for r in recs if r['qid'] in ('Q2', 'Q7', 'Q9'))
        outcome, reason = M.q16m(q14, fail, q2, q7, q8v, q9, self.reg, prop)
        fired, stake, notes = money.check(u, prop, period)
        disp, why = M.disposition(fired, outcome, link_how == 'needs_review', q14)
        res.update(property_no=prop, link=link_how, q2=q2, claim=claim, q6=q6, q7=q7, q8=q8v, q9=q9, claim_outcome=outcome,
                   claim_reason=reason, money=fired, stake=round(stake, 2), notes=notes, disposition=disp, reasons=why,
                   errors=sum(1 for r in recs if r['error']))
        return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(DEMO / 'synth-month'))
    ap.add_argument('--months', type=int, nargs='+', required=True)
    ap.add_argument('--backend', choices=('oracle', 'claude', 'jev', 'replay'), default='oracle')
    ap.add_argument('--replay', nargs='+', default=[], help='replay sources: RUN or QID=RUN (e.g. Q2=runs/month/X); no calls')
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model'); ap.add_argument('--jev-model', default=jev.MODEL)
    ap.add_argument('--formats', default=str(HERE / 'formats_known.json'), help="the owner's saved format maps")
    ap.add_argument('--person-maps', help='formats the person adds at close on a drift event (onboarding a new format)')
    ap.add_argument('--floors')
    ap.add_argument('--deadline-s', type=float, default=60.0)
    ap.add_argument('--max-spend', type=float, default=0.20)
    ap.add_argument('--yes', action='store_true'); ap.add_argument('--d283')
    ap.add_argument('--seed', type=int, default=6)
    ap.add_argument('--loop', action='store_true', help='month-close challenger and promotion (rule approved 10-08)')
    ap.add_argument('--out')
    ap.add_argument('--frozen', help='frozen/FREEZE.json: re-hash every frozen file, use its floors (required for months 3-6)')
    a = ap.parse_args()
    if a.frozen:
        fz = json.loads(Path(a.frozen).read_text())
        root = Path(a.frozen).resolve().parent
        bad = [f for f, h in fz['hashes'].items() if hashlib.sha256((root / f).read_bytes()).hexdigest() != h]
        if bad:
            sys.exit(f'REFUSED: frozen files changed since the freeze: {bad}')
        a.floors = str(root / fz['floors_file'])
    elif any(m > 2 for m in a.months) and a.backend != 'oracle':
        sys.exit('REFUSED: months 3-6 run only with --frozen month/frozen/FREEZE.json (step 4 freeze)')
    if a.backend == 'oracle' and a.mode == 'live':
        ap.error('the oracle has no live mode')
    if a.backend == 'claude' and a.mode == 'live' and not a.model:
        ap.error('claude live needs --model <exact id>')
    if a.backend == 'jev' and a.mode == 'live':
        if not (a.yes and a.d283):
            ap.error('jev live is metered: --yes and --d283 <case> (D-300 covers this study)')
        ok, msg = jev.key_status()
        if not ok:
            sys.exit(msg)
    if a.mode == 'dry-run' or a.backend in ('oracle', 'replay'):
        jev.install_socket_guard()
    corpus = Path(a.corpus)
    truth = json.loads((corpus / 'truth_m.json').read_text())
    ref = {k: json.loads((corpus / 'reference' / f'{k}.json').read_text())
           for k in ('doi', 'contract_rates', 'afe_register', 'elections', 'joa_terms', 'properties')}
    spec = json.loads((corpus / 'case_spec_m.json').read_text())
    period = {m['month']: m['billing_period'] for m in spec['months']}
    formats = json.loads(Path(a.formats).read_text())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm = f"D-{a.backend}-{a.mode}-m{''.join(map(str, a.months))}-{stamp}"
    out = Path(a.out) if a.out else DEMO / 'runs' / 'month' / arm
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(frozen=a.frozen, arm=arm, corpus=str(corpus), months=a.months, backend=a.backend, mode=a.mode, d283=a.d283,
                model=a.model if a.backend == 'claude' else a.jev_model if a.backend == 'jev' else None,
                floors=a.floors or f'default {DEFAULT_FLOOR}', formats_at_start=sorted(formats), started=stamp,
                truth_sha256=hashlib.sha256((corpus / 'truth_m.json').read_bytes()).hexdigest())
    if a.backend == 'claude':
        meta['claude_version'] = claude_version()
        if a.mode == 'live':
            meta['claude_auth_method'] = claude_auth_method()
    if a.backend == 'jev' and a.mode == 'live':
        ok, msg = jev.auth_check(os.environ[jev.KEY_ENV]); meta['jev_auth'] = msg
        if not ok:
            sys.exit(msg)
    events, state = [], None
    labels, done, promotions = {}, [], []
    t0 = time.time()
    arm_obj = None
    try:
        for m in a.months:
            for attempt in ('first', 'after_remap'):
                reg = M.Register(ref['afe_register'], formats)
                if arm_obj is None:
                    arm_obj = Arm(a, truth, reg, ref['properties'], out)
                    if a.backend == 'replay':
                        arm_obj.replay = Replay({(x.split('=', 1)[0] if '=' in x else '*'): x.split('=', 1)[-1] for x in a.replay})
                arm_obj.reg = reg; arm_obj.oracle.reg = reg
                money = M.Money(ref, reg, state)
                units, drift = MU.load_month(corpus, m, formats)
                res = [arm_obj.line(m, u, money, period[m]) for u in sorted(units, key=lambda u: (u['doc_id'], u['line_no']))]
                for ev in drift:   # the whole document goes to a person
                    for t in truth['lines']:
                        if t['doc_id'] == ev['doc_id']:
                            res.append(dict(month=m, doc_id=t['doc_id'], line_no=t['line_no'], format='unknown',
                                            disposition='hold', reasons=['drift:' + ev['drift']], money=[], stake=0.0))
                tag = f'm{m}' if attempt == 'first' else f'm{m}-remap'
                (out / tag).mkdir(exist_ok=True)
                (out / tag / 'outcomes.json').write_text(json.dumps(res, indent=1, ensure_ascii=False) + '\n')
                events += [dict(e, attempt=attempt) for e in drift]
                if drift and a.person_maps and attempt == 'first':
                    new = json.loads(Path(a.person_maps).read_text())
                    added = {k: v for k, v in new.items() if k not in formats}
                    formats.update(added)
                    events.append(dict(month=m, person_action='added format map', formats=sorted(added)))
                    continue          # the person onboards the new format; the month is re-run
                state = money.state()
                break
            # close (step 12): audit sample of posted lines, checked against the key
            rng = random.Random(f'{a.seed}-{m}')
            posted = [r for r in res if r['disposition'] == 'post']
            sample = rng.sample(posted, max(1, round(AUDIT_SHARE * len(posted)))) if posted else []
            tl = {(x['doc_id'], x['line_no']): x for x in truth['lines']}
            found = [(s['doc_id'], s['line_no']) for s in sample if tl[(s['doc_id'], s['line_no'])]['disposition'] == 'hold']
            close = dict(month=m, posted=len(posted), held=len(res) - len(posted), audit_n=len(sample), audit_found=found,
                         audit_estimate_silent=round(len(found) / len(sample) * len(posted), 1) if sample else None)
            (out / tag / 'close.json').write_text(json.dumps(close, indent=1) + '\n')
            # the person's labels: every held line decided, plus the audit sample (the key plays the person)
            for r in res:
                if r['disposition'] == 'hold' and r.get('format') != 'unknown':
                    labels[(r['doc_id'], r['line_no'])] = tl[(r['doc_id'], r['line_no'])]['disposition']
            for s_ in sample:
                labels[(s_['doc_id'], s_['line_no'])] = tl[(s_['doc_id'], s_['line_no'])]['disposition']
            done.append(m)
            if a.loop and a.backend in ('claude', 'jev', 'replay'):
                import loop as L
                arm_obj.log.flush()
                running = {q: float(arm_obj.floors.get(q, DEFAULT_FLOOR)) for q in ('Q2', 'Q5', 'Q6', 'Q7', 'Q9')}
                src_run = a.replay[0].split('=', 1)[-1] if a.backend == 'replay' else str(out)
                prop, ok = L.challenger(sys.modules[__name__], a, truth, ref, formats, period, list(done), src_run,
                                        labels, running, out / '_loop')
                promotions.append(dict(after_month=m, **prop))
                if ok:
                    arm_obj.floors = dict(prop['challenger'])
                (out / 'promotions.json').write_text(json.dumps(promotions, indent=1) + '\n')
    finally:
        if arm_obj:
            arm_obj.log.close()
        n = sum(1 for _ in open(out / 'calls.jsonl')) if (out / 'calls.jsonl').exists() else 0
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                    wall_s=round(time.time() - t0, 1), requests=n, live_calls=arm_obj.calls if arm_obj else 0,
                    formats_at_end=sorted(formats), unsimulated=arm_obj.unsimulated if arm_obj else 0)
        if a.backend == 'jev':
            meta.update(spend_usd=round(arm_obj.spend, 6) if arm_obj and a.mode == 'live' else 0.0,
                        spend_basis='usage.input_tokens at $0.042/Mtok (docs price)' if a.mode == 'live' else 'dry-run: no call')
        (out / 'events.json').write_text(json.dumps(events, indent=1) + '\n')
        (out / 'state.json').write_text(json.dumps(state or {}, indent=1) + '\n')
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps({k: meta[k] for k in meta if k != 'corpus'}, indent=1)); print(f'outputs: {out}')


if __name__ == '__main__':
    main()
