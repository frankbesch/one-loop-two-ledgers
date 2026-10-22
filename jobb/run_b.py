#!/usr/bin/env python3
"""Job B line runner (One Loop step 2): ask the typed questions per bill line, let code decide the outcome.

  run_b.py --smoke                                       oracle answers on the 3-document smoke corpus
  run_b.py --split calibration --backend jev --mode dry-run          every Jev body built, zero network
  run_b.py --split calibration --backend claude --mode live --model claude-sonnet-5-5   (subscription CLI)
  run_b.py --split calibration --backend jev --mode live --yes --d283 <case> --max-spend 0.05   (Frank, metered)
  run_b.py ... --vocab alternate                         D-295 label-swap arm: header and remark lead-in words swapped

Backends: oracle (perfect answers from the key: proves the harness, never a result), claude (`claude -p` on
the subscription), jev (TypeSafe System One, metered; live only with --yes, a D-283 case id, and a spend cap).
Dry-run builds every request the backend would get (round 2 decided by oracle answers), installs the
socket guard, and prints the call count and spend bound.

Run discipline (D-293 (4), D-295): log `claude --version` per arm; size the Claude budget from a Jev-only arm
first; Claude deadline about 4.2 s per call; Claude-only arms in daytime. Outputs: runs/jobb/<arm>/.
"""
import argparse, datetime, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(DEMO / 'typed'))
import codelayer as C  # noqa: E402
import questions as Q  # noqa: E402
import units as U  # noqa: E402
import jev_backend as jev  # noqa: E402

DEFAULT_FLOOR = 0.60           # house prior (typed runner CHOICE_FLOOR); step 3 calibrates per question
CLAUDE_S_PER_CALL = 4.2        # measured 2026-10-03 (D-293)
MAX_CONSECUTIVE_ERRORS = 3
AUTH = {'claims_afe': 'afe', 'claims_other': 'other_authority', 'no_claim': 'no_claim'}
Q7_TRUTH = {'placeholder': 'placeholder', 'no_number': 'no_reference', 'none': 'no_reference'}


# ------------------------------------------------------------------ oracle (harness proof only)

class Oracle:
    def __init__(self, truth, register):
        self.lines = {(l['doc_id'], l['line_no']): l for l in truth['lines']}
        self.register = register

    def _ans(self, value, opts, evidence):
        keys = list(opts) + [C.NEEDS_REVIEW]
        rest = (1 - 0.9) / (len(keys) - 1)
        return {'answer': value, 'probabilities': {k: (0.9 if k == value else rest) for k in keys}, 'evidence': evidence}

    def ask(self, qid, unit, text, target, tokens=None):
        t = self.lines[(unit['doc_id'], unit['line_no'])]
        claim = AUTH[t['claim_type']]
        if qid == 'Q2':
            if target == 'line':
                v = 'no_claim' if t['difficulty'] == 'hard' else claim
            else:
                v = claim if target['remark_role'] == 'claim' else 'no_claim'
            ev = self._evidence(t, text) if v != 'no_claim' else C.NO_EVIDENCE
            return self._ans(v, Q.options_for('Q2'), ev)
        if qid == 'Q6':
            return self._ans(t['authority_kind'] if t['authority_kind'] in Q.Q6_OPTIONS else 'other', Q.Q6_OPTIONS, self._evidence(t, text))
        if qid == 'Q7':
            v = Q7_TRUTH.get(t['reference_kind'], 'number_given')
            return self._ans(v, Q.Q7_OPTIONS, self._evidence(t, text))
        if qid == 'Q9':
            known = [x for x in tokens if any(C.norm(r['afe_number']) == C.norm(x) for r in self.register)]
            inclaim = [x for x in tokens if x in (t.get('claim_text') or '')]
            pick = None
            if t['reference_kind'] in ('exact', 'reformatted', 'reworded', 'unknown_number'):
                pick = (known or inclaim or [None])[0]
            opts = Q.options_for('Q9', tokens)
            if pick is None:
                return self._ans('none_of_these', opts, C.NO_EVIDENCE)
            key = f't{tokens.index(pick) + 1}'
            span = next((s for s in Q.spans(text) if pick in s), pick)
            return self._ans(key, opts, span)
        raise KeyError(qid)

    @staticmethod
    def _evidence(t, text):
        ct = t.get('claim_text') or ''
        sq = C._squash(text)
        if ct and C._squash(ct) in sq:
            return ct
        return next((s for s in Q.spans(text) if len(s) >= 3), C.NO_EVIDENCE)


# ------------------------------------------------------------------ claude -p (subscription)

def claude_version():
    try:
        return subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f'unavailable: {e}'


def claude_auth_method():
    try:
        out = subprocess.run(['claude', 'auth', 'status'], capture_output=True, text=True, timeout=30).stdout
        return json.loads(out).get('authMethod') or 'unknown'
    except Exception:  # noqa: BLE001
        return 'unknown'


def ask_claude(prompt, model, timeout):
    """One isolated `claude -p` call. Errors live in the stdout envelope (headless-claude-preflight)."""
    cmd = ['claude', '-p', '--output-format', 'json', '--tools', '', '--setting-sources', '',
           '--no-session-persistence', '--system-prompt', Q.SYSTEM_PROMPT, '--model', model]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                              env={k: v for k, v in os.environ.items() if k != jev.KEY_ENV}, cwd='/')
    except subprocess.TimeoutExpired:
        return None, {'duration_ms': int((time.time() - t0) * 1000)}, f'timeout after {timeout}s'
    try:
        env = json.loads(proc.stdout)
    except ValueError:
        return None, {'stderr': proc.stderr[-300:], 'duration_ms': int((time.time() - t0) * 1000)}, 'unparseable envelope'
    if proc.returncode != 0 or env.get('is_error'):
        msg = str(env.get('result') or proc.stderr or f'exit {proc.returncode}')
        if re.search(r'log ?in|auth', msg, re.I):
            msg += ' (remedy: claude auth login, in your own Terminal)'
        return None, env, msg
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', (env.get('result') or '').strip())
    try:
        return json.loads(text), env, None
    except ValueError:
        return None, env, 'model returned no JSON: ' + text[:200]


# ------------------------------------------------------------------ the runner

class Runner:
    def __init__(self, a, truth, register, out):
        self.a, self.register, self.out = a, register, out
        self.oracle = Oracle(truth, register)
        self.labels = Q.VOCAB[a.vocab]
        self.floors = json.loads(Path(a.floors).read_text()) if a.floors else {}
        self.calls, self.errors_in_row, self.spend, self.bound = 0, 0, 0.0, 0
        self.log = open(out / 'calls.jsonl', 'w')
        self.key = os.environ.get(jev.KEY_ENV) if a.backend == 'jev' and a.mode == 'live' else None

    def floor(self, qid):
        return float(self.floors.get(qid, DEFAULT_FLOOR))

    def ask(self, qid, unit, text, target, tokens=None):
        """-> (value, record). Any failure is an error unit and fails closed to needs_review."""
        rec = dict(doc_id=unit['doc_id'], line_no=unit['line_no'], qid=qid, vocab=self.a.vocab,
                   target='line' if target == 'line' else ('remark' if isinstance(target, dict) else target),
                   backend=self.a.backend, mode=self.a.mode, tokens=tokens)
        ans, env, err = None, {}, None
        if self.a.backend == 'jev':
            body, sp = Q.jev_body(qid, text, self.a.jev_model, tokens)
            b = jev.max_tokens(body); self.bound += b
            rec.update(body_sha256=hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(), bound_bytes=b)
            if self.a.mode == 'live':
                if self.spend + jev.usd(b) > self.a.max_spend:
                    raise SystemExit(f'STOP: next call would pass --max-spend ${self.a.max_spend} (spent ${self.spend:.4f})')
                st, raw, ms = jev.http('POST', jev.API_URL, self.key, body)
                env = {'http_status': st, 'duration_ms': int(ms)}
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
                ans = self.oracle.ask(qid, unit, text, target, tokens)
        elif self.a.backend == 'claude':
            prompt = Q.claude_prompt(qid, text, tokens)
            rec['prompt_sha256'] = hashlib.sha256(prompt.encode()).hexdigest()
            if self.a.mode == 'live':
                ans, env, err = ask_claude(prompt, self.a.model, self.a.deadline_s)
                self.calls += 1
                env = {k: env.get(k) for k in ('duration_ms', 'usage', 'total_cost_usd', 'modelUsage', 'num_turns') if k in env}
                served = list((env.get('modelUsage') or {}).keys())
                if not err and served and self.a.model not in served:
                    err = f'served model {served} is not the pinned {self.a.model}'
            else:
                ans = self.oracle.ask(qid, unit, text, target, tokens)
        else:
            ans = self.oracle.ask(qid, unit, text, target, tokens)
        value, top, p = C.NEEDS_REVIEW, None, None
        if err is None:
            try:
                value, top, p = Q.decide(ans, qid, self.floor(qid), tokens, check_sum=self.a.backend != 'jev')
            except Q.Shape as e:
                err = f'malformed: {e}'
        self.errors_in_row = self.errors_in_row + 1 if err else 0
        ev = (ans or {}).get('evidence', '')
        q9tok = value if qid == 'Q9' and value not in ('none_of_these', C.NEEDS_REVIEW) else None
        rec.update(answer=ans, value=value, top=top, p_top=p, error=err, envelope=env,
                   q17=C.q17(value, ev, text, q9tok, negative_needs_quote=self.a.backend != 'jev') if err is None else 'fail')
        self.log.write(json.dumps(rec, ensure_ascii=False) + '\n'); self.log.flush()
        if self.errors_in_row >= MAX_CONSECUTIVE_ERRORS:
            raise SystemExit(f'STOP: {MAX_CONSECUTIVE_ERRORS} errors in a row; last: {err}')
        return value, rec

    def line(self, unit):
        reg, prop = self.register, unit['property']
        res = dict(doc_id=unit['doc_id'], line_no=unit['line_no'], split=unit['split'], property=prop)
        res['q14'] = C.q14(unit)
        res['code_only'] = C.code_only(unit, reg)[0]
        recs = []
        v, r = self.ask('Q2', unit, C.line_text(unit, self.labels), 'line'); q2 = [v]; recs.append(r)
        for rm in unit['remarks']:
            v, r = self.ask('Q2', unit, C.remark_text(rm, self.labels), {'remark_role': self._role(unit, rm)}); q2.append(v); recs.append(r)
        claim = C.combined_claim(q2)
        q6 = q7 = q9 = None
        q8v = C.q8(unit['reference'], unit['description'])
        text = C.unit_text(unit, self.labels)
        if claim == 'other_authority':
            q6, r = self.ask('Q6', unit, text, 'unit'); recs.append(r)
        if claim == 'afe':
            if q8v != 'placeholder':
                q7, r = self.ask('Q7', unit, text, 'unit'); recs.append(r)
            toks = C.tokens(text)
            if toks:
                q9, r = self.ask('Q9', unit, text, 'unit', toks); recs.append(r)
            else:
                q9 = 'none_of_these'   # code: the lister found no candidate
        blocking_fail = any(r['q17'] == 'fail' for r in recs if r['qid'] in ('Q2', 'Q7', 'Q9'))
        outcome, reason = C.q16(res['q14'], blocking_fail, q2, q7, q8v, q9, reg, prop)
        res.update(q2=q2, claim=claim, q6=q6, q7=q7, q8=q8v, q9=q9, q17_fail=blocking_fail, outcome=outcome, reason=reason,
                   errors=sum(1 for r in recs if r['error']))
        return res

    def _role(self, unit, rm):
        """Oracle needs the key's remark role; live backends never see it."""
        t = self.oracle.lines[(unit['doc_id'], unit['line_no'])]
        for r in self.truth_remarks.get((unit['doc_id'], unit['line_no']), []):
            if C._squash(r['text']) == C._squash(rm['text']):
                return r['remark_role']
        return 'no_claim' if t else 'no_claim'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--smoke', action='store_true', help='synth-jobb-smoke, split smoke, oracle unless --backend')
    ap.add_argument('--corpus', default=str(DEMO / 'synth-jobb'))
    ap.add_argument('--split', choices=('calibration', 'scored', 'smoke'))
    ap.add_argument('--backend', choices=('oracle', 'claude', 'jev'), default='oracle')
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model', help='claude: exact model id (required live)')
    ap.add_argument('--jev-model', default=jev.MODEL)
    ap.add_argument('--vocab', choices=sorted(Q.VOCAB), default='standard')
    ap.add_argument('--floors', help='JSON {qid: floor}; default 0.60 each until step 3 calibrates')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--deadline-s', type=float, default=60.0, help='claude per-call timeout')
    ap.add_argument('--max-spend', type=float, default=0.05, help='jev live: hard cap, USD')
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--d283', help='jev live: the D-283 case id that approved this spend')
    ap.add_argument('--out')
    ap.add_argument('--frozen', help='frozen/FREEZE.json: verify every hash and use the frozen floors (required for --split scored)')
    a = ap.parse_args()
    if a.frozen:
        fz = json.loads(Path(a.frozen).read_text())
        root = Path(a.frozen).resolve().parent
        bad = [f for f, h in fz['hashes'].items() if hashlib.sha256((root / f).read_bytes()).hexdigest() != h]
        if bad:
            sys.exit(f'REFUSED: frozen files changed since the freeze: {bad}')
        if a.backend in fz['floors_by_backend']:
            a.floors = str(root / fz['floors_by_backend'][a.backend])
        if a.backend == 'claude' and a.model and a.model != fz['models']['claude']:
            sys.exit(f"REFUSED: claude model {a.model} is not the frozen {fz['models']['claude']}")
    elif a.split == 'scored':
        sys.exit('REFUSED: the scored split runs only with --frozen frozen/FREEZE.json (step 3)')
    if a.smoke:
        a.corpus, a.split = str(DEMO / 'synth-jobb-smoke'), a.split or 'smoke'
    if not a.split:
        ap.error('--split is required (or --smoke)')
    if a.backend == 'oracle' and a.mode == 'live':
        ap.error('the oracle has no live mode')
    if a.backend == 'claude' and a.mode == 'live' and not a.model:
        ap.error('claude live needs --model <exact id> (pinned and logged)')
    if a.backend == 'jev' and a.mode == 'live':
        if not (a.yes and a.d283):
            ap.error('jev live is metered: it needs --yes and --d283 <case id> (D-283)')
        ok, msg = jev.key_status()
        if not ok:
            sys.exit(msg)
    if a.mode == 'dry-run' or a.backend == 'oracle':
        jev.install_socket_guard()

    corpus = Path(a.corpus)
    truth = json.loads((corpus / 'truth_b.json').read_text())
    register = json.loads((corpus / 'reference' / 'afe_register.json').read_text())
    units = U.load_units(corpus, a.split)
    if a.limit:
        units = units[:a.limit]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm = f'{a.backend}-{a.mode}-{a.split}-{a.vocab}-{stamp}'
    out = Path(a.out) if a.out else DEMO / 'runs' / 'jobb' / arm
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(frozen=a.frozen, arm=arm, corpus=str(corpus), split=a.split, backend=a.backend, mode=a.mode, vocab=a.vocab,
                model=a.model if a.backend == 'claude' else a.jev_model if a.backend == 'jev' else None,
                floors=a.floors or f'default {DEFAULT_FLOOR}', units=len(units), started=stamp, d283=a.d283,
                truth_sha256=hashlib.sha256((corpus / 'truth_b.json').read_bytes()).hexdigest())
    if a.backend == 'claude':
        meta['claude_version'] = claude_version()
        if a.mode == 'live':
            meta['claude_auth_method'] = claude_auth_method()
            hour = datetime.datetime.now().hour
            if not 7 <= hour < 18:
                print(f'WARNING: Claude-only arms run in daytime (D-293); local hour is {hour}.', file=sys.stderr)
    if a.backend == 'jev' and a.mode == 'live':
        ok, msg = jev.auth_check(os.environ[jev.KEY_ENV])
        meta['jev_auth'] = msg
        if not ok:
            sys.exit(msg)

    run = Runner(a, truth, register, out)
    run.truth_remarks = {}
    for r in truth['remarks']:
        run.truth_remarks.setdefault((r['doc_id'], r['names_line']), []).append(r)
    t0 = time.time()
    results = []
    try:
        for u in units:
            results.append(run.line(u))
    finally:
        run.log.close()
        n_calls = sum(1 for _ in open(out / 'calls.jsonl'))
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                    wall_s=round(time.time() - t0, 1), requests=n_calls, live_calls=run.calls, lines_done=len(results))
        if a.backend == 'jev':
            meta.update(bound_bytes=run.bound, spend_bound_usd=round(jev.usd(run.bound), 6),
                        spend_usd=round(run.spend, 6) if a.mode == 'live' else 0.0,
                        spend_basis='usage.input_tokens at $0.042/Mtok (docs price)' if a.mode == 'live' else 'dry-run: no call')
        if a.backend == 'claude':
            meta['claude_wall_estimate_s'] = round(n_calls * CLAUDE_S_PER_CALL, 1)
        (out / 'outcomes.json').write_text(json.dumps(results, indent=1, ensure_ascii=False) + '\n')
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps({k: meta[k] for k in meta if k not in ('corpus',)}, indent=1))
    print(f'outputs: {out}')


if __name__ == '__main__':
    main()
