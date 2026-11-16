'''Re-derive the headline point estimates with separate code (plain loops, no numpy, no
shared helpers) and compare them with out/numbers.json.

Usage: python src/verify_independent.py --models ...
'''
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', nargs='+', required=True)
    ap.add_argument('--numbers', default=os.path.join(ROOT, 'out', 'numbers.json'))
    a = ap.parse_args()
    N = json.load(open(a.numbers))
    worst = 0.0
    for m in a.models:
        rows = [json.loads(l) for l in open(os.path.join(ROOT, 'runs', m, 'trials.jsonl'), encoding='utf-8')]
        by = {}
        for r in rows:
            by[(r['arm'], r['case'], r['cond'], r['role'], r['draw'])] = r
        cases = sorted({r['case'] for r in rows})
        bases = sorted({c.rsplit('-', 1)[0] for c in cases})

        def pct(r, k):
            return r[k] * 100.0 / r['amount']

        def mean_by_base(fn):
            per_base = []
            for b in bases:
                vals = []
                for mer in 'AMB':
                    v = fn(b + '-' + mer)
                    if v is not None:
                        vals.append(v)
                if vals:
                    per_base.append(sum(vals) / len(vals))
            return sum(per_base) / len(per_base) if per_base else None

        def pair(arm, cond):
            def get(c):
                x, y = by.get((arm, c, cond, 'A', 0)), by.get((arm, c, cond, 'B', 0))
                return (x, y) if x and y else None
            return get

        checks = {}
        for arm in ('base', 'g1', 'g2'):
            for cond in ('N', 'P', 'PA'):
                get = pair(arm, cond)
                pre = arm + '.' + cond + '.'
                checks[pre + 'rg'] = mean_by_base(lambda c: (lambda p: None if p is None else pct(p[0], 'forecast') - pct(p[1], 'forecast'))(get(c)))
                checks[pre + 'zone'] = mean_by_base(lambda c: (lambda p: None if p is None else pct(p[1], 'walk_away') - pct(p[0], 'walk_away'))(get(c)))
                checks[pre + 'impasse'] = mean_by_base(lambda c: (lambda p: None if p is None else float(p[1]['walk_away'] < p[0]['walk_away']))(get(c)))
                checks[pre + 'adv'] = mean_by_base(lambda c: (lambda p: None if p is None else ((p[0]['next_step'] >= 4) + (p[1]['next_step'] >= 4)) / 2)(get(c)))

        def obs_imp(c):
            x, y = by.get(('base', c, 'ON', 'O', 0)), by.get(('base', c, 'ON', 'O', 1))
            if not (x and y):
                return None
            return ((x['highest_b'] < y['lowest_a']) + (y['highest_b'] < x['lowest_a'])) / 2
        checks['obs.impasse'] = mean_by_base(obs_imp)

        def op_rg(c):
            x, y = by.get(('base', c, 'OP', 'A', 0)), by.get(('base', c, 'OP', 'B', 0))
            return pct(x, 'forecast') - pct(y, 'forecast') if x and y else None
        checks['op.rg'] = mean_by_base(op_rg)
        for k, v in checks.items():
            ref = N['metrics'].get(k, {}).get(m, {}).get('est')
            if v is None or ref is None:
                continue
            d = abs(v - ref)
            worst = max(worst, d)
            if d > 0.002:
                print('MISMATCH', m, k, round(v, 4), ref)
    print('largest difference between the two derivations:', round(worst, 5))


if __name__ == '__main__':
    main()
