'''Write each party's own account of each case with a hosted model, and check it.

For every case and party the writer model gets the facts the party states in full, the
facts it plays down and the fact it leaves out (cases.account_spec). A second model then
reads the account and reports, fact by fact, whether it is stated in full, played down or
absent, and whether the account adds a new fact. Accounts that fail are written again.

Usage: python src/make_accounts.py [--writer glm-5.2] [--checker qwen3.5-397b]
'''
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor

from cases import ROOT, account_spec, build_cases, load_bases
from client import Client, parse_json
from prompts import T, parties

NL = chr(10)


def bullets(xs: list[str]) -> str:
    return NL.join('- ' + x for x in xs)


def check(cl: Client, checker: str, base: dict, case: dict, side: str, account: str, spec: dict) -> dict:
    points = spec['full'] + spec['doubt'] + spec['omit']
    want = ['FULL'] * len(spec['full']) + ['DOUBT'] * len(spec['doubt']) + ['ABSENT'] * len(spec['omit'])
    p = parties(case, side)
    msg = T['check_user'].format(bg=base['BG'], account=account, points=NL.join(f'{i + 1}. {x}' for i, x in enumerate(points)), **p)
    r = cl.call(checker, [{'role': 'user', 'content': msg}], temperature=0, max_tokens=8000,
                valid=lambda t: isinstance((parse_json(t) or {}).get('points'), list))
    obj = parse_json(r.get('text')) or {}
    got = [str(x).upper() for x in obj.get('points', [])]
    problems = []
    if len(got) != len(want):
        problems.append('checker returned the wrong number of labels')
    else:
        for i, (g, w) in enumerate(zip(got, want)):
            # a played-down fact stated in full, or the reverse, is tolerated; what must hold is
            # that stated facts are present and the left-out fact is absent
            if w == 'ABSENT' and g != 'ABSENT':
                problems.append(f'point {i + 1} should be absent')
            if w != 'ABSENT' and g == 'ABSENT':
                problems.append(f'point {i + 1} is missing')
            if w == 'FULL' and g == 'DOUBT':
                problems.append(f'point {i + 1} should be stated in full')
    if str(obj.get('new', '')).upper().startswith('Y'):
        problems.append('adds a new fact')
    return {'labels': got, 'want': want, 'problems': problems}


def make_one(cl: Client, a, base: dict, case: dict, side: str) -> dict:
    spec = account_spec(base, case['merit'], side)
    p = parties(case, side)
    msg = T['account_user'].format(bg=base['BG'], own=bullets(spec['full']), downplay=bullets(spec['doubt']), omit=bullets(spec['omit']), **p)
    best = None
    for draw in range(a.max_tries):
        r = cl.call(a.writer, [{'role': 'user', 'content': msg}], system=T['account_system'], temperature=0.7,
                    max_tokens=1500, draw=draw, valid=lambda t: 90 <= len(t.split()) <= 260)
        account = (r.get('text') or '').strip()
        if not account:
            continue
        res = check(cl, a.checker, base, case, side, account, spec)
        rec = {'case': case['case'], 'side': side, 'account': account, 'words': len(account.split()), 'draw': draw,
               'labels': res['labels'], 'want': res['want'], 'problems': res['problems']}
        if best is None or len(rec['problems']) < len(best['problems']):
            best = rec
        if not res['problems']:
            break
    return best or {'case': case['case'], 'side': side, 'account': None, 'problems': ['no account']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--writer', default='gemma-4-31b-it')
    ap.add_argument('--checker', default='qwen3.5-397b')
    ap.add_argument('--max-tries', type=int, default=4)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'accounts.jsonl'))
    a = ap.parse_args()
    bases = {b['id']: b for b in load_bases()}
    cases = build_cases()
    if a.limit:
        cases = cases[: a.limit]
    cl = Client(os.path.join(ROOT, 'runs', 'cache_accounts'), effort=None)  # the accounts were written at the platform default
    jobs = [(c, s) for c in cases for s in ('A', 'B')]
    with ThreadPoolExecutor(a.workers) as ex:
        recs = list(ex.map(lambda j: make_one(cl, a, bases[j[0]['base']], j[0], j[1]), jobs))
    with open(a.out, 'w', encoding='utf-8') as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + NL)
    bad = [r for r in recs if r['problems']]
    print(json.dumps({'accounts': len(recs), 'with_problems': len(bad), 'stats': cl.stats}))
    for r in bad:
        print(r['case'], r['side'], r['problems'])


if __name__ == '__main__':
    main()
