#!/usr/bin/env python3
"""Step 6 arm B, one agent decides everything: Claude reads each month's packet with the reference data and
lists every line to hold. No typed questions, no code rules, no floors.

  arm_b.py --months 1 2 --backend oracle                                     harness proof (perfect agent)
  arm_b.py --months 1 --backend claude --mode live --model claude-sonnet-5-5  subscription (D-288), one call a month
  arm_b.py --months 3 4 5 6 --backend claude --mode live --model claude-sonnet-5-5 --frozen month/frozen/FREEZE-ABC.json
  arm_b.py --months 3 --dump-prompts                                        write the prompts only, no call
  arm_b.py --months 3 4 5 6 ... --packet packets/packets.json --size d6     packet mode: review a subset of documents

One month-evaluation per month (up to three attempts). The prompt carries: the written policy (arms_common.POLICY, the same words arm C gets), the
reference files, the lines billed in earlier months (reference/prior_ledger_m<k>.json, the ledger any reviewer
has), and the month's documents as local layout text from the clean renderings (D-286). The agent returns the
lines to hold; every other line posts. Code only maps its list onto the month's lines (read with both format
maps) and records what it named that is not a line. A failed call is retried twice, then the month fails
closed: every line goes to a person, and the run says so.
F3 (Frank, 10-08): all six months; cloud credit where it makes sense, else the subscription. Six calls a month
of about 90k tokens each fit the subscription, so the default is a local run.

Packet mode (--packet <packets json> --size <tag>, publishing 18-packet-size-preregistration.md): the call sees only
the packet's documents as documents. The month's other lines go into the ledger block under their own header, so
duplicate and AFE-total checks still see them. Outcomes, failed-closed rows and the score cover packet lines only.
When the packet is the whole month, the prompt is byte-identical to the non-packet prompt.
Void and fail-closed: an attempt whose envelope has no modelUsage naming exactly the pinned model (another or a mixed
model, a timeout, no result event, an auth failure, any error envelope without model metadata), an error envelope
from the pinned model that is neither a malformed reply nor a transient API error (429, 529, overloaded, rate limit), or (worksheet-calc) an init block without the calc server
connected, voids the run-set (VOID.txt, calls.jsonl record, meta.json, exit 6, no retry). Only a malformed reply from
exactly the pinned model (no JSON, no exceptions list) is retried; after three such attempts the month fails closed,
is recorded in meta, and the run-set continues.
"""
import argparse, datetime, hashlib, json, os, re, sys, time
from pathlib import Path

import arms_common as AC

SYSTEM = 'You review one joint-interest billing month. Reply with only a JSON object, no prose, no code fence.'
SYSTEM_CALC = ('You review one joint-interest billing month. Call the calculate tool for every comparison and total, as '
               'many times as you need; then give your final reply as only a JSON object, no prose, no code fence.')
import re as _re
TRANSIENT = _re.compile(r'\b(429|529|overloaded|rate.?limit)\b', _re.I)  # pinned-model transient API errors: retry (prereg v2 §4)
MONEY = {'wrong_decimal', 'wrong_rate', 'nonconsent_property', 'afe_overrun', 'duplicate', 'date_window'}
KEY_ISSUE = {'unsupported': 'claim_unsupported', 'contradicted': 'claim_contradicted', 'other_authority': 'claim_other_authority'}


WORKSHEET = (
    'Work in two passes. First fill a worksheet with one row for EVERY billing line of every document, in document '
    'order, as one pipe-separated string: doc_id|line_no|property_no (resolve printed names through properties.json)|'
    'owner decimal in force on the service date (from doi.json, for THIS property_no)|printed decimal|contract rate in '
    'force or -|printed rate or -|election in force|AFE the line is coded to or -|that AFE\'s cumulative gross after this '
    'line, counting earlier months|earlier line it duplicates (doc:line) or -|service date inside the window yes/no|'
    'claim: none, supported, unsupported, contradicted or other_authority. Look every value up; never carry a value over '
    'from another row or another property. Then list the exceptions from the worksheet.\n')


CALC_NOTE = ('You have one tool, calculate, which evaluates arithmetic exactly. Use it for every number you compare or '
             'compute: each decimal and rate comparison, rate times quantity, owner net, each AFE cumulative total, and '
             'the date window. Do not do arithmetic in your head.\n')


OUTSIDE_HEADER = ('Other lines billed this month, not in this packet (not part of this review\'s worksheet or exceptions; '
                  'listed so duplicate and AFE-total checks can see them). Billing order within the month is by document id, '
                  'then line number, across the packet documents and this list together:')


def month_docs(corpus, month):
    return sorted((Path(corpus) / 'clean').glob(f'm{month}_*.pdf'))


def load_packets(path, size, months, corpus):
    """-> (raw bytes, {month: sorted doc ids}). Exits on a missing size or month, or a doc id not in the month."""
    raw = Path(path).read_bytes()
    sizes = json.loads(raw).get('sizes') or {}
    if size not in sizes:
        sys.exit(f'packet file {path}: size {size!r} not found; sizes are {sorted(sizes)}')
    out = {}
    for m in months:
        ids = sizes[size].get(f'm{m}')
        if not ids:
            sys.exit(f'packet file {path}: size {size} has no documents for m{m}')
        have = {p.stem for p in month_docs(corpus, m)}
        missing = sorted(set(map(str, ids)) - have)
        if missing:
            sys.exit(f'packet file {path}: size {size} m{m} lists documents not among the month\'s clean PDFs: {missing}')
        out[m] = sorted(set(map(str, ids)))
    return raw, out


def outside_block(units, packet):
    """The month's lines on documents outside the packet, in the prior-ledger row format; '' when there are none."""
    rest = [u for u in units if u['doc_id'] not in packet]
    return ('\n\n' + OUTSIDE_HEADER + '\n' + AC.ledger_table(rest)) if rest else ''


def prompt_for(corpus, month, period, ref, variant='v1', packet=None, outside=''):
    docs = month_docs(corpus, month)
    if packet is not None:
        docs = [p for p in docs if p.stem in packet]
    body = '\n\n'.join(f'==== Document {p.stem} ====\n{AC.doc_text(p)}' for p in docs)
    issues = sorted(AC.HOLD_ISSUES | {'needs_review'})
    return (AC.POLICY
            + '\nneeds_review: use it for a line you cannot decide from the text.\n'
            + f'\nBilling month under review: {period} (month {month}).\n'
            + '\nReference data (each row applies from its effective or approved date):\n' + AC.reference_block(ref)
            + '\n\nLines billed in earlier months (pipe-separated):\n' + AC.prior_ledger_block(corpus, month) + outside
            + ('\n\n' + WORKSHEET if variant.startswith('worksheet') else '')
            + ('\n' + CALC_NOTE if variant.endswith('calc') else '')
            + ('\n\nReturn {"worksheet": [<one string per line>], "exceptions": [{"doc_id": <document id>' if variant.startswith('worksheet')
               else '\n\nReturn {"exceptions": [{"doc_id": <document id>')
            + ', "line_no": <line number on that document>, '
            f'"issue": <one of {json.dumps(issues)}>, "evidence": <exact words from the document>, '
            '"dollars_at_stake": <owner net dollars at risk>}]}. List every line to hold, once, with its main issue. '
            'Lines you do not list are posted.\n\n'
            f"This month's documents ({len(docs)}):\n\n{body}")


def calc_log_name(month, attempt):
    return f'calc-m{month}-a{attempt}.jsonl'


def calc_args(out, month, attempt):
    """The calculator MCP server for one attempt of one month's call; every tool call is logged to
    calc-m<k>-a<attempt>.jsonl in the run folder, so a retry never mixes its calls with an earlier attempt's."""
    cfg = Path(out).resolve() / f'calc-mcp-m{month}-a{attempt}.json'
    cfg.write_text(json.dumps({'mcpServers': {'calc': {'command': sys.executable, 'args': [str(Path(__file__).resolve().parent / 'calc_mcp.py')],
                                                       'env': {'CALC_LOG': str(Path(out).resolve() / calc_log_name(month, attempt))}}}}))
    return ['--mcp-config', str(cfg), '--strict-mcp-config', '--allowedTools', 'mcp__calc__calculate']


def calc_status(init, name='calc'):
    """-> the calc server's status in the stream's init event, None when init has no entry for it."""
    servers = init.get('mcp_servers') if isinstance(init, dict) else None
    for sv in servers if isinstance(servers, list) else []:
        if isinstance(sv, dict) and sv.get('name') == name:
            return sv.get('status')
    return None


def claude_stream(prompt, model, timeout, system, extra):
    """claude -p with stream-json, for the tool variant: keeps the init event (tools offered, MCP status) and counts
    tool calls, so a call where the tool was offered but unused is visible. -> (answer, envelope, error)."""
    import os, re, subprocess, time as _t
    import jev_backend as jev
    cmd = ['claude', '-p', '--output-format', 'stream-json', '--verbose', '--tools', '', '--setting-sources', '',
           '--no-session-persistence', '--system-prompt', system, '--model', model] + list(extra)
    t0 = _t.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                              env={k: v for k, v in os.environ.items() if k != jev.KEY_ENV}, cwd='/')
    except subprocess.TimeoutExpired as ex:
        part = ex.stdout
        if isinstance(part, bytes):
            part = part.decode('utf-8', 'replace')
        return None, {'duration_ms': int((_t.time() - t0) * 1000), 'partial_stdout': (part or '')[-2000:]}, f'timeout after {timeout}s'
    init, res, uses = {}, None, 0
    for line in proc.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('type') == 'system' and e.get('subtype') == 'init':
            init = {'tools': e.get('tools'), 'mcp_servers': e.get('mcp_servers')}
        elif e.get('type') == 'assistant':
            uses += sum(1 for c in (e.get('message') or {}).get('content') or [] if c.get('type') == 'tool_use')
        elif e.get('type') == 'result':
            res = e
    if res is None:
        return None, {'init': init, 'stderr': proc.stderr[-300:]}, f'no result event (exit {proc.returncode})'
    env = dict(res, init=init, tool_uses=uses)
    if res.get('is_error'):
        return None, env, str(res.get('result'))
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', (res.get('result') or '').strip())
    m = re.search(r'\{.*\}', text, re.S)
    try:
        return json.loads(m.group(0) if m else text), env, None
    except ValueError:
        return None, env, 'model returned no JSON: ' + text[:200]


def oracle(truth, month):
    ex = []
    for t in truth['lines']:
        if t['month'] == month and t['disposition'] == 'hold':
            issue = t['money_error'] if t['money_error'] != 'none' else KEY_ISSUE[t['outcome']]
            ex.append(dict(doc_id=t['doc_id'], line_no=t['line_no'], issue=issue, evidence='', dollars_at_stake=t['error_dollars']))
    return {'exceptions': ex}


def line_no_of(v):
    """A line number only as an int (not a bool) or a string of ASCII digits; anything else -> None, never coerced."""
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    if isinstance(v, str) and re.fullmatch(r'[0-9]+', v):
        return int(v)
    return None


def has_exceptions(ans):
    return isinstance(ans, dict) and isinstance(ans.get('exceptions'), list)


def worksheet_coverage(ws, units):
    """Worksheet rows against the units in scope, keyed on each row's first two pipe fields (doc_id, line_no int).
    -> the five calls.jsonl fields; all None when the answer has no worksheet list."""
    if not isinstance(ws, list):
        return dict(worksheet_rows=None, worksheet_unparsed=None, worksheet_dupes=None, worksheet_missing=None,
                    worksheet_extra=None)
    seen, unparsed, dupes = set(), 0, 0
    for row in ws:
        f = row.split('|') if isinstance(row, str) else []
        ln = line_no_of(f[1].strip()) if len(f) >= 2 else None
        if ln is None or not f[0].strip():
            unparsed += 1; continue
        k = (f[0].strip(), ln)
        if k in seen:
            dupes += 1
        seen.add(k)
    scope = {(u['doc_id'], u['line_no']) for u in units}
    return dict(worksheet_rows=len(ws), worksheet_unparsed=unparsed, worksheet_dupes=dupes,
                worksheet_missing=[list(k) for k in sorted(scope - seen)], worksheet_extra=[list(k) for k in sorted(seen - scope)])


def to_rows(month, units, ans):
    """-> (rows, named-but-not-a-line, malformed entries)."""
    want = {}
    bad, unknown = [], []
    for e in ans['exceptions'] if has_exceptions(ans) else []:
        try:
            ln = line_no_of(e['line_no'])
            if ln is None:
                raise ValueError('line_no')
            k = (str(e['doc_id']).strip(), ln)
        except (KeyError, TypeError, ValueError):
            bad.append(e); continue
        want.setdefault(k, []).append(str(e.get('issue', 'needs_review')))
    keys = {(u['doc_id'], u['line_no']) for u in units}
    unknown = [dict(doc_id=k[0], line_no=k[1], issues=v) for k, v in want.items() if k not in keys]
    rows = []
    for u in units:
        iss = want.get((u['doc_id'], u['line_no']), [])
        rows.append(dict(month=month, doc_id=u['doc_id'], line_no=u['line_no'], format=u['format'],
                         disposition='hold' if iss else 'post', money=[i for i in iss if i in MONEY],
                         reasons=['agent:' + i for i in iss]))
    return rows, unknown, bad


def freeze_binding(frozen, packet, corpus):
    """Problems binding --packet and --corpus to the freeze manifest; [] when both are bound. The packet must be the
    manifest entry ending packets/packets.json; the corpus must be the folder of the entry ending truth_m.json."""
    fz = json.loads(Path(frozen).read_text())
    root = Path(frozen).resolve().parent
    entries = [(root / f).resolve() for f in fz.get('hashes', {})]
    pk = [e for e in entries if e.as_posix().endswith('packets/packets.json')]
    tr = [e.parent for e in entries if e.as_posix().endswith('truth_m.json')]
    probs = []
    if Path(packet).resolve() not in pk:
        probs.append(f'packet {Path(packet).resolve()} is not the freeze entry {[str(e) for e in pk]}')
    if Path(corpus).resolve() not in tr:
        probs.append(f'corpus {Path(corpus).resolve()} is not the folder of the freeze entry {[str(e) for e in tr]}')
    return probs


def void(out, meta, reason, envelope):
    """An infrastructure fault: VOID.txt with the reason and the attempt's envelope summary, then exit 6 (meta.json is
    written by main's finally block). No retry."""
    meta['void'] = reason
    (Path(out) / 'VOID.txt').write_text(f'VOID: {reason}\n\nenvelope:\n{json.dumps(envelope, indent=1, default=str)}\n')
    print(f'VOID: {reason}', file=sys.stderr)
    sys.exit(6)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(AC.DEMO / 'synth-month'))
    ap.add_argument('--months', type=int, nargs='+', required=True)
    ap.add_argument('--backend', choices=('oracle', 'claude'), default='oracle')
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model')
    ap.add_argument('--deadline-s', type=float, default=1800.0)
    ap.add_argument('--frozen', help='a freeze json, e.g. frozen/FREEZE-ABC.json or frozen/FREEZE-SIZE.json (required for a live run on months 3-6)')
    ap.add_argument('--dump-prompts', action='store_true')
    ap.add_argument('--prompt-variant', choices=('v1', 'worksheet', 'worksheet-calc'), default='v1',
                    help='v1: the step 5 prompt; worksheet: a per-line lookup worksheet first (06); worksheet-calc: plus a calculator tool (07)')
    ap.add_argument('--packet', help='packet mode: a packets json ({"seed", "sizes": {<tag>: {"m<k>": [doc ids]}}}); needs --size')
    ap.add_argument('--size', help='packet mode: one key under "sizes" in the --packet file, e.g. d6 or d24; needs --packet')
    ap.add_argument('--out')
    a = ap.parse_args()
    if bool(a.packet) != bool(a.size):
        ap.error('--packet and --size go together: give both or neither')
    live = a.backend == 'claude' and a.mode == 'live'
    if a.backend == 'oracle' and a.mode == 'live':
        ap.error('the oracle has no live mode')
    if live and not a.model:
        ap.error('claude live needs --model <exact id>')
    if a.backend == 'claude' and not live and not a.dump_prompts:
        ap.error('claude dry-run has nothing to answer with: use --backend oracle, or --dump-prompts')
    AC.guard_months(a.months, a.frozen, live)
    if live and a.frozen:
        if json.loads(Path(a.frozen).read_text()).get('scratch') is True:
            sys.exit(f'REFUSED: {a.frozen} is a scratch freeze ("scratch": true); a live run needs a real freeze')
        if a.packet:
            probs = freeze_binding(a.frozen, a.packet, a.corpus)
            if probs:
                sys.exit('REFUSED: --packet/--corpus not bound to the freeze (' + '; '.join(probs) + ')')
    truth, ref, period = AC.load(a.corpus)
    packets = None
    if a.packet:
        praw, packets = load_packets(a.packet, a.size, a.months, a.corpus)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm = (f"B{'' if a.prompt_variant == 'v1' else '-' + a.prompt_variant}-{a.backend}-{a.mode}"
           f"{'-' + a.size if packets else ''}-m{''.join(map(str, a.months))}-{stamp}")
    out = Path(a.out) if a.out else AC.DEMO / 'runs' / 'month' / arm
    out.mkdir(parents=True, exist_ok=True)
    lock = out / '.owner'  # one writer per folder (prereg v2 §4): a second runner voids the folder and exits 6
    if lock.exists():
        (out / 'VOID.txt').write_text(f'second writer: folder owned by {lock.read_text().strip()}; this run pid {os.getpid()} at {stamp}\n')
        sys.exit(6)
    lock.write_text(f'pid {os.getpid()} started {stamp}\n')
    meta = dict(arm=arm, corpus=str(Path(a.corpus).resolve()), months=a.months, backend=a.backend, mode=a.mode,
                model=a.model if a.backend == 'claude' else None, frozen=a.frozen, prompt_variant=a.prompt_variant, started=stamp,
                truth_sha256=hashlib.sha256((Path(a.corpus) / 'truth_m.json').read_bytes()).hexdigest(), months_failed_closed=[])
    if packets:
        meta.update(packet_file=str(Path(a.packet).resolve()), packet_sha256=hashlib.sha256(praw).hexdigest(),
                    packet_size=a.size, packet_docs={f'm{m}': packets[m] for m in a.months}, packet_lines={})
    if live:
        from run_b import claude_version, claude_auth_method
        meta.update(claude_version=claude_version(), claude_auth_method=claude_auth_method())
    log = open(out / 'calls.jsonl', 'a')
    t0 = time.time()
    try:
        for m in a.months:
            units, left = AC.month_lines(a.corpus, m)
            if left:
                sys.exit(f'month {m}: {len(left)} documents unreadable with both format maps: {left}')
            if packets:
                pk = set(packets[m])
                prompt = prompt_for(a.corpus, m, period[m], ref, a.prompt_variant, packet=pk, outside=outside_block(units, pk))
                outside_keys = {(u['doc_id'], u['line_no']) for u in units if u['doc_id'] not in pk}
                units = [u for u in units if u['doc_id'] in pk]
                meta['packet_lines'][f'm{m}'] = len(units)
            else:
                prompt = prompt_for(a.corpus, m, period[m], ref, a.prompt_variant)
            if a.dump_prompts:
                (out / f'prompt-m{m}.txt').write_text(prompt); print(f'm{m}: {len(prompt)} chars'); continue
            rec = dict(month=m, backend=a.backend, mode=a.mode, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                       prompt_chars=len(prompt))
            if packets:
                rec.update(packet_size=a.size, packet_lines=len(units))
            ans, err, attempts = None, None, 0
            if live:
                calc = a.prompt_variant.endswith('calc')
                for attempts in range(1, 4):
                    if calc:
                        ans, env, err = claude_stream(prompt, a.model, a.deadline_s, SYSTEM_CALC, calc_args(out, m, attempts))
                    else:
                        ans, env, err = AC.claude_call(prompt, a.model, a.deadline_s, SYSTEM, ())
                    env = env if isinstance(env, dict) else {}
                    ok, served = AC.served_ok(env, a.model)
                    voids = []
                    if not ok:  # infrastructure fault, never a retry: no model metadata, or not exactly the pinned model
                        voids.append(f'served model {served} is not the pinned {a.model}' if served else
                                     f'envelope has no modelUsage naming the pinned {a.model} (error: {err or "none"})')
                    else:
                        init = env.get('init')
                        if calc and calc_status(init) != 'connected':
                            voids.append(f'calculator server status {calc_status(init)!r}, not connected'
                                         + ('' if init else ' (no init block)'))
                        if err and not (err.startswith('model returned no JSON') or err == 'no exceptions list'
                                        or TRANSIENT.search(err)):
                            voids.append(f'error envelope from the pinned model is neither malformed nor transient: {err}')
                    if not err and not voids and not has_exceptions(ans):
                        err = 'no exceptions list'
                    envl = dict(AC.slim_env(env), error=err, attempt=attempts,
                                **{k: env[k] for k in ('init', 'tool_uses', 'partial_stdout', 'stderr') if k in env})
                    if calc:
                        envl['calc_log'] = calc_log_name(m, attempts)
                    rec.setdefault('envelopes', []).append(envl)
                    if voids:
                        rec.update(void='; '.join(voids), attempts=attempts, answer=ans, error=err)
                        log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
                        void(out, meta, f'month {m} attempt {attempts}: ' + '; '.join(voids), envl)
                    if not err:
                        break
            else:
                ans = oracle(truth, m)
            if err:
                rows = [dict(month=m, doc_id=u['doc_id'], line_no=u['line_no'], format=u['format'], disposition='hold',
                             money=[], reasons=['agent:failed_closed']) for u in units]
                unknown, bad = [], []
                meta['months_failed_closed'].append(m)
            else:
                rows, unknown, bad = to_rows(m, units, ans)
            ws = ans.get('worksheet') if isinstance(ans, dict) else None
            if packets:  # names on this month's lines outside the packet are not "not a line": count them apart
                outside = [x for x in unknown if (x['doc_id'], x['line_no']) in outside_keys]
                unknown = [x for x in unknown if (x['doc_id'], x['line_no']) not in outside_keys]
                rec.update(named_outside_packet=outside)
            rec.update(answer=ans, error=err, attempts=attempts, named_not_a_line=unknown, malformed=bad,
                       **worksheet_coverage(ws, units))
            log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
            AC.write_month(out, m, rows)
            print(f"m{m}: held {sum(r['disposition'] == 'hold' for r in rows)}, not-a-line {len(unknown)}, "
                  f"malformed {len(bad)}, error {err}", flush=True)
    finally:
        log.close()
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                    wall_s=round(time.time() - t0, 1))
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(f'outputs: {out}')


if __name__ == '__main__':
    main()
