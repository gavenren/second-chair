'''Dispute cases: parse data/disputes.txt and build the 72 cases (24 bases x 3 merit versions).'''
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NL = chr(10)
MERITS = ('A', 'M', 'B')  # decisive fact favours A, mixed, favours B


def load_bases(path: str | None = None) -> list[dict]:
    path = path or os.path.join(ROOT, 'data', 'disputes.txt')
    bases, cur = [], None
    for line in open(path, encoding='utf-8'):
        line = line.rstrip(NL)
        if not line.strip() or line.startswith('#'):
            continue
        if line.startswith('=='):
            bid, domain, amount = [x.strip() for x in line[2:].split('|')]
            cur = {'id': bid, 'domain': domain, 'amount': int(amount)}
            bases.append(cur)
            continue
        key, _, val = line.partition(':')
        key, val = key.strip(), val.strip()
        if key in ('A', 'B'):
            name, role, rel = [x.strip() for x in val.split('|')]
            cur[key.lower()] = {'name': name, 'role': role, 'rel': rel}
        else:
            cur[key] = val
    for i, b in enumerate(bases):
        b['index'] = i
        for k in ('a', 'b', 'STAKE', 'BG', 'A1', 'A2', 'B1', 'B2', 'DA', 'DB', 'DM'):
            assert k in b, (b['id'], k)
    assert len({b['id'] for b in bases}) == len(bases)
    return bases


def money(n: int) -> str:
    return f'{n:,}'


def neutral_file(base: dict, merit: str) -> str:
    '''The agreed summary: background, the four ordinary facts, the decisive fact.

    The order of the ordinary facts alternates between bases (A first or B first) and
    is the same whoever reads the file.'''
    order = ('A1', 'B1', 'A2', 'B2') if base['index'] % 2 == 0 else ('B1', 'A1', 'B2', 'A2')
    lines = [base['BG']] + ['- ' + base[k] for k in order] + ['- ' + base['D' + merit]]
    return NL.join(lines)


def build_cases(bases: list[dict] | None = None) -> list[dict]:
    '''Cases in run order: three rounds over the bases, with the merit version rotating,
    so that any prefix of the list is balanced across bases and merit versions.'''
    bases = bases or load_bases()
    cases = []
    for r in range(3):
        for b in bases:
            merit = MERITS[(b['index'] + r) % 3]
            cases.append({
                'case': f'{b["id"]}-{merit}', 'base': b['id'], 'merit': merit, 'domain': b['domain'],
                'amount': b['amount'], 'a': b['a'], 'b': b['b'], 'stake': b['STAKE'],
                'file': neutral_file(b, merit), 'order': len(cases),
            })
    return cases


def account_spec(base: dict, merit: str, side: str) -> dict:
    '''Which facts a party states, plays down and leaves out in their own account.

    A party states its own two facts in full, plays down the first of the other party's
    facts and leaves out the second. The decisive fact is stated in full if it favours the
    party or is mixed, and played down if it favours the other party.'''
    own, opp = ('A', 'B') if side == 'A' else ('B', 'A')
    full = [base[own + '1'], base[own + '2']]
    doubt = [base[opp + '1']]
    omit = [base[opp + '2']]
    dec = base['D' + merit]
    if merit == opp:
        doubt.append(dec)
    else:
        full.append(dec)
    return {'full': full, 'doubt': doubt, 'omit': omit}


if __name__ == '__main__':
    cs = build_cases()
    print(len(cs), 'cases;', len({c['base'] for c in cs}), 'bases')
    print(cs[0]['file'])
