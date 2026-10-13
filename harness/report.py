"""Summarise the Claude-vs-RIFT benchmark: RIFT `BENCH {json}` logs and Claude Code JSONL lines.

Input tokens are compared as total prompt tokens (uncached + cache read + cache write), which is
what OpenRouter reports as prompt_tokens for RIFT; Claude Code's three Anthropic fields are summed
to match. Usage marked incomplete is reported, never counted as zero.
"""
from pathlib import Path
import argparse, json, statistics

HERE = Path(__file__).resolve().parent
NUM = ('input_tokens', 'cached_read', 'cache_write', 'output_tokens', 'cost_usd', 'seconds', 'turns')


def load(paths):
    sets = {t['id']: t['set'] for f in sorted((HERE.parent / 'tasks').glob('*.json')) for t in json.loads(f.read_text())}
    runs = []
    for spec in paths:
        label, _, path = spec.rpartition('=')
        for raw in Path(path).read_text().splitlines():
            raw = raw.removeprefix('BENCH ').strip()
            if not raw:
                continue
            r = json.loads(raw)
            if 'task' not in r:
                continue
            for k in NUM:
                r[k] = float(r[k]) if r.get(k) not in (None, '') else None
            r['arm'] = label or ('Claude Code' if r['arm'] == 'CC' else 'RIFT')
            r['set'] = r.get('set') or sets.get(r['task']) or ('polyglot-py' if r['task'].startswith('py_') else '?')
            runs.append(r)
    return runs


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None


def mean(rs, k):
    xs = [r[k] for r in rs if r.get(k) is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, nd=0, prefix=''):
    return '—' if x is None else f'{prefix}{x:,.{nd}f}'


def summary(runs):
    arms = list(dict.fromkeys(r['arm'] for r in runs))
    sets = list(dict.fromkeys(r['set'] for r in runs))
    rows = []
    for arm in arms:
        rs = [r for r in runs if r['arm'] == arm]
        acc = sum(r['accepted'] for r in rs)
        cost = sum(r['cost_usd'] or 0 for r in rs)
        by_set = [f"{sum(r['accepted'] for r in rs if r['set'] == s)}/{sum(r['set'] == s for r in rs)}" for s in sets]
        rows.append([arm, f'{acc}/{len(rs)} ({100 * acc / len(rs):.0f}%)', *by_set,
                     fmt(cost, 3, '$'), fmt(cost / len(rs), 4, '$'), fmt(cost / acc if acc else None, 4, '$'),
                     fmt(mean(rs, 'input_tokens')), fmt(mean(rs, 'cached_read')), fmt(mean(rs, 'cache_write')),
                     fmt(mean(rs, 'output_tokens')), fmt(mean(rs, 'turns'), 1),
                     fmt(statistics.median([r['seconds'] for r in rs]), 0),
                     fmt(pct([r['seconds'] for r in rs], 0.9), 0),
                     str(sum(not r.get('usage_complete', True) for r in rs))])
    head = ['Arm', 'Accepted', *sets, 'Total cost', 'Cost/run', 'Cost/accepted',
            'Input tok (mean)', 'Cache read (mean)', 'Cache write (mean)', 'Output tok (mean)', 'Turns (mean)',
            'Median s', 'p90 s', 'Incomplete usage']
    return table(head, rows)


def per_task(runs):
    tasks = sorted({r['task'] for r in runs}, key=lambda t: (t[0] == 'x', t))
    arms = list(dict.fromkeys(r['arm'] for r in runs))
    rows = []
    for t in tasks:
        cells = [t]
        costs = {}
        for arm in arms:
            rs = [r for r in runs if r['task'] == t and r['arm'] == arm]
            if not rs:
                cells += ['—'] * 4
                continue
            costs[arm] = mean(rs, 'cost_usd')
            cells += [f"{sum(r['accepted'] for r in rs)}/{len(rs)}", fmt(costs[arm], 4, '$'),
                      fmt(mean(rs, 'input_tokens')), fmt(mean(rs, 'seconds'), 0)]
        rows.append(cells)
    head = ['Task'] + [f'{a} {c}' for a in arms for c in ('ok', '$', 'input', 's')]
    return table(head, rows)


def failures(runs):
    bad = [r for r in runs if not r['accepted']]
    return '\n'.join(f"- {r['arm']} {r['task']} rep {r['rep']}: state={r.get('state')} "
                     f"{(r.get('detail') or r.get('reason') or '').strip()[-200:]!r}" for r in bad) or '- none'


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows]
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('logs', nargs='+', help='[label=]path; RIFT BENCH logs or Claude Code JSONL')
    args = ap.parse_args()
    runs = load(args.logs)
    print(f'Runs: {len(runs)}\n\n## Summary\n\n{summary(runs)}\n\n## Per task (mean over reps)\n\n'
          f'{per_task(runs)}\n\n## Not accepted\n\n{failures(runs)}')


if __name__ == '__main__':
    main()
