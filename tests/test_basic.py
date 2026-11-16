import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cases import MERITS, account_spec, build_cases, load_bases  # noqa: E402
from client import parse_json, to_number  # noqa: E402
from prompts import T, angry_line, elicit, first_turn  # noqa: E402
from run import BASE_PLAN, parse_fields  # noqa: E402
from judge import parse_codes  # noqa: E402

BASES = load_bases()
CASES = build_cases(BASES)


def test_bases_complete():
    assert len(BASES) == 24
    for b in BASES:
        assert b['a']['name'] != b['b']['name']
        assert f'{b["amount"]:,}' in b['BG'], b['id']          # the disputed amount appears in the background
        for k in ('BG', 'A1', 'A2', 'B1', 'B2', 'DA', 'DB', 'DM'):
            assert chr(34) not in b[k] and b[k].endswith('.'), (b['id'], k)


def test_cases_balanced():
    assert len(CASES) == 72 and len({c['case'] for c in CASES}) == 72
    for k in (24, 48, 72):                                        # every prefix of 24 is balanced
        block = CASES[k - 24:k]
        assert len({c['base'] for c in block}) == 24
        assert sorted(c['merit'] for c in block) == sorted(list(MERITS) * 8)


def test_file_is_the_same_for_both_parties():
    acc = {(c['case'], s): 'ACCOUNT ' + s for c in CASES for s in 'AB'}
    for c in CASES[:10]:
        a, b = first_turn(c, 'N', 'A', acc), first_turn(c, 'N', 'B', acc)
        assert c['file'] in a and c['file'] in b
        assert a.startswith('I' + chr(39) + 'm ' + c['a']['name']) and b.startswith('I' + chr(39) + 'm ' + c['b']['name'])
        # the numbers question is word-for-word the same for both parties except the walk-away line
        ea, eb = elicit(c, 'N', 'A').split(chr(10)), elicit(c, 'N', 'B').split(chr(10))
        diff = [i for i, (x, y) in enumerate(zip(ea, eb)) if x != y]
        assert len(ea) == len(eb) and all(ea[i].startswith('- walk_away') or ea[i].startswith('- next_step') for i in diff)


def test_angry_differs_only_by_one_sentence():
    acc = {(c['case'], s): 'ACCOUNT ' + s for c in CASES for s in 'AB'}
    for c in CASES[:10]:
        for s in 'AB':
            p, pa = first_turn(c, 'P', s, acc), first_turn(c, 'PA', s, acc)
            assert pa.replace(angry_line(c, s) + ' ', '') == p


def test_account_spec():
    b = BASES[0]
    for merit in MERITS:
        for side, opp in (('A', 'B'), ('B', 'A')):
            sp = account_spec(b, merit, side)
            assert b[side + '1'] in sp['full'] and b[side + '2'] in sp['full']
            assert sp['omit'] == [b[opp + '2']] and b[opp + '1'] in sp['doubt']
            dec = b['D' + merit]
            assert (dec in sp['doubt']) == (merit == opp) and (dec in sp['full']) == (merit != opp)


def test_parse_fields():
    ok = '{' + chr(34) + 'forecast' + chr(34) + ': 900, ' + chr(34) + 'walk_away' + chr(34) + ': ' + chr(34) + '$1,200' + chr(34) + ', ' + chr(34) + 'right' + chr(34) + ': 60, ' + chr(34) + 'next_step' + chr(34) + ': 2}'
    assert parse_fields('Here you go: ' + ok, 'N', 1800) == {'forecast': 900.0, 'walk_away': 1200.0, 'right': 60.0, 'next_step': 2}
    assert parse_fields(ok, 'N', 1000) is None                    # walk-away above the amount in dispute
    assert parse_fields(ok.replace('2}', '7}'), 'N', 1800) is None
    assert parse_fields('no json', 'N', 1800) is None and parse_fields(ok, 'ON', 1800) is None
    assert to_number('45%') == 45 and to_number(True) is None and parse_json('x') is None


def test_parse_codes():
    q = chr(34)
    good = '{' + ', '.join(f'{q}{k}{q}: {v}' for k, v in (('step', 4), ('validates', 2), ('other_view', 0), ('one_sided', 1), ('concede', 0), ('threat', 1))) + '}'
    assert parse_codes(good)['step'] == 4
    assert parse_codes(good.replace(': 4', ': 9')) is None


def test_plan():
    assert len(BASE_PLAN) == 10 and len(set(BASE_PLAN)) == 10
    assert all(k in T for k in ('g1_system', 'g2_note_system', 'g2_assess_system', 'g2_advise_system', 'judge_user'))
