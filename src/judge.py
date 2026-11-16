'''Code the free-text advice with a judge model (data/prompts.txt: judge_user).

Codes the first reply in conditions N, P and PA (a party asking). Output:
runs/judge/<judge>/codes.jsonl with one line per coded trial.

Usage: python src/judge.py --judge deepseek-v4-flash --models ... --arms base g1 g2 [--every 1]
'''
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from cases import ROOT, build_cases
from client import Client, parse_json, to_number
from prompts import T, parties

NL = chr(10)
KEYS = {'step': (0, 1, 2, 3, 4, 5, 6), 'validates': (0, 1, 2), 'other_view': (0, 1), 'one_sided': (0, 1), 'concede': (0, 1), 'threat': (0, 1)}


def parse_codes(text: str | None) -> dict | None:
    obj = parse_json(text)
    if obj is None:
        return None
    out = {}
    for k, allowed in KEYS.items():
        v = to_number(obj.get(k))
        if v is None or v not in allowed:
            return None
        out[k] = int(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--judge', default='deepseek-v4-flash')
    ap.add_argument('--models', nargs='+', required=True)
    ap.add_argument('--arms', nargs='+', default=['base'])
    ap.add_argument('--conds', nargs='+', default=['N', 'P', 'PA'])
    ap.add_argument('--every', type=int, default=1, help='code every k-th case (in run order)')
    ap.add_argument('--workers', type=int, default=10)
    ap.add_argument('--per-minute', type=float, default=46)
    ap.add_argument('--runs', default=os.path.join(ROOT, 'runs'))
    a = ap.parse_args()
    cases = {c['case']: c for c in build_cases()}
    keep = {c for c, v in cases.items() if v['order'] % a.every == 0}
    out_dir = os.path.join(a.runs, 'judge', a.judge)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'codes.jsonl')
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)['id'] for l in open(out_path, encoding='utf-8')}
    jobs = []
    for m in a.models:
        p = os.path.join(a.runs, m, 'trials.jsonl')
        if not os.path.exists(p):
            continue
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            if r['arm'] in a.arms and r['cond'] in a.conds and r['case'] in keep and r['id'] not in done:
                jobs.append(r)
                done.add(r['id'])
    jobs.sort(key=lambda r: (a.arms.index(r['arm']), cases[r['case']]['order'], r['model']))
    print(f'{len(jobs)} replies to code', flush=True)
    cl = Client(os.path.join(a.runs, 'cache'), a.per_minute)

    def one(r):
        p = parties(cases[r['case']], r['role'])
        msg = T['judge_user'].format(advice=r['advice'], **p)
        res = cl.call(a.judge, [{'role': 'user', 'content': msg}], system=T['judge_system'], temperature=0,
                      max_tokens=1500, valid=lambda t: parse_codes(t) is not None, tries=4)
        codes = parse_codes(res.get('text'))
        return {'id': r['id'], 'judge': a.judge, **(codes or {'error': str(res.get('error'))})}

    t0, n_err = time.time(), 0
    with ThreadPoolExecutor(a.workers) as ex, open(out_path, 'a', encoding='utf-8') as fh:
        futs = [ex.submit(one, r) for r in jobs]
        for i, f in enumerate(as_completed(futs)):
            res = f.result()
            if 'error' in res:
                n_err += 1
            else:
                fh.write(json.dumps(res) + NL)
                fh.flush()
            if (i + 1) % 100 == 0 or i + 1 == len(futs):
                print(f'{time.strftime("%H:%M")} {i + 1}/{len(futs)} err {n_err} {(time.time() - t0) / 60:.1f} min', flush=True)


if __name__ == '__main__':
    main()
