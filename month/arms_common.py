"""Shared parts of the step 6 comparison arms A, B and C (publishing 03-full-month-brief.md §4).

Every arm writes the same outputs as arm D, so `score_month.py` scores all four unchanged:
  <out>/meta.json, <out>/m<k>/outcomes.json (one row per line: doc_id, line_no, disposition, money, reasons).
"hold" means the line goes to a person; the person (the answer key) then decides it correctly.

Fairness choices (each favours the comparison arm, never arm D):
  - Line enumeration and the arithmetic check read the PDFs with BOTH format maps (A and B) from month 1, so no
    comparison arm loses lines to the month 4 drift. Arm D gets format B only when the person adds it.
  - Arms B and C get the same written policy (POLICY), which states in words what the key holds.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(DEMO / 'jobb')); sys.path.insert(0, str(DEMO / 'typed'))
import munits as MU  # noqa: E402

REF_FILES = ('doi', 'contract_rates', 'afe_register', 'elections', 'joa_terms', 'properties')
ISSUES = {
    'none': 'No issue: the line can be posted.',
    'wrong_decimal': "The printed owner decimal differs from the division order in force on the service date.",
    'wrong_rate': 'The unit rate differs from the contract rate in force for that vendor and service on the service date.',
    'nonconsent_property': 'The property is one where the owner elected non-consent before the service date.',
    'afe_overrun': 'The cumulative gross billed to the AFE this line is coded to, in billing order across all months, '
                   'passes the approved amount times (1 + the JOA tolerance).',
    'duplicate': 'Same vendor, same invoice number and same gross as a line already billed in this or an earlier month '
                 '(the later line is the duplicate).',
    'date_window': "The service date is after the billing month's end, or more than the JOA exception window before it.",
    'claim_unsupported': 'The line or its remark claims AFE approval, and the AFE register does not support it: a stand-in '
                         'instead of a number (N/A, TBD, to follow), no number at all, a number not in the register, or an '
                         'AFE for a different property.',
    'claim_contradicted': 'The line claims AFE approval and the register shows that AFE as declined.',
    'claim_other_authority': 'The line claims authority other than an AFE: an emergency, a service contract, an operating '
                             'agreement clause, a prior election, a verbal or informal approval, or an operator policy.',
}
HOLD_ISSUES = set(ISSUES) - {'none'}
POLICY = (
    'You review a joint-interest billing month for a non-operating owner. Hold a line for a person when any of these '
    'apply; post it otherwise:\n'
    + '\n'.join(f'- {k}: {v}' for k, v in ISSUES.items() if k != 'none')
    + '\nAn AFE claim that the register supports (the number is an approved AFE for the same property, printed in any '
    'format or reworded) is fine. Approval words inside a name or an item (for example "Approved-vendor list fee") are '
    'not a claim. A line coded to an AFE through a cost bucket, with no approval claim, still counts toward that AFE\'s '
    'cumulative total. Use the reference version in force on each line\'s service date.\n')


def load(corpus):
    corpus = Path(corpus)
    truth = json.loads((corpus / 'truth_m.json').read_text())
    ref = {k: json.loads((corpus / 'reference' / f'{k}.json').read_text()) for k in REF_FILES}
    spec = json.loads((corpus / 'case_spec_m.json').read_text())
    period = {m['month']: m['billing_period'] for m in spec['months']}
    return truth, ref, period


def all_formats():
    return json.loads((HERE / 'person_maps_B.json').read_text())


def month_lines(corpus, month):
    """Every bill line of the month, read with both format maps. -> (units, drift events left over)."""
    units, events = MU.load_month(corpus, month, all_formats())
    return sorted(units, key=lambda u: (u['doc_id'], u['line_no'])), events


def doc_text(pdf):
    """The page text a reader sees: local layout text from the clean rendering (D-286), trailing spaces cut."""
    out = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, check=True, timeout=60).stdout
    lines = [ln.rstrip() for ln in out.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def reference_block(ref):
    return '\n'.join(f'{k}.json: {json.dumps(ref[k], ensure_ascii=False, separators=(",", ":"))}' for k in REF_FILES)


LEDGER_COLS = ['doc_id', 'line_no', 'property_printed', 'vendor', 'invoice_no', 'service_date', 'reference', 'gross', 'net_amount']


def ledger_table(rows):
    """Header line plus one compact pipe row per line, in LEDGER_COLS order (the prior-ledger format)."""
    return '|'.join(LEDGER_COLS) + '\n' + '\n'.join('|'.join(str(r.get(c, '')) for c in LEDGER_COLS) for r in rows)


def prior_ledger_block(corpus, month):
    """Lines billed in earlier months (reference/prior_ledger_m<k>.json), one compact row each."""
    p = Path(corpus) / 'reference' / f'prior_ledger_m{month}.json'
    if not p.exists():
        return 'none (first month)'
    return ledger_table(json.loads(p.read_text()))


def arithmetic(u):
    """The only code check arms B and C keep: printed numbers that do not add up. -> reason or None."""
    g, d, n = u['gross'], u['owner_decimal'], u['net_amount']
    if g is None or d is None or n is None:
        return 'arithmetic:unreadable'
    if abs(round(g * d, 2) - n) > 0.011:
        return 'arithmetic:net'
    q, r = u['quantity'], u['unit_rate']
    if q is not None and r is not None and abs(round(q * r, 2) - g) > 0.011:
        return 'arithmetic:gross'
    return None


def write_month(out, month, rows):
    d = Path(out) / f'm{month}'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'outcomes.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False) + '\n')


def guard_months(months, frozen, need_freeze):
    """Months 3-6 are the scored months: a live comparison run there needs the A/B/C freeze to hash clean."""
    import hashlib
    if not any(m > 2 for m in months) or not need_freeze:
        return None
    if not frozen:
        sys.exit('REFUSED: months 3-6 run only with --frozen <freeze json>')
    fz = json.loads(Path(frozen).read_text())
    root = Path(frozen).resolve().parent
    bad = [f for f, h in fz['hashes'].items() if hashlib.sha256((root / f).read_bytes()).hexdigest() != h]
    if bad:
        sys.exit(f'REFUSED: frozen files changed since the freeze: {bad}')
    return fz


# ------------------------------------------------------------------ Claude (subscription CLI), one call

def claude_call(prompt, model, timeout, system, extra=()):
    """One isolated `claude -p` call with tools off. Errors live in the stdout envelope (headless-claude-preflight).
    -> (parsed JSON or None, envelope, error or None)."""
    import jev_backend as jev
    cmd = ['claude', '-p', '--output-format', 'json', '--tools', '', '--setting-sources', '',
           '--no-session-persistence', '--system-prompt', system, '--model', model] + list(extra)
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
        m = re.search(r'\{.*\}', text, re.S)
        if m:
            try:
                return json.loads(m.group(0)), env, None
            except ValueError:
                pass
        return None, env, 'model returned no JSON: ' + text[:200]


def served_ok(env, model):
    """Fail closed: ok only when the envelope's modelUsage is a non-empty dict whose keys are exactly {model}.
    -> (ok, served model ids)."""
    mu = env.get('modelUsage') if isinstance(env, dict) else None
    served = sorted(map(str, mu)) if isinstance(mu, dict) else []
    return isinstance(mu, dict) and set(mu) == {model}, served


def slim_env(env):
    return {k: env.get(k) for k in ('duration_ms', 'usage', 'total_cost_usd', 'modelUsage', 'num_turns') if k in env}
