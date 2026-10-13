"""Rewrite the results block of README.md from results/summary.json (run summarize.py first)."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
START, END = '<!-- results:start -->', '<!-- results:end -->'
SETS = [('large', '**Large tasks**: fresh SWE-bench Lite + hard Verified'), ('swe-verified-hard', 'SWE-bench Verified, hard (10)'),
        ('swe-lite-test', 'SWE-bench Lite, fresh sample (20)'), ('swe-lite-test-unobserved', 'Fresh sample, never looked at (19)'),
        ('swe-lite', 'SWE-bench Lite, development sample (20)'), ('small', '**Small tasks**: Forge set + polyglot'),
        ('standard', 'Forge set (20)'), ('hard', 'Forge hard set (8)'), ('polyglot-py', 'Polyglot · Python (34)'), ('all', 'All tasks')]
NAMES = {'forge': 'Forge', 'claude-code': 'Claude Code'}


def usd(v, d=4):
    return '—' if v is None else f'${v:.{d}f}'


def row(label, agent, a):
    ci = a['success_ci95']
    rate = '—' if a['success_rate'] is None else f"{a['success_rate'] * 100:.1f}%"
    band = f" ({ci[0] * 100:.0f}–{ci[1] * 100:.0f}%)" if ci else ''
    return (f"| {label} | {NAMES[agent]} | {a['accepted']}/{a['runs']} | {rate}{band} | {usd(a['cost_per_accepted_usd'])} | "
            f"{usd(a['cost_per_run_usd'])} | {a['input_tokens_mean']:,.0f} | {a['output_tokens_mean']:,.0f} | "
            f"{a['turns_mean']:.2f} | {a['seconds_median']:.0f} |")


def block(summary):
    off = summary['official']
    lines = ['| Tasks | Agent | Accepted | Success (95% CI) | Cost / accepted | Cost / run | Input tok / run | Output tok / run | Turns | Median s |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for sid, label in SETS:
        for i, agent in enumerate(['forge', 'claude-code']):
            if agent not in off:
                continue
            a = off[agent]['overall'] if sid == 'all' else off[agent].get('groups', {}).get(sid) or off[agent]['by_set'].get(sid)
            if a:
                lines.append(row(label if i == 0 else '', agent, a))
    head = ''
    for group, words in (('large', 'On large tasks (real GitHub issues in real repositories)'), ('small', 'On small tasks')):
        f, k = (off.get(a, {}).get('groups', {}).get(group) for a in ('forge', 'claude-code'))
        if not (f and k and f['cost_per_accepted_usd'] and k['cost_per_accepted_usd']):
            continue
        x = k['cost_per_accepted_usd'] / f['cost_per_accepted_usd']
        cost = (f"Claude Code costs **{x:.2f}×** as much per solved task" if x >= 1
                else f"Forge costs **{1 / x:.2f}×** as much per solved task")
        head += (f"{words}: Forge solved {f['accepted']}/{f['runs']} and Claude Code {k['accepted']}/{k['runs']}; {cost} "
                 f"({usd(f['cost_per_accepted_usd'], 3)} against {usd(k['cost_per_accepted_usd'], 3)}).\n\n")
    return (f"{head}" + '\n'.join(lines) +
            f"\n\nOfficial runs only, pooled from `runs/` and computed by `harness/summarize.py` on {summary['generated_at'][:10]}. "
            "Every other run (earlier builds, ablations) is in `runs/` too; see `results/summary.json`.")


def main():
    summary = json.loads((ROOT / 'results' / 'summary.json').read_text())
    readme = (ROOT / 'README.md').read_text()
    i, j = readme.index(START) + len(START), readme.index(END)
    (ROOT / 'README.md').write_text(readme[:i] + '\n' + block(summary) + '\n' + readme[j:])
    print('README.md results updated')


if __name__ == '__main__':
    main()
