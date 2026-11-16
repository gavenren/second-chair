'''Run the dispute-advice trials on hosted models through the Adaption Responses API.

One trial = one conversation: the first message (who is asking, and what they were told),
the model's free-text advice, then a follow-up asking for four numbers.

Arms
  base  no system prompt
  g1    a one-paragraph system prompt asking the model to consider the other side first
  g2    Second Chair: (1) the model rewrites the user's message as a neutral case note that
        does not say who is asking, (2) a fresh call assesses the note without knowing who
        will read the assessment, (3) the advice call gets that assessment in its system prompt

Conditions (cond, role)
  N   the party (A or B) asks, quoting the summary both parties agree on
  P   the party asks, giving its own account
  PA  as P, with one angry sentence added before the question
  ON  a neutral helper asks about the agreed summary (two independent draws)
  OP  a neutral helper asks about one party's account (role says whose)

Usage: python src/run.py --models gemma-4-31b-it deepseek-v4-flash --arms base --n-cases 72
'''
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from cases import ROOT, build_cases
from client import Client, parse_json, to_number
from prompts import T, elicit, first_turn, keys_for, parties

NL = chr(10)
BASE_PLAN = [('N', 'A', 0), ('N', 'B', 0), ('P', 'A', 0), ('P', 'B', 0), ('PA', 'A', 0), ('PA', 'B', 0),
             ('ON', 'O', 0), ('ON', 'O', 1), ('OP', 'A', 0), ('OP', 'B', 0)]
GUARD_PLAN = [('N', 'A', 0), ('N', 'B', 0), ('PA', 'A', 0), ('PA', 'B', 0)]


def parse_fields(text: str | None, cond: str, amount: int) -> dict | None:
    obj = parse_json(text)
    if obj is None:
        return None
    out = {}
    for k in keys_for(cond):
        v = to_number(obj.get(k))
        if v is None:
            return None
        if k == 'right':
            if not 0 <= v <= 100:
                return None
        elif k == 'next_step':
            if v not in (1, 2, 3, 4, 5, 6):
                return None
            v = int(v)
        elif not 0 <= v <= amount * 1.001:
            return None
        out[k] = v
    return out


def load_accounts() -> dict:
    acc = {}
    for line in open(os.path.join(ROOT, 'data', 'accounts.jsonl'), encoding='utf-8'):
        r = json.loads(line)
        acc[(r['case'], r['side'])] = r['account']
    return acc


def run_trial(cl: Client, model: str, arm: str, case: dict, cond: str, role: str, draw: int, accounts: dict) -> dict:
    tid = f'{model}|{arm}|{case["case"]}|{cond}|{role}|{draw}'
    rec = {'id': tid, 'model': model, 'arm': arm, 'case': case['case'], 'base': case['base'], 'merit': case['merit'],
           'domain': case['domain'], 'amount': case['amount'], 'cond': cond, 'role': role, 'draw': draw}
    user = first_turn(case, cond, role, accounts)
    system = None
    if arm == 'g1':
        system = T['g1_system']
    elif arm == 'g2':
        note = cl.call(model, [{'role': 'user', 'content': user}], system=T['g2_note_system'], temperature=0, max_tokens=3000)
        if not note.get('text'):
            return {**rec, 'error': 'note: ' + str(note.get('error'))}
        assess = cl.call(model, [{'role': 'user', 'content': note['text']}],
                         system=T['g2_assess_system'].format(**parties(case, 'A')), temperature=0, max_tokens=3000)
        if not assess.get('text'):
            return {**rec, 'error': 'assessment: ' + str(assess.get('error'))}
        rec['note'], rec['assessment'] = note['text'], assess['text']
        system = T['g2_advise_system'].format(assessment=assess['text'])
    adv = cl.call(model, [{'role': 'user', 'content': user}], system=system, temperature=0.7, max_tokens=4000, draw=draw)
    if not adv.get('text'):
        return {**rec, 'error': 'advice: ' + str(adv.get('error'))}
    msgs = [{'role': 'user', 'content': user}, {'role': 'assistant', 'content': adv['text']},
            {'role': 'user', 'content': elicit(case, cond, role)}]
    amount = case['amount']
    el = cl.call(model, msgs, system=system, temperature=0, max_tokens=1500, draw=draw,
                 valid=lambda t: parse_fields(t, cond, amount) is not None, tries=4)
    fields = parse_fields(el.get('text'), cond, amount)
    if fields is None:
        return {**rec, 'advice': adv['text'], 'error': 'numbers: ' + str(el.get('error'))}
    rec.update(fields)
    rec.update({'advice': adv['text'], 'advice_words': len(adv['text'].split()), 'numbers_raw': el['text'],
                'tokens_out': (adv.get('out') or 0) + (el.get('out') or 0)})
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', nargs='+', required=True)
    ap.add_argument('--arms', nargs='+', default=['base'])
    ap.add_argument('--n-cases', type=int, default=72)
    ap.add_argument('--first-case', type=int, default=0)
    ap.add_argument('--workers', type=int, default=10)
    ap.add_argument('--per-minute', type=float, default=46)
    ap.add_argument('--out', default=os.path.join(ROOT, 'runs'))
    ap.add_argument('--effort', default='none', help='reasoning effort; the word default leaves the platform default')
    a = ap.parse_args()
    cases = build_cases()[a.first_case: a.n_cases]
    accounts = load_accounts()
    cl = Client(os.path.join(a.out, 'cache'), a.per_minute, None if a.effort == 'default' else a.effort)
    done = set()
    for m in a.models:
        os.makedirs(os.path.join(a.out, m), exist_ok=True)
        p = os.path.join(a.out, m, 'trials.jsonl')
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                r = json.loads(line)
                if 'error' not in r:
                    done.add(r['id'])
    jobs = []
    for arm in a.arms:
        for case in cases:
            for m in a.models:
                for cond, role, draw in (BASE_PLAN if arm == 'base' else GUARD_PLAN):
                    if f'{m}|{arm}|{case["case"]}|{cond}|{role}|{draw}' not in done:
                        jobs.append((m, arm, case, cond, role, draw))
    print(f'{len(jobs)} trials to run ({len(done)} already done)', flush=True)
    lock, t0, n_ok, n_err = threading.Lock(), time.time(), 0, 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run_trial, cl, m, arm, case, cond, role, draw, accounts) for m, arm, case, cond, role, draw in jobs]
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            with lock:
                if 'error' in r:
                    n_err += 1
                    path = os.path.join(a.out, r['model'], 'errors.jsonl')
                else:
                    n_ok += 1
                    path = os.path.join(a.out, r['model'], 'trials.jsonl')
                with open(path, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(r, ensure_ascii=False) + NL)
            if (i + 1) % 50 == 0 or i + 1 == len(futs):
                print(f'{time.strftime("%H:%M")} {i + 1}/{len(futs)} ok {n_ok} err {n_err} '
                      f'{(time.time() - t0) / 60:.1f} min {json.dumps(cl.stats)}', flush=True)


if __name__ == '__main__':
    main()
