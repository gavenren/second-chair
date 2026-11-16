'''Write the numbers the report uses as one compact JSON line (out/report_numbers.json),
with an MD5 so that a copy can be checked. Rates are in percent; everything else is in
percentage points of the disputed amount. p: pooled [estimate, low, high]. pm: the same
per model, in the order of the models list.

Usage: python src/export.py [--numbers out/numbers.json]
'''
import argparse
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATE = ('impasse', 'adv', 'advA', 'advB', 'mutual', 'formal', 'talk', 'rg_pos', 'rg_neg', 'adv_address')
Q_COND = ('fA', 'fB', 'wA', 'wB', 'rg', 'abs_rg', 'rg_pos', 'right_gap', 'zone', 'impasse', 'adv', 'advA', 'advB', 'mutual', 'step', 'holdA', 'holdB', 'err', 'words')
EXTRA = ('obs.f', 'obs.noise', 'obs.zone', 'obs.impasse', 'obs.wA', 'obs.wB', 'base.N.tiltA', 'base.N.tiltB',
         'op.fA', 'op.fB', 'op.wA', 'op.wB', 'op.rg', 'op.zone', 'op.impasse', 'op.adv', 'op.mutual', 'op.step',
         'op.right_gap', 'base.P.address', 'base.P.addressA', 'base.P.addressB', 'base.P.adv_address', 'base.P.zone_address')
PER_MODEL = ('obs.noise', 'base.N.rg', 'base.N.right_gap', 'obs.impasse', 'base.N.impasse', 'base.P.impasse', 'base.PA.impasse', 'op.impasse',
             'obs.zone', 'base.N.zone', 'base.PA.zone', 'base.P.rg', 'op.rg', 'base.P.address', 'base.PA.rg', 'op.adv', 'base.N.adv', 'base.P.adv',
             'base.PA.adv', 'base.anger.adv', 'base.PA.mutual', 'g1.N.rg', 'g2.N.rg', 'g1.N.impasse', 'g2.N.impasse', 'g1.PA.rg', 'g2.PA.rg',
             'g1.PA.impasse', 'g2.PA.impasse', 'g1.PA.adv', 'g2.PA.adv', 'g1.PA.mutual', 'g2.PA.mutual', 'g2.PA.zone', 'g2.N.zone')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--numbers', default=os.path.join(ROOT, 'out', 'numbers.json'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'out', 'report_numbers.json'))
    a = ap.parse_args()
    N = json.load(open(a.numbers))
    models = N['models']

    def one(v, key):
        scale = 100.0 if key.split('.')[-1] in RATE else 1.0
        return None if v.get('est') is None else [round(v['est'] * scale, 1), round(v['lo'] * scale, 1), round(v['hi'] * scale, 1)]

    keys = list(EXTRA)
    for arm in ('base', 'g1', 'g2'):
        for c in (('N', 'P', 'PA') if arm == 'base' else ('N', 'PA')):
            keys += [arm + '.' + c + '.' + q for q in Q_COND]
    keys += ['base.anger.' + q for q in ('adv', 'step', 'rg', 'zone', 'impasse', 'mutual')]
    for arm in ('g1', 'g2'):
        for c in ('N', 'PA'):
            keys += [arm + '-base.' + c + '.' + q for q in ('rg', 'zone', 'impasse', 'adv', 'mutual', 'err')]
    M = N['metrics']
    R = {'models': models, 'n_cases': N['n_cases'], 'n_boot': N['n_boot'], 'trials': N['trials'], 'unresolved_errors': N['unresolved_errors']}
    R['p'] = {k: one(M[k]['pooled'], k) for k in keys if k in M}
    R['pm'] = {k: [one(M[k][m], k) for m in models] for k in PER_MODEL if k in M}
    R['nc'] = {k: [M[k].get(m, {}).get('n_cases') for m in models] for k in ('base.N.rg', 'base.P.rg', 'base.PA.rg', 'obs.f', 'op.rg', 'g1.N.rg', 'g1.PA.rg', 'g2.N.rg', 'g2.PA.rg') if k in M}
    R['ms'] = {k: {'p': one(v['pooled'], k), 'm': [one(v[m], k) for m in models] if k in ('obs.f', 'base.N.fmean', 'base.PA.fmean', 'g1.PA.fmean', 'g2.PA.fmean', 'g1.N.fmean', 'g2.N.fmean') else None}
               for k, v in N['merit_sens'].items() if not k.startswith('op.') and '.P.' not in k}
    R['ratio'] = {k: (None if v['pooled'].get('est') is None else [v['pooled']['est'], v['pooled']['lo'], v['pooled']['hi']]) for k, v in N['ratio'].items() if k.startswith('base.') or k.startswith('op.')}
    R['bm'] = {k: [one(v[mt]['pooled'], k) for mt in ('A', 'M', 'B')] for k, v in N['by_merit'].items()
               if k in ('obs.f', 'obs.impasse', 'base.N.rg', 'base.N.impasse', 'base.P.rg', 'base.P.impasse', 'base.PA.rg', 'base.PA.impasse', 'base.PA.adv',
                        'base.N.fA', 'base.N.fB', 'g2.PA.impasse', 'g2.PA.rg', 'g2.PA.adv', 'g2.PA.fmean', 'base.PA.fmean', 'g1.PA.fmean', 'g1.PA.impasse')}
    R['bd'] = N['by_domain']
    R['steps'] = {k[7:]: v for k, v in N['steps'].items() if k.startswith('pooled|') and k not in ('pooled|g1|P', 'pooled|g2|P')}
    R['zh'] = {k: v for k, v in N['zone_hist'].items() if k in ('edges', 'obs.zone', 'op.zone', 'base.N.zone', 'base.P.zone', 'base.PA.zone', 'g1.PA.zone', 'g2.PA.zone')}
    R['cp'] = [[c[1], c[2], c[3]] for c in N['case_points']]
    j = N['judge']
    R['judge'] = {k: v for k, v in j.items() if k != 'cells'}
    R['judge']['cells'] = {k: v.get('pooled') for k, v in j.get('cells', {}).items()}
    text = json.dumps(R, separators=(',', ':'), sort_keys=True)
    open(a.out, 'w').write(text)
    print(len(text), 'bytes  md5', hashlib.md5(text.encode()).hexdigest())


if __name__ == '__main__':
    main()
