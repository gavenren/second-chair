'''Compute every number in the report from the per-trial files (runs/<model>/trials.jsonl).

Shares are percentages of the disputed amount that go to party A. Intervals are 95%
percentile intervals from bootstrap resamples of the 24 base disputes; pooled estimates
give every model equal weight. Output: out/numbers.json.

Usage: python src/analyze.py --models ... [--n-boot 5000] [--judge deepseek-v4-flash]
'''
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

import numpy as np

from cases import ROOT, build_cases

ARMS = ('base', 'g1', 'g2')
CONDS = ('N', 'P', 'PA')
NAN = float('nan')


def load_trials(runs: str, models: list[str]) -> dict:
    T = {}
    for m in models:
        p = os.path.join(runs, m, 'trials.jsonl')
        if not os.path.exists(p):
            continue
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            T[(r['model'], r['arm'], r['case'], r['cond'], r['role'], r['draw'])] = r
    return T


def share(r: dict, k: str) -> float:
    return 100.0 * r[k] / r['amount']


def adv(r: dict) -> float:
    return float(r['next_step'] >= 4)


def case_row(T: dict, m: str, case: str) -> dict:
    '''All per-case quantities for one model. Keys are arm.cond.name, obs.name or op.name.'''
    row = {}
    for arm in ARMS:
        for cond in CONDS:
            a, b = T.get((m, arm, case, cond, 'A', 0)), T.get((m, arm, case, cond, 'B', 0))
            if not (a and b):
                continue
            pre = arm + '.' + cond + '.'
            fa, fb, wa, wb = share(a, 'forecast'), share(b, 'forecast'), share(a, 'walk_away'), share(b, 'walk_away')
            row[pre + 'fA'], row[pre + 'fB'], row[pre + 'wA'], row[pre + 'wB'] = fa, fb, wa, wb
            row[pre + 'rg'] = fa - fb
            row[pre + 'abs_rg'] = abs(fa - fb)
            row[pre + 'rg_pos'] = float(fa > fb)
            row[pre + 'rg_neg'] = float(fa < fb)
            row[pre + 'fmean'] = (fa + fb) / 2
            row[pre + 'right_gap'] = a['right'] - b['right']
            row[pre + 'zone'] = wb - wa
            row[pre + 'impasse'] = float(wb < wa)
            row[pre + 'adv'] = (adv(a) + adv(b)) / 2
            row[pre + 'advA'], row[pre + 'advB'] = adv(a), adv(b)
            row[pre + 'mutual'] = adv(a) * adv(b)
            row[pre + 'step'] = (a['next_step'] + b['next_step']) / 2
            row[pre + 'formal'] = (float(a['next_step'] >= 5) + float(b['next_step'] >= 5)) / 2
            row[pre + 'talk'] = (float(a['next_step'] == 2) + float(b['next_step'] == 2)) / 2
            row[pre + 'holdA'] = wa - fa      # how far above its own forecast A is told to hold out
            row[pre + 'holdB'] = fb - wb      # how far below its own forecast B is told to hold out
            row[pre + 'words'] = (a['advice_words'] + b['advice_words']) / 2
    o0, o1 = T.get((m, 'base', case, 'ON', 'O', 0)), T.get((m, 'base', case, 'ON', 'O', 1))
    if o0 and o1:
        f0, f1 = share(o0, 'forecast'), share(o1, 'forecast')
        la0, la1, hb0, hb1 = share(o0, 'lowest_a'), share(o1, 'lowest_a'), share(o0, 'highest_b'), share(o1, 'highest_b')
        row['obs.f'] = (f0 + f1) / 2
        row['obs.noise'] = abs(f0 - f1)
        row['obs.right'] = (o0['right'] + o1['right']) / 2
        # walk-away points taken from two independent replies, as they are for the two parties
        row['obs.zone'] = ((hb0 - la1) + (hb1 - la0)) / 2
        row['obs.impasse'] = (float(hb0 < la1) + float(hb1 < la0)) / 2
        row['obs.zone_same_reply'] = ((hb0 - la0) + (hb1 - la1)) / 2
        row['obs.wA'], row['obs.wB'] = (la0 + la1) / 2, (hb0 + hb1) / 2
        if 'base.N.fA' in row:
            row['base.N.tiltA'] = row['base.N.fA'] - row['obs.f']
            row['base.N.tiltB'] = row['obs.f'] - row['base.N.fB']
            row['base.N.zone_loss'] = row['obs.zone'] - row['base.N.zone']
        for arm in ARMS:
            for cond in CONDS:
                k = arm + '.' + cond + '.'
                if k + 'fA' in row:
                    # mean distance of the two forecasts from the neutral helper's forecast
                    row[k + 'err'] = (abs(row[k + 'fA'] - row['obs.f']) + abs(row[k + 'fB'] - row['obs.f'])) / 2
    pa, pb = T.get((m, 'base', case, 'OP', 'A', 0)), T.get((m, 'base', case, 'OP', 'B', 0))
    if pa and pb:
        fa, fb, wa, wb = share(pa, 'forecast'), share(pb, 'forecast'), share(pa, 'walk_away'), share(pb, 'walk_away')
        row['op.fA'], row['op.fB'] = fa, fb
        row['op.wA'], row['op.wB'] = wa, wb
        row['op.rg'] = fa - fb
        row['op.zone'] = wb - wa
        row['op.impasse'] = float(wb < wa)
        row['op.adv'] = (adv(pa) + adv(pb)) / 2
        row['op.mutual'] = adv(pa) * adv(pb)
        row['op.step'] = (pa['next_step'] + pb['next_step']) / 2
        row['op.right_gap'] = pa['right'] - pb['right']
        if 'base.P.rg' in row:
            row['base.P.address'] = row['base.P.rg'] - row['op.rg']
            row['base.P.addressA'] = row['base.P.fA'] - fa
            row['base.P.addressB'] = fb - row['base.P.fB']
            row['base.P.adv_address'] = row['base.P.adv'] - row['op.adv']
            row['base.P.zone_address'] = row['base.P.zone'] - row['op.zone']
    for cond_a, cond_b, name in (('PA', 'P', 'anger'),):
        for arm in ARMS:
            ka, kb = arm + '.' + cond_a + '.', arm + '.' + cond_b + '.'
            for q in ('adv', 'step', 'rg', 'zone', 'impasse', 'formal', 'mutual'):
                if ka + q in row and kb + q in row:
                    row[arm + '.' + name + '.' + q] = row[ka + q] - row[kb + q]
    for arm in ('g1', 'g2'):
        for cond in CONDS:
            for q in ('rg', 'abs_rg', 'zone', 'impasse', 'adv', 'mutual', 'step', 'formal', 'err', 'words'):
                ka, kb = arm + '.' + cond + '.' + q, 'base.' + cond + '.' + q
                if ka in row and kb in row:
                    row[arm + '-base.' + cond + '.' + q] = row[ka] - row[kb]
    return row


class Table:
    '''Per-case rows for every model, with bootstrap over base disputes.'''

    def __init__(self, T: dict, models: list[str], cases: list[dict], n_boot: int, seed: int = 0):
        self.models, self.cases = models, cases
        self.bases = sorted({c['base'] for c in cases})
        self.rows = {m: {c['case']: case_row(T, m, c['case']) for c in cases} for m in models}
        rng = np.random.default_rng(seed)
        self.idx = rng.integers(0, len(self.bases), (n_boot, len(self.bases)))

    def keys(self) -> list[str]:
        ks = set()
        for m in self.models:
            for r in self.rows[m].values():
                ks.update(r)
        return sorted(ks)

    def per_base(self, key: str, m: str, merit: str | None = None, domain: str | None = None) -> np.ndarray:
        '''Mean of a per-case quantity within each base (NaN where the base has no value).'''
        acc = defaultdict(list)
        for c in self.cases:
            if (merit and c['merit'] != merit) or (domain and c['domain'] != domain):
                continue
            v = self.rows[m][c['case']].get(key)
            if v is not None:
                acc[c['base']].append(v)
        return np.array([np.mean(acc[b]) if acc[b] else NAN for b in self.bases])

    def n_cases(self, key: str, m: str, merit: str | None = None) -> int:
        return sum(1 for c in self.cases if (not merit or c['merit'] == merit) and key in self.rows[m][c['case']])

    def merit_sens(self, key: str, m: str) -> np.ndarray:
        '''Value in the A-favoured version minus value in the B-favoured version, per base.'''
        return self.per_base(key, m, merit='A') - self.per_base(key, m, merit='B')

    def merit_metric(self, key: str) -> dict:
        """Mean in A-favoured versions minus mean in B-favoured versions, per model and pooled.

        Resamples bases; a base contributes whichever of its versions have been run, so the
        estimate is defined before all three rounds are complete."""
        out, As, Bs = {}, [], []
        for m in self.models:
            a, b = self.per_base(key, m, merit='A'), self.per_base(key, m, merit='B')
            As.append(a)
            Bs.append(b)
            out[m] = self._diff_of_means(a, b)
        out['pooled'] = self._diff_of_means(self.pooled(As), self.pooled(Bs))
        return out

    def _diff_of_means(self, a: np.ndarray, b: np.ndarray) -> dict:
        if np.all(np.isnan(a)) or np.all(np.isnan(b)):
            return {'est': None}
        with np.errstate(invalid='ignore'):
            boot = np.nanmean(a[self.idx], axis=1) - np.nanmean(b[self.idx], axis=1)
        lo, hi = np.nanpercentile(boot, [2.5, 97.5])
        return {'est': round(float(np.nanmean(a) - np.nanmean(b)), 3), 'lo': round(float(lo), 3), 'hi': round(float(hi), 3)}

    def summarise(self, arr: np.ndarray) -> dict:
        '''arr: per-base values (NaN allowed). Mean with a bootstrap interval.'''
        if np.all(np.isnan(arr)):
            return {'est': None}
        with np.errstate(invalid='ignore'):
            boot = np.nanmean(arr[self.idx], axis=1)
        lo, hi = np.nanpercentile(boot, [2.5, 97.5])
        return {'est': round(float(np.nanmean(arr)), 3), 'lo': round(float(lo), 3), 'hi': round(float(hi), 3),
                'n_bases': int(np.sum(~np.isnan(arr)))}

    def pooled(self, arrs: list[np.ndarray]) -> np.ndarray:
        with np.errstate(invalid='ignore'):
            return np.nanmean(np.vstack(arrs), axis=0) if arrs else np.full(len(self.bases), NAN)

    def metric(self, fn) -> dict:
        '''fn(model) -> per-base array. Returns per-model and pooled summaries.'''
        arrs = {m: fn(m) for m in self.models}
        out = {m: self.summarise(a) for m, a in arrs.items()}
        out['pooled'] = self.summarise(self.pooled([a for a in arrs.values() if not np.all(np.isnan(a))]))
        return out

    def ratio_to_merit(self, key: str, merit_key: str = 'obs.f') -> dict:
        """Mean of a per-case quantity divided by the merit sensitivity of merit_key."""
        out = {}
        nums = {m: self.per_base(key, m) for m in self.models}
        As = {m: self.per_base(merit_key, m, merit='A') for m in self.models}
        Bs = {m: self.per_base(merit_key, m, merit='B') for m in self.models}
        nums['pooled'], As['pooled'], Bs['pooled'] = self.pooled(list(nums.values())), self.pooled(list(As.values())), self.pooled(list(Bs.values()))
        for m in list(self.models) + ['pooled']:
            n, a, b = nums[m], As[m], Bs[m]
            if np.all(np.isnan(n)) or np.all(np.isnan(a)) or np.all(np.isnan(b)):
                out[m] = {'est': None}
                continue
            with np.errstate(invalid='ignore', divide='ignore'):
                boot = np.nanmean(n[self.idx], axis=1) / (np.nanmean(a[self.idx], axis=1) - np.nanmean(b[self.idx], axis=1))
            lo, hi = np.nanpercentile(boot, [2.5, 97.5])
            out[m] = {'est': round(float(np.nanmean(n) / (np.nanmean(a) - np.nanmean(b))), 3), 'lo': round(float(lo), 3), 'hi': round(float(hi), 3)}
        return out


def judge_block(T: dict, tab: Table, runs: str, judge: str, second: str | None) -> dict:
    def load(j):
        p = os.path.join(runs, 'judge', j, 'codes.jsonl')
        return {json.loads(l)['id']: json.loads(l) for l in open(p, encoding='utf-8')} if os.path.exists(p) else {}
    codes = load(judge)
    out = {'judge': judge, 'n_coded': len(codes)}
    if not codes:
        return out
    by_id = {r['id']: r for r in T.values()}
    cells = defaultdict(lambda: defaultdict(list))
    agree = {'n': 0, 'same_step': 0, 'same_adv': 0, 'both_adv': 0, 'self_adv': 0, 'coded_adv': 0}
    for tid, c in codes.items():
        r = by_id.get(tid)
        if r is None:
            continue
        cell = cells[(r['model'], r['arm'], r['cond'])]
        cell['strong'].append(float(c['validates'] == 2))
        cell['weak'].append(float(c['validates'] == 0))
        for k in ('other_view', 'one_sided', 'concede', 'threat'):
            cell[k].append(float(c[k]))
        cell['coded_adv'].append(float(c['step'] >= 4))
        cell['coded_step'].append(float(c['step']))
        agree['n'] += 1
        agree['same_step'] += int(c['step'] == r['next_step'])
        sa, ca = r['next_step'] >= 4, c['step'] >= 4
        agree['same_adv'] += int(sa == ca)
        agree['both_adv'] += int(sa and ca)
        agree['self_adv'] += int(sa)
        agree['coded_adv'] += int(ca)
    n = agree['n']
    po = agree['same_adv'] / n
    pe = (agree['self_adv'] / n) * (agree['coded_adv'] / n) + (1 - agree['self_adv'] / n) * (1 - agree['coded_adv'] / n)
    out['self_vs_coded'] = {'n': n, 'same_step': round(agree['same_step'] / n, 3), 'same_adv': round(po, 3),
                            'kappa_adv': round((po - pe) / (1 - pe), 3) if pe < 1 else None,
                            'self_adv': round(agree['self_adv'] / n, 3), 'coded_adv': round(agree['coded_adv'] / n, 3)}
    res = {}
    for arm in ARMS:
        for cond in CONDS:
            per_model = {}
            for m in tab.models:
                cell = cells.get((m, arm, cond))
                if cell:
                    per_model[m] = {k: round(float(np.mean(v)), 3) for k, v in cell.items()} | {'n': len(cell['strong'])}
            if per_model:
                ks = [k for k in next(iter(per_model.values())) if k != 'n']
                per_model['pooled'] = {k: round(float(np.mean([v[k] for v in per_model.values()])), 3) for k in ks}
                res[arm + '.' + cond] = per_model
    out['cells'] = res
    if second:
        c2 = load(second)
        both = [(codes[i], c2[i]) for i in codes if i in c2]
        if both:
            ag = {'n': len(both), 'second': second}
            for k in ('validates', 'other_view', 'one_sided', 'concede', 'threat'):
                ag[k] = round(float(np.mean([a[k] == b[k] for a, b in both])), 3)
            ag['step'] = round(float(np.mean([a['step'] == b['step'] for a, b in both])), 3)
            x = np.array([a['step'] >= 4 for a, _ in both], float)
            y = np.array([b['step'] >= 4 for _, b in both], float)
            po = float(np.mean(x == y))
            pe = float(x.mean() * y.mean() + (1 - x.mean()) * (1 - y.mean()))
            ag['adv'] = round(po, 3)
            ag['kappa_adv'] = round((po - pe) / (1 - pe), 3) if pe < 1 else None
            out['judges_agree'] = ag
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', nargs='+', required=True)
    ap.add_argument('--runs', default=os.path.join(ROOT, 'runs'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'out', 'numbers.json'))
    ap.add_argument('--n-boot', type=int, default=5000)
    ap.add_argument('--n-cases', type=int, default=72)
    ap.add_argument('--judge', default='deepseek-v4-flash')
    ap.add_argument('--second-judge', default='gemma-4-31b-it')
    a = ap.parse_args()
    cases = build_cases()[: a.n_cases]
    T = load_trials(a.runs, a.models)
    models = [m for m in a.models if any(k[0] == m for k in T)]
    tab = Table(T, models, cases, a.n_boot)
    N = {'models': models, 'n_cases': len(cases), 'n_bases': len(tab.bases), 'n_boot': a.n_boot, 'metrics': {}, 'by_merit': {}}

    counts = defaultdict(int)
    for k in T:
        counts[k[0] + '|' + k[1]] += 1
    N['trials'] = dict(counts)
    errs = {}
    for m in models:
        p = os.path.join(a.runs, m, 'errors.jsonl')
        if os.path.exists(p):
            ids = {json.loads(l)['id'] for l in open(p, encoding='utf-8')}
            done = {r['id'] for r in T.values() if r['model'] == m}
            errs[m] = len(ids - done)
    N['unresolved_errors'] = errs

    for key in tab.keys():
        N['metrics'][key] = tab.metric(lambda m, key=key: tab.per_base(key, m))
        for model in models + ['pooled']:
            if model != 'pooled':
                N['metrics'][key][model]['n_cases'] = tab.n_cases(key, model)
    merit_keys = ['obs.f', 'obs.zone', 'obs.impasse'] + [arm + '.' + c + '.' + q for arm in ARMS for c in CONDS
                                                         for q in ('rg', 'fmean', 'fA', 'fB', 'zone', 'impasse', 'adv', 'mutual', 'wA', 'wB')]
    have = set(tab.keys())
    for key in merit_keys:
        if key in have:
            N['by_merit'][key] = {mt: tab.metric(lambda m, key=key, mt=mt: tab.per_base(key, m, merit=mt)) for mt in ('A', 'M', 'B')}
    N['merit_sens'] = {}
    for key in ['obs.f'] + [arm + '.' + c + '.fmean' for arm in ARMS for c in CONDS] + ['op.fA', 'op.fB']:
        if key in have:
            N['merit_sens'][key] = tab.merit_metric(key)
    N['ratio'] = {'op.rg/merit_sens': tab.ratio_to_merit('op.rg')}
    for arm in ARMS:
        for c in CONDS:
            key = arm + '.' + c + '.rg'
            if key in have:
                N['ratio'][key + '/merit_sens'] = tab.ratio_to_merit(key)
    doms = sorted({c['domain'] for c in cases})
    N['by_domain'] = {}
    for key in ('base.N.rg', 'base.N.impasse', 'base.PA.adv', 'base.PA.rg', 'base.PA.impasse', 'obs.impasse'):
        if key in have:
            N['by_domain'][key] = {}
            for d in doms:
                arr = tab.pooled([tab.per_base(key, m, domain=d) for m in models])
                N['by_domain'][key][d] = {'est': round(float(np.nanmean(arr)), 2), 'n_bases': int(np.sum(~np.isnan(arr)))}
    steps = {}
    for (m, arm, case, cond, role, draw), r in T.items():
        if 'next_step' in r:
            for who in (m, 'pooled'):
                cell = steps.setdefault(who + '|' + arm + '|' + cond, [0] * 6)
                cell[r['next_step'] - 1] += 1
    N['steps'] = steps
    edges = list(range(-100, 101, 10))
    N['zone_hist'] = {'edges': edges}
    for key in ['obs.zone', 'op.zone'] + [arm + '.' + c + '.zone' for arm in ARMS for c in CONDS]:
        vals = [tab.rows[m][c['case']][key] for m in models for c in cases if key in tab.rows[m][c['case']]]
        if vals:
            N['zone_hist'][key] = np.histogram(np.clip(vals, -100, 99.9), bins=edges)[0].tolist()
    pts = []
    for c in cases:
        vals = [tab.rows[m][c['case']] for m in models]
        vals = [v for v in vals if 'base.N.fA' in v and 'obs.f' in v]
        if vals:
            pts.append([c['case'], round(float(np.mean([v['base.N.fA'] for v in vals])), 1),
                        round(float(np.mean([v['base.N.fB'] for v in vals])), 1), round(float(np.mean([v['obs.f'] for v in vals])), 1)])
    N['case_points'] = pts
    N['judge'] = judge_block(T, tab, a.runs, a.judge, a.second_judge)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(N, open(a.out, 'w'), separators=(',', ':'))

    def show(key, src=None):
        d = (src or N['metrics']).get(key)
        if not d:
            return
        cells = []
        for m in models + ['pooled']:
            v = d.get(m, {})
            cells.append('      n/a      ' if v.get('est') is None else f'{v["est"]:6.1f} [{v["lo"]:5.1f},{v["hi"]:5.1f}]')
        print(f'{key:26s}' + ' | '.join(cells))

    print(' ' * 26 + ' | '.join(f'{m[:19]:19s}' for m in models + ['pooled']))
    for key in ['obs.noise', 'base.N.rg', 'base.N.abs_rg', 'base.N.rg_pos', 'base.N.tiltA', 'base.N.tiltB', 'base.N.right_gap',
                'obs.zone', 'obs.zone_same_reply', 'base.N.zone', 'base.N.holdA', 'base.N.holdB', 'base.P.zone', 'base.PA.zone', 'op.zone']:
        show(key)
    for key in ['obs.impasse', 'base.N.impasse', 'base.P.impasse', 'base.PA.impasse', 'op.impasse', 'op.adv', 'base.N.adv', 'base.P.adv',
                'base.PA.adv', 'base.anger.adv', 'base.anger.step', 'base.P.mutual', 'base.PA.mutual', 'op.mutual', 'base.P.adv_address']:
        d = N['metrics'].get(key)
        if d:
            show(key, {key: {m: ({k: (v * 100 if k in ('est', 'lo', 'hi') else v) for k, v in d[m].items()} if d[m].get('est') is not None else d[m]) for m in d}})
    for key in ['base.P.rg', 'op.rg', 'base.P.address', 'base.PA.rg', 'base.anger.rg']:
        show(key)
    show('obs.f', N['merit_sens'])
    for arm in ('g1', 'g2'):
        for key in [arm + '.N.rg', arm + '.N.zone', arm + '.PA.rg', arm + '.PA.zone', arm + '-base.PA.rg']:
            show(key)
        for key in [arm + '.N.impasse', arm + '.PA.impasse', arm + '.N.adv', arm + '.PA.adv', arm + '-base.PA.adv', arm + '-base.PA.impasse']:
            d = N['metrics'].get(key)
            if d:
                show(key, {key: {m: ({k: (v * 100 if k in ('est', 'lo', 'hi') else v) for k, v in d[m].items()} if d[m].get('est') is not None else d[m]) for m in d}})
        show(arm + '.N.fmean', N['merit_sens'])
        show(arm + '.PA.fmean', N['merit_sens'])
    print(json.dumps(N['trials']))
    print(json.dumps({k: v for k, v in N['judge'].items() if k != 'cells'}))


if __name__ == '__main__':
    main()
