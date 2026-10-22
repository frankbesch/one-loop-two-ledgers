#!/usr/bin/env python3
"""A calculator tool for arm B's tool variant: a minimal MCP server over stdio, stdlib only.

One tool, `calculate(expression)`: arithmetic on numbers with + - * / ** ( ), and the functions round, abs, min,
max, sum. Exact decimal arithmetic (no float drift). Nothing else: no names, no attributes, no file or network
access. Every call is appended to the file named by env CALC_LOG (JSON lines), so a run's tool use is auditable.
"""
import ast, json, os, sys
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 34
getcontext().rounding = ROUND_HALF_UP   # accounting rounding, as the code layer (mcode.cents)
FUNCS = {'round': lambda x, n=0: round(x, int(n)), 'abs': abs, 'min': min, 'max': max, 'sum': lambda *a: sum(a, Decimal(0))}
OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
       ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b}


def ev(n):
    if isinstance(n, ast.Expression):
        return ev(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return Decimal(str(n.value))
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        return OPS[type(n.op)](ev(n.left), ev(n.right))
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        v = ev(n.operand)
        return -v if isinstance(n.op, ast.USub) else v
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and not n.keywords:
        return FUNCS[n.func.id](*[ev(a) for a in n.args])
    if isinstance(n, (ast.List, ast.Tuple)):
        raise ValueError('lists are not supported; pass numbers as arguments')
    raise ValueError(f'unsupported element: {type(n).__name__}')


def calculate(expr):
    if len(expr) > 20000:
        raise ValueError('expression too long')
    v = ev(ast.parse(expr.replace(',', '') if expr.count(',') and '(' not in expr else expr, mode='eval'))
    return format(v.normalize(), 'f') if v == v.to_integral() else str(v)


TOOL = {'name': 'calculate',
        'description': 'Evaluate an arithmetic expression exactly. Supports + - * / ** ( ) and round(x, n), abs, '
                       'min, max, sum(a, b, ...). Example: round(1234.56 * 0.0875, 2)',
        'inputSchema': {'type': 'object', 'properties': {'expression': {'type': 'string'}}, 'required': ['expression']}}


def reply(i, result=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': i}
    msg.update({'error': error} if error else {'result': result})
    sys.stdout.write(json.dumps(msg) + '\n'); sys.stdout.flush()


def main():
    log = os.environ.get('CALC_LOG')
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except ValueError:
            continue
        i, m = req.get('id'), req.get('method')
        if i is None:
            continue                                   # a notification
        if m == 'initialize':
            reply(i, {'protocolVersion': req.get('params', {}).get('protocolVersion', '2025-06-18'),
                      'capabilities': {'tools': {}}, 'serverInfo': {'name': 'calc', 'version': '1.0'}})
        elif m == 'tools/list':
            reply(i, {'tools': [TOOL]})
        elif m == 'tools/call':
            expr = (req.get('params', {}).get('arguments') or {}).get('expression', '')
            try:
                out, err = calculate(str(expr)), False
            except Exception as e:                      # noqa: BLE001  (any bad expression is an error result)
                out, err = f'error: {e}', True
            if log:
                with open(log, 'a') as f:
                    f.write(json.dumps({'expression': expr, 'result': out, 'error': err}) + '\n')
            reply(i, {'content': [{'type': 'text', 'text': out}], 'isError': err})
        elif m == 'ping':
            reply(i, {})
        else:
            reply(i, error={'code': -32601, 'message': f'method not found: {m}'})


if __name__ == '__main__':
    main()
