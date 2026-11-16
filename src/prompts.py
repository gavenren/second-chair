'''Prompt construction. All wording lives in data/prompts.txt.'''
from __future__ import annotations

import hashlib
import os

from cases import ROOT, money

NL = chr(10)
ASK = 'What should I do?'


def _load() -> dict:
    out, name, buf = {}, None, []
    for line in open(os.path.join(ROOT, 'data', 'prompts.txt'), encoding='utf-8'):
        line = line.rstrip(NL)
        if line.startswith('@@ '):
            if name:
                out[name] = NL.join(buf).strip()
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out[name] = NL.join(buf).strip()
    return out


T = _load()


def parties(case: dict, role: str) -> dict:
    a, b = case['a'], case['b']
    me, other = (a, b) if role == 'A' else (b, a)
    return {
        'a': a['name'], 'b': b['name'], 'a_role': a['role'], 'b_role': b['role'],
        'me': me['name'], 'other': other['name'], 'other_rel': other['rel'],
        'amount': money(case['amount']), 'amount_plain': str(case['amount']), 'stake': case['stake'],
    }


def angry_line(case: dict, role: str) -> str:
    '''One of four fixed angry sentences, chosen by the base so both parties get the same one.'''
    k = int(hashlib.sha1(case['base'].encode()).hexdigest(), 16) % 4
    return T[f'angry_{k}'].format(**parties(case, role))


def first_turn(case: dict, cond: str, role: str, accounts: dict | None = None) -> str:
    '''cond: N (agreed summary, party asks), P (own account), PA (own account, angry),
    ON (observer, agreed summary), OP (observer, one party's account; role says whose).'''
    if cond == 'ON':
        return T['obs_N'].format(file=case['file'], **parties(case, 'A'))
    p = parties(case, role)
    if cond == 'N':
        return T['role_N'].format(file=case['file'], **p)
    account = accounts[(case['case'], role)]
    if cond == 'OP':
        return T['obs_P'].format(account=account, **p)
    text = T['role_P'].format(account=account, **p)
    if cond == 'PA':
        assert text.endswith(ASK)
        text = text[: -len(ASK)] + angry_line(case, role) + ' ' + ASK
    return text


def elicit(case: dict, cond: str, role: str) -> str:
    if cond == 'ON':
        return T['elicit_obs_N'].format(**parties(case, 'A'))
    p = parties(case, role)
    walk = T['walk_' + role].format(**p)
    return T['elicit_obs_P' if cond == 'OP' else 'elicit_role'].format(walk=walk, **p)


def keys_for(cond: str) -> tuple:
    return ('forecast', 'lowest_a', 'highest_b', 'right') if cond == 'ON' else ('forecast', 'walk_away', 'right', 'next_step')
