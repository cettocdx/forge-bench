"""Aggregate every recorded run into results/summary.json (what the benchmark page shows).

Each run lives in runs/<id>/ with:
  run.json       label, agent, kind (official | exploratory | ablation), date, notes, and for an official
                 run of a comparison other than the one with Claude Code, comparison (e.g. "astra")
  meta.json      the setup the runner wrote (versions, model, effort, task file SHA-256)
  results.jsonl  one line per task run, verbatim from the runner

Token counts are compared as total prompt tokens (uncached + cache read + cache write), which is
how OpenRouter reports RIFT's prompt_tokens; Claude Code's Anthropic fields are summed to match.
A run with incomplete usage is counted in success but flagged, never treated as zero cost.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, math, statistics

ROOT = Path(__file__).resolve().parent.parent
# Instances of the fresh and hard SWE-bench samples looked at before the official build was final (see
# METHODOLOGY.md): those samples are also given without them, as the extra sets "<set>-unobserved".
# django__django-12284 led to an earlier fix; the first six of each sample were run with GPT-6 Astra while
# 30eb649 was made. The development sample (swe-lite) was used to find and fix Forge's problems, so it has
# no such view.
OBSERVED = {
    'swe-lite-test': {'django__django-12284', 'django__django-14915', 'django__django-14997', 'django__django-15738',
                      'matplotlib__matplotlib-24265', 'pallets__flask-5063'},
    'swe-verified-hard': {'astropy__astropy-13398', 'astropy__astropy-13579', 'astropy__astropy-14369',
                          'django__django-13449', 'django__django-13837', 'pylint-dev__pylint-4551'},
}
VIEW = '-unobserved'
# The headline groups: large tasks are real repositories with issues outside the development sample
# (SWE-bench Lite except that sample, and the hard SWE-bench Verified instances); small tasks are
# single-file exercises and the Forge set. 'swe-lite-300' is all of SWE-bench Lite, the benchmark Aider
# reported on, development sample included.
GROUPS = {
    'large': ('swe-lite-test', 'swe-lite-rest', 'swe-verified-hard'),
    'swe-lite-300': ('swe-lite', 'swe-lite-test', 'swe-lite-rest'),
    'small': ('standard', 'hard', 'polyglot-py'),
}


def primary(rs):
    return [r for r in rs if not (r['set'] or '').endswith(VIEW)]


def num(v):
    return float(v) if v not in (None, '') else None


def set_of(task_id, known):
    """Older RIFT records carry no set: the task files say which set an id belongs to."""
    return known.get(task_id) or ('polyglot-py' if task_id.startswith('py_') else None)


def records(run_dir, known=None):
    known = known or {}
    out = []
    for line in (run_dir / 'results.jsonl').read_text().splitlines():
        line = line.removeprefix('BENCH ').strip()
        if not line:
            continue
        r = json.loads(line)
        if 'task' not in r:
            continue  # budget stop markers
        if r.get('gold_valid') is False:
            continue  # a SWE-bench instance whose own gold patch fails here is left out for every agent
        out.append({
            'task': r['task'], 'set': r.get('set') or set_of(r['task'], known), 'rep': r.get('rep'),
            'accepted': bool(r.get('accepted')),
            'cost_usd': num(r.get('cost_usd')), 'input_tokens': num(r.get('input_tokens')),
            'cache_read': num(r.get('cached_read')), 'cache_write': num(r.get('cache_write')),
            'output_tokens': num(r.get('output_tokens')), 'turns': num(r.get('turns')), 'seconds': num(r.get('seconds')),
            'usage_complete': r.get('usage_complete', True) is not False,
        })
        if out[-1]['set'] in OBSERVED and r['task'] not in OBSERVED[out[-1]['set']]:
            out.append(dict(out[-1], set=out[-1]['set'] + VIEW))
    return out


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 6) if xs else None


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))], 2) if xs else None


def aggregate(rs):
    k, n = sum(r['accepted'] for r in rs), len(rs)
    cost = sum(r['cost_usd'] or 0 for r in rs)
    return {
        'runs': n, 'accepted': k, 'success_rate': round(k / n, 4) if n else None, 'success_ci95': wilson(k, n),
        'total_cost_usd': round(cost, 4), 'cost_per_run_usd': round(cost / n, 5) if n else None,
        'cost_per_accepted_usd': round(cost / k, 5) if k else None,
        'input_tokens_mean': mean([r['input_tokens'] for r in rs]),
        'cache_read_mean': mean([r['cache_read'] for r in rs]),
        'cache_write_mean': mean([r['cache_write'] for r in rs]),
        'output_tokens_mean': mean([r['output_tokens'] for r in rs]),
        'turns_mean': mean([r['turns'] for r in rs]),
        'seconds_median': pct([r['seconds'] for r in rs], 0.5), 'seconds_p90': pct([r['seconds'] for r in rs], 0.9),
        'incomplete_usage': sum(not r['usage_complete'] for r in rs),
    }


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=ROOT / 'results' / 'summary.json')
    args = ap.parse_args()
    known = {t['id']: t['set'] for f in (ROOT / 'tasks').glob('*.json') for t in json.loads(f.read_text())}
    runs, pooled = [], {}
    for d in sorted(p for p in (ROOT / 'runs').iterdir() if p.is_dir()):
        info = json.loads((d / 'run.json').read_text())
        meta = json.loads((d / 'meta.json').read_text()) if (d / 'meta.json').exists() else {}
        rs = records(d, known)
        if info['kind'] == 'official':
            pool = pooled.setdefault(info.get('comparison', 'claude'), {})
            pool.setdefault(info['agent'], {'label': info['label'], 'runs': [], 'records': []})
            pool[info['agent']]['runs'].append(d.name)
            pool[info['agent']]['records'] += rs
        sets = sorted({r['set'] for r in rs if r['set']})
        runs.append({
            'id': d.name, **info, 'meta': meta,
            'files': {f.name: sha256(f) for f in sorted(d.iterdir()) if f.is_file()},
            'overall': aggregate(primary(rs)),
            'by_set': {s: aggregate([r for r in rs if r['set'] == s]) for s in sets},
            'per_task': {t: {'accepted': sum(r['accepted'] for r in g), 'runs': len(g), 'cost_usd': mean([r['cost_usd'] for r in g]),
                             'input_tokens': mean([r['input_tokens'] for r in g]), 'seconds': mean([r['seconds'] for r in g])}
                         for t in sorted({r['task'] for r in rs}) for g in [[r for r in primary(rs) if r['task'] == t]]},
        })
    # Each comparison: every official run of an agent pooled from its raw records, on the tasks every
    # agent of that comparison ran (so no agent is compared on a different mix of tasks).
    # (an instance in two sets, sympy__sympy-17630, is two tasks: one per set)
    def compare(pool, groups):
        common = set.intersection(*({(r['set'], r['task']) for r in p['records']} for p in pool.values())) if pool else set()
        out = {}
        for agent, p in pool.items():
            rs = [r for r in p['records'] if (r['set'], r['task']) in common]
            left_out = sorted({r['task'] for r in p['records'] if (r['set'], r['task']) not in common})
            sets = sorted({r['set'] for r in rs if r['set']})
            out[agent] = {
                'label': p['label'], 'runs': p['runs'], 'tasks_left_out': left_out, 'overall': aggregate(primary(rs)),
                'groups': {g: aggregate([r for r in rs if r['set'] in members]) for g, members in groups.items()
                           if any(r['set'] in members for r in rs)},
                'by_set': {s: aggregate([r for r in rs if r['set'] == s]) for s in sets},
                'per_task': {t: {'set': g[0]['set'], 'accepted': sum(r['accepted'] for r in g), 'runs': len(g),
                                 'cost_usd': mean([r['cost_usd'] for r in g]), 'input_tokens': mean([r['input_tokens'] for r in g]),
                                 'output_tokens': mean([r['output_tokens'] for r in g]), 'seconds': mean([r['seconds'] for r in g])}
                             for t in sorted({r['task'] for r in rs}) for g in [[r for r in primary(rs) if r['task'] == t]]},
            }
        return out, common
    official, common = compare(pooled.get('claude', {}), GROUPS)
    # Other comparisons (Forge and Codex on GPT-6 Astra): a sample of SWE-bench, so no all-of-Lite group.
    comparisons = {name: compare(pool, {g: GROUPS[g] for g in ('large', 'small')})[0]
                   for name, pool in pooled.items() if name != 'claude'}
    # Every agent x model x effort we ran (official and ablation runs), per task set: what the
    # leaderboards and the success-vs-cost charts plot.
    configs = {}
    for d in sorted(p for p in (ROOT / 'runs').iterdir() if p.is_dir()):
        info = json.loads((d / 'run.json').read_text())
        if info['kind'] not in ('official', 'ablation') or info.get('comparison', 'claude') != 'claude':
            continue
        meta = json.loads((d / 'meta.json').read_text()) if (d / 'meta.json').exists() else {}
        model = 'Claude Sonnet 5.5' if 'sonnet' in str(meta.get('model', '')) else 'Claude Opus 5.5'
        effort = str(meta.get('effort') or 'medium')
        key = f"{info['agent']}|{model}|{effort}"
        c = configs.setdefault(key, {'key': key, 'agent': info['agent'], 'model': model, 'effort': effort,
                                     'kinds': set(), 'runs': [], 'records': []})
        c['kinds'].add(info['kind'])
        c['runs'].append(d.name)
        c['records'] += records(d, known)
    config_list = []
    for c in configs.values():
        rs = c.pop('records')
        sets = sorted({r['set'] for r in rs if r['set']})
        c['kind'] = 'official' if 'official' in c.pop('kinds') else 'ablation'
        # The official configurations are compared on the same tasks as the comparison above.
        if c['kind'] == 'official':
            rs = [r for r in rs if (r['set'], r['task']) in common]
            sets = sorted({r['set'] for r in rs if r['set']})
        c['by_set'] = {st: aggregate([r for r in rs if r['set'] == st]) for st in sets}
        config_list.append(c)
    summary = {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'schema': 1,
        'official': official,
        'comparisons': comparisons,
        'configs': sorted(config_list, key=lambda c: c['key']),
        'tasks': {p.name: sha256(p) for p in sorted((ROOT / 'tasks').glob('*')) if p.is_file()},
        'runs': runs,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=1) + '\n')
    print(f"{len(runs)} runs -> {args.out}")


if __name__ == '__main__':
    main()
